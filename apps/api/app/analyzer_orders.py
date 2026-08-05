"""Analyzer order queue: attempts, immutable messages, and TCP transport send.

Phase 2 uses a LaboraIQ stub order payload over TCP. Phase 3 replaces the payload
builder/parser with HL7 LAW while keeping this queue and message store.
"""

from __future__ import annotations

import hashlib
import socket
import uuid
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.auth import AuthContext
from app.models import (
    Analyzer,
    AnalyzerMessage,
    AnalyzerOrderAttempt,
    AnalyzerWorklistItem,
    Specimen,
)


def _hash_payload(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_stub_order_payload(
    *,
    specimen: Specimen,
    analyzer: Analyzer,
    worklist_item: AnalyzerWorklistItem,
    correlation_id: str,
) -> str:
    """Provisional order frame until HL7 LAW is implemented in Phase 3."""
    return "\n".join(
        [
            "LABORAIQ-ORDER-V0",
            f"protocol={analyzer.protocol}",
            f"analyzer_code={analyzer.code}",
            f"barcode={specimen.barcode}",
            f"accession={specimen.accession_number or ''}",
            f"machine_test_code={worklist_item.machine_test_code}",
            f"correlation_id={correlation_id}",
            "END",
        ]
    )


def next_attempt_number(db: Session, worklist_item_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(AnalyzerOrderAttempt.attempt_no)).where(
            AnalyzerOrderAttempt.worklist_item_id == worklist_item_id
        )
    )
    return int(current or 0) + 1


def create_queued_attempt(
    db: Session,
    *,
    worklist_item: AnalyzerWorklistItem,
    correlation_id: str,
    user_id: uuid.UUID | None,
) -> AnalyzerOrderAttempt:
    attempt = AnalyzerOrderAttempt(
        organization_id=worklist_item.organization_id,
        branch_id=worklist_item.branch_id,
        worklist_item_id=worklist_item.id,
        analyzer_id=worklist_item.analyzer_id,
        attempt_no=next_attempt_number(db, worklist_item.id),
        state="queued",
        correlation_id=correlation_id,
        created_by=user_id,
    )
    db.add(attempt)
    db.flush()
    return attempt


def store_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    analyzer_id: uuid.UUID,
    worklist_item_id: uuid.UUID | None,
    attempt_id: uuid.UUID | None,
    direction: str,
    body: str,
    correlation_id: str,
    content_type: str = "text/plain",
) -> AnalyzerMessage:
    message = AnalyzerMessage(
        organization_id=organization_id,
        analyzer_id=analyzer_id,
        worklist_item_id=worklist_item_id,
        attempt_id=attempt_id,
        direction=direction,
        content_type=content_type,
        body=body,
        payload_hash=_hash_payload(body),
        correlation_id=correlation_id,
    )
    db.add(message)
    db.flush()
    return message


def send_order_over_tcp(analyzer: Analyzer, payload: str) -> tuple[bool, str, str | None]:
    """Send stub order bytes. Returns (success, detail, optional inbound body)."""
    try:
        with socket.create_connection(
            (analyzer.host, analyzer.port),
            timeout=analyzer.connection_timeout_seconds,
        ) as connection:
            connection.sendall(payload.encode("utf-8"))
            connection.settimeout(min(2, max(1, analyzer.connection_timeout_seconds)))
            try:
                inbound = connection.recv(4096)
            except TimeoutError:
                inbound = b""
            inbound_text = inbound.decode("utf-8", errors="replace") if inbound else None
            return True, "TCP order payload delivered", inbound_text
    except OSError as error:
        return False, (str(error)[:500] or error.__class__.__name__), None


def process_order_attempt(
    db: Session,
    request: Request,
    context: AuthContext,
    attempt: AnalyzerOrderAttempt,
) -> AnalyzerOrderAttempt:
    if attempt.state != "queued":
        return attempt

    worklist_item = db.get(AnalyzerWorklistItem, attempt.worklist_item_id)
    analyzer = db.get(Analyzer, attempt.analyzer_id)
    specimen = db.get(Specimen, worklist_item.specimen_id) if worklist_item else None
    if worklist_item is None or analyzer is None or specimen is None:
        attempt.state = "failed"
        attempt.error = "Worklist item, analyzer, or specimen missing"
        attempt.finished_at = datetime.now(UTC)
        return attempt

    attempt.state = "sending"
    attempt.started_at = datetime.now(UTC)
    worklist_item.status = "in_flight"
    worklist_item.updated_by = context.user_id
    db.flush()

    payload = build_stub_order_payload(
        specimen=specimen,
        analyzer=analyzer,
        worklist_item=worklist_item,
        correlation_id=attempt.correlation_id,
    )
    request_message = store_message(
        db,
        organization_id=attempt.organization_id,
        analyzer_id=analyzer.id,
        worklist_item_id=worklist_item.id,
        attempt_id=attempt.id,
        direction="outbound",
        body=payload,
        correlation_id=attempt.correlation_id,
        content_type="text/plain; laboraiq-order=v0",
    )
    attempt.request_message_id = request_message.id
    attempt.payload_hash = request_message.payload_hash

    success, detail, inbound = send_order_over_tcp(analyzer, payload)
    if inbound:
        response_message = store_message(
            db,
            organization_id=attempt.organization_id,
            analyzer_id=analyzer.id,
            worklist_item_id=worklist_item.id,
            attempt_id=attempt.id,
            direction="inbound",
            body=inbound,
            correlation_id=attempt.correlation_id,
        )
        attempt.response_message_id = response_message.id
    elif success:
        # Transport accepted the write; Phase 3 will require a real protocol ACK.
        ack_body = "TCP_TRANSPORT_OK\nnote=application ACK pending HL7 Phase 3\n"
        response_message = store_message(
            db,
            organization_id=attempt.organization_id,
            analyzer_id=analyzer.id,
            worklist_item_id=worklist_item.id,
            attempt_id=attempt.id,
            direction="inbound",
            body=ack_body,
            correlation_id=attempt.correlation_id,
            content_type="text/plain; laboraiq-transport=v0",
        )
        attempt.response_message_id = response_message.id

    attempt.finished_at = datetime.now(UTC)
    if success:
        attempt.state = "acknowledged"
        attempt.error = None
        worklist_item.status = "completed"
        event_type = "analyzer.order_acknowledged"
    else:
        attempt.state = "failed"
        attempt.error = detail
        retries_used = attempt.attempt_no
        max_attempts = analyzer.retry_limit + 1
        if retries_used < max_attempts:
            worklist_item.status = "queued"
            create_queued_attempt(
                db,
                worklist_item=worklist_item,
                correlation_id=request.state.correlation_id,
                user_id=context.user_id,
            )
            event_type = "analyzer.order_retry_queued"
        else:
            worklist_item.status = "failed"
            event_type = "analyzer.order_failed"
    worklist_item.updated_by = context.user_id

    record_event(
        db,
        request,
        context,
        event_type=event_type,
        entity_type="analyzer_order_attempt",
        entity_id=attempt.id,
        branch_id=attempt.branch_id,
        action="process",
        new={
            "state": attempt.state,
            "attempt_no": attempt.attempt_no,
            "worklist_status": worklist_item.status,
            "error": attempt.error,
            "payload_hash": attempt.payload_hash,
        },
    )
    return attempt


def process_queued_orders(
    db: Session,
    request: Request,
    context: AuthContext,
    *,
    limit: int = 20,
) -> list[AnalyzerOrderAttempt]:
    filters = [
        AnalyzerOrderAttempt.organization_id == context.organization_id,
        AnalyzerOrderAttempt.state == "queued",
    ]
    if not context.is_organization_scoped:
        filters.append(AnalyzerOrderAttempt.branch_id.in_(context.branch_ids or {uuid.uuid4()}))
    attempts = list(
        db.scalars(
            select(AnalyzerOrderAttempt)
            .where(*filters)
            .order_by(AnalyzerOrderAttempt.created_at.asc(), AnalyzerOrderAttempt.attempt_no.asc())
            .limit(limit)
        ).all()
    )
    processed: list[AnalyzerOrderAttempt] = []
    for attempt in attempts:
        processed.append(process_order_attempt(db, request, context, attempt))
    return processed

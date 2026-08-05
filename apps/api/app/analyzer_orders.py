"""Analyzer order queue: attempts, immutable messages, and TCP/MLLP send.

Phase 3 uses HL7 v2.5.1 OML^O33 over MLLP for analyzers with protocol HL7_LAW.
Other protocols keep the LaboraIQ stub frame until dedicated adapters exist.
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
from app.hl7_law import (
    build_oml_o33,
    is_result_message,
    parse_ack,
    read_mllp_messages,
    unwrap_mllp,
    wrap_mllp,
)
from app.models import (
    Analyzer,
    AnalyzerMessage,
    AnalyzerOrderAttempt,
    AnalyzerWorklistItem,
    LabOrder,
    Patient,
    Specimen,
    TestCatalogItem,
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
    """Legacy stub frame for non-HL7 analyzers."""
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


def build_order_payload(
    db: Session,
    *,
    specimen: Specimen,
    analyzer: Analyzer,
    worklist_item: AnalyzerWorklistItem,
    correlation_id: str,
) -> tuple[str, str]:
    """Return (payload_body, content_type)."""
    if analyzer.protocol != "HL7_LAW":
        return (
            build_stub_order_payload(
                specimen=specimen,
                analyzer=analyzer,
                worklist_item=worklist_item,
                correlation_id=correlation_id,
            ),
            "text/plain; laboraiq-order=v0",
        )

    order = db.get(LabOrder, worklist_item.order_id)
    patient = db.get(Patient, order.patient_id) if order else None
    test = db.get(TestCatalogItem, worklist_item.test_id)
    if order is None or patient is None or test is None:
        raise ValueError("Order, patient, or test missing for HL7 order build")

    message = build_oml_o33(
        analyzer_code=analyzer.code,
        barcode=specimen.barcode,
        accession=specimen.accession_number,
        machine_test_code=worklist_item.machine_test_code,
        test_name=test.name,
        patient_number=patient.patient_number,
        patient_name=patient.full_name,
        patient_sex=patient.sex,
        order_number=order.order_number,
        correlation_id=correlation_id,
    )
    return message, "application/hl7-v2; profile=LAW; type=OML^O33"


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


def send_order_over_tcp(
    analyzer: Analyzer,
    payload: str,
    *,
    use_mllp: bool = False,
) -> tuple[bool, str, list[str]]:
    """Send order bytes. Returns (transport_ok, detail, inbound HL7/plain messages)."""
    try:
        with socket.create_connection(
            (analyzer.host, analyzer.port),
            timeout=analyzer.connection_timeout_seconds,
        ) as connection:
            outbound = wrap_mllp(payload) if use_mllp else payload.encode("utf-8")
            connection.sendall(outbound)
            read_timeout = min(5.0, max(1.0, float(analyzer.connection_timeout_seconds)))
            connection.settimeout(read_timeout)
            if use_mllp:
                inbound_messages = read_mllp_messages(
                    connection.recv,
                    timeout_seconds=read_timeout,
                    max_messages=2,
                )
                # Brief second window for a follow-up ORU if only ACK arrived.
                if len(inbound_messages) == 1:
                    connection.settimeout(min(1.0, read_timeout))
                    more = read_mllp_messages(
                        connection.recv,
                        timeout_seconds=1.0,
                        max_messages=1,
                        idle_rounds=1,
                    )
                    inbound_messages.extend(more)
                if not inbound_messages:
                    return False, "No MLLP ACK received from analyzer", []
                return True, "MLLP exchange completed", inbound_messages

            try:
                inbound = connection.recv(4096)
            except TimeoutError:
                inbound = b""
            if inbound:
                framed = unwrap_mllp(inbound)
                if framed:
                    return True, "TCP order payload delivered", framed
                text = inbound.decode("utf-8", errors="replace")
                return True, "TCP order payload delivered", [text]
            return True, "TCP order payload delivered", []
    except OSError as error:
        return False, (str(error)[:500] or error.__class__.__name__), []


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

    try:
        payload, content_type = build_order_payload(
            db,
            specimen=specimen,
            analyzer=analyzer,
            worklist_item=worklist_item,
            correlation_id=attempt.correlation_id,
        )
    except ValueError as error:
        attempt.state = "failed"
        attempt.error = str(error)[:500]
        attempt.finished_at = datetime.now(UTC)
        worklist_item.status = "failed"
        worklist_item.updated_by = context.user_id
        return attempt

    use_mllp = analyzer.protocol == "HL7_LAW"
    request_message = store_message(
        db,
        organization_id=attempt.organization_id,
        analyzer_id=analyzer.id,
        worklist_item_id=worklist_item.id,
        attempt_id=attempt.id,
        direction="outbound",
        body=payload,
        correlation_id=attempt.correlation_id,
        content_type=content_type,
    )
    attempt.request_message_id = request_message.id
    attempt.payload_hash = request_message.payload_hash

    transport_ok, detail, inbound_messages = send_order_over_tcp(
        analyzer, payload, use_mllp=use_mllp
    )

    ack_message: str | None = None
    result_message: str | None = None
    result_message_id: uuid.UUID | None = None
    for inbound in inbound_messages:
        stored = store_message(
            db,
            organization_id=attempt.organization_id,
            analyzer_id=analyzer.id,
            worklist_item_id=worklist_item.id,
            attempt_id=attempt.id,
            direction="inbound",
            body=inbound,
            correlation_id=attempt.correlation_id,
            content_type=(
                "application/hl7-v2; profile=LAW"
                if use_mllp or inbound.startswith("MSH|")
                else "text/plain"
            ),
        )
        if attempt.response_message_id is None:
            attempt.response_message_id = stored.id
        if use_mllp or inbound.startswith("MSH|"):
            if is_result_message(inbound):
                result_message = inbound
                result_message_id = stored.id
            elif ack_message is None:
                ack_message = inbound

    attempt.finished_at = datetime.now(UTC)
    success = False
    if not transport_ok:
        attempt.state = "failed"
        attempt.error = detail
    elif use_mllp:
        if ack_message is None:
            attempt.state = "failed"
            attempt.error = "HL7 ACK missing from analyzer response"
        else:
            ack = parse_ack(ack_message)
            if ack.ok:
                success = True
                attempt.state = "acknowledged"
                attempt.error = None
                worklist_item.status = "result_received" if result_message else "awaiting_result"
            else:
                attempt.state = "failed"
                attempt.error = f"HL7 NAK {ack.code}: {ack.text}"[:500]
    else:
        # Stub protocol: transport write success is enough (Phase 2 behaviour).
        success = True
        attempt.state = "acknowledged"
        attempt.error = None
        worklist_item.status = "completed"
        if not inbound_messages:
            ack_body = "TCP_TRANSPORT_OK\nnote=stub protocol has no application ACK\n"
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

    if not success:
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
    else:
        event_type = (
            "analyzer.order_result_received" if result_message else "analyzer.order_acknowledged"
        )
        if result_message:
            from app.results import normalize_worklist_result

            normalize_worklist_result(
                db,
                request,
                context,
                worklist_item,
                oru_body=result_message,
                source_message_id=result_message_id,
            )

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
            "result_received": bool(result_message),
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

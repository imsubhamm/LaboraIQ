"""Lab result normalization, review workflow, and PDF report generation."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.auth import AuthContext
from app.hl7_law import extract_oru_observations, is_result_message
from app.models import (
    AnalyzerMessage,
    AnalyzerParameterMapping,
    AnalyzerWorklistItem,
    LabOrder,
    LabResult,
    LabResultObservation,
    Patient,
    Specimen,
    TestCatalogItem,
    TestCatalogParameter,
)


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def compute_flag(
    value: str,
    *,
    reference_low: str | None,
    reference_high: str | None,
    analyzer_flags: str | None,
) -> str | None:
    if analyzer_flags:
        return analyzer_flags.strip().upper()[:20] or None
    number = _parse_number(value)
    low = _parse_number(reference_low)
    high = _parse_number(reference_high)
    if number is None or (low is None and high is None):
        return None
    if low is not None and number < low:
        return "L"
    if high is not None and number > high:
        return "H"
    return "N"


def find_oru_message(db: Session, worklist_item_id: uuid.UUID) -> AnalyzerMessage | None:
    messages = list(
        db.scalars(
            select(AnalyzerMessage)
            .where(
                AnalyzerMessage.worklist_item_id == worklist_item_id,
                AnalyzerMessage.direction == "inbound",
            )
            .order_by(AnalyzerMessage.created_at.desc())
        ).all()
    )
    for message in messages:
        if is_result_message(message.body):
            return message
    return None


def normalize_worklist_result(
    db: Session,
    request: Request,
    context: AuthContext,
    worklist_item: AnalyzerWorklistItem,
    *,
    oru_body: str | None = None,
    source_message_id: uuid.UUID | None = None,
) -> LabResult:
    existing = db.scalar(select(LabResult).where(LabResult.worklist_item_id == worklist_item.id))
    if existing and existing.status == "released":
        raise HTTPException(status_code=409, detail="Released results cannot be re-normalized")

    source_message: AnalyzerMessage | None = None
    body = oru_body
    if body is None:
        source_message = find_oru_message(db, worklist_item.id)
        if source_message is None:
            raise HTTPException(status_code=404, detail="No ORU message found for worklist item")
        body = source_message.body
        source_message_id = source_message.id
    elif source_message_id:
        source_message = db.get(AnalyzerMessage, source_message_id)

    raw_observations = extract_oru_observations(body)
    if not raw_observations:
        raise HTTPException(status_code=422, detail="ORU message contains no OBX observations")

    param_maps = {
        mapping.machine_parameter_code.upper(): mapping
        for mapping in db.scalars(
            select(AnalyzerParameterMapping).where(
                AnalyzerParameterMapping.test_mapping_id == worklist_item.mapping_id
            )
        ).all()
    }
    catalog_params = {
        parameter.external_code.upper(): parameter
        for parameter in db.scalars(
            select(TestCatalogParameter).where(
                TestCatalogParameter.test_id == worklist_item.test_id
            )
        ).all()
    }

    if existing:
        result = existing
        result.observations.clear()
        db.flush()
    else:
        result = LabResult(
            organization_id=worklist_item.organization_id,
            branch_id=worklist_item.branch_id,
            worklist_item_id=worklist_item.id,
            specimen_id=worklist_item.specimen_id,
            order_id=worklist_item.order_id,
            test_id=worklist_item.test_id,
            analyzer_id=worklist_item.analyzer_id,
            correlation_id=worklist_item.correlation_id,
            created_by=context.user_id,
        )
        db.add(result)

    result.source_message_id = source_message_id
    result.status = "pending_review"
    result.technical_reviewed_by = None
    result.technical_reviewed_at = None
    result.technical_review_notes = None
    result.pathologist_validated_by = None
    result.pathologist_validated_at = None
    result.pathologist_notes = None
    result.released_by = None
    result.released_at = None
    result.report_number = None
    db.flush()

    for index, raw in enumerate(raw_observations, start=1):
        code = (raw.get("observation_code") or "").upper()
        mapping = param_maps.get(code)
        catalog = None
        if mapping:
            catalog = db.get(TestCatalogParameter, mapping.parameter_id)
        if catalog is None:
            catalog = catalog_params.get(code)
        unit = (
            (mapping.unit if mapping and mapping.unit else None)
            or (catalog.unit if catalog else None)
            or (raw.get("unit") or None)
        )
        reference_low = catalog.reference_low if catalog else None
        reference_high = catalog.reference_high if catalog else None
        reference_text = catalog.reference_text if catalog else None
        value = raw.get("value") or ""
        observation = LabResultObservation(
            result_id=result.id,
            sequence_no=int(raw.get("sequence") or index),
            parameter_id=catalog.id if catalog else None,
            machine_parameter_code=code or f"OBS{index}",
            parameter_name=(catalog.name if catalog else None)
            or raw.get("observation_name")
            or code
            or f"Observation {index}",
            value=value,
            unit=unit,
            reference_low=reference_low,
            reference_high=reference_high,
            reference_text=reference_text,
            flag=compute_flag(
                value,
                reference_low=reference_low,
                reference_high=reference_high,
                analyzer_flags=raw.get("abnormal_flags"),
            ),
            raw_obx=str(raw),
        )
        db.add(observation)

    worklist_item.status = "normalized"
    worklist_item.updated_by = context.user_id
    db.flush()

    record_event(
        db,
        request,
        context,
        event_type="lab_result.normalized",
        entity_type="lab_result",
        entity_id=result.id,
        branch_id=result.branch_id,
        action="normalize",
        new={
            "status": result.status,
            "worklist_item_id": str(worklist_item.id),
            "observation_count": len(raw_observations),
            "source_message_id": str(source_message_id) if source_message_id else None,
        },
    )
    return result


def technical_review(
    db: Session,
    request: Request,
    context: AuthContext,
    result: LabResult,
    *,
    notes: str | None,
) -> LabResult:
    if result.status not in {"pending_review", "technically_reviewed"}:
        raise HTTPException(
            status_code=409,
            detail="Only pending or technically reviewed results can be technically reviewed",
        )
    result.status = "technically_reviewed"
    result.technical_reviewed_by = context.user_id
    result.technical_reviewed_at = datetime.now(UTC)
    result.technical_review_notes = notes
    record_event(
        db,
        request,
        context,
        event_type="lab_result.technical_reviewed",
        entity_type="lab_result",
        entity_id=result.id,
        branch_id=result.branch_id,
        action="technical_review",
        new={"status": result.status, "notes": notes},
    )
    return result


def pathologist_validate(
    db: Session,
    request: Request,
    context: AuthContext,
    result: LabResult,
    *,
    notes: str | None,
) -> LabResult:
    if result.status not in {"technically_reviewed", "pathologist_validated"}:
        raise HTTPException(
            status_code=409,
            detail="Result must be technically reviewed before pathologist validation",
        )
    result.status = "pathologist_validated"
    result.pathologist_validated_by = context.user_id
    result.pathologist_validated_at = datetime.now(UTC)
    result.pathologist_notes = notes
    record_event(
        db,
        request,
        context,
        event_type="lab_result.pathologist_validated",
        entity_type="lab_result",
        entity_id=result.id,
        branch_id=result.branch_id,
        action="pathologist_validate",
        new={"status": result.status, "notes": notes},
    )
    return result


def release_result(
    db: Session,
    request: Request,
    context: AuthContext,
    result: LabResult,
) -> LabResult:
    if result.status not in {"pathologist_validated", "released"}:
        raise HTTPException(
            status_code=409,
            detail="Result must be pathologist validated before release",
        )
    if result.status != "released":
        stamp = datetime.now(UTC)
        result.status = "released"
        result.released_by = context.user_id
        result.released_at = stamp
        if not result.report_number:
            stamp_part = stamp.strftime("%Y%m%d%H%M%S")
            result.report_number = f"RPT-{stamp_part}-{str(result.id)[:6].upper()}"
        worklist_item = db.get(AnalyzerWorklistItem, result.worklist_item_id)
        if worklist_item:
            worklist_item.status = "released"
            worklist_item.updated_by = context.user_id
        record_event(
            db,
            request,
            context,
            event_type="lab_result.released",
            entity_type="lab_result",
            entity_id=result.id,
            branch_id=result.branch_id,
            action="release",
            new={"status": result.status, "report_number": result.report_number},
        )
    return result


def build_result_pdf(db: Session, result: LabResult) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    specimen = db.get(Specimen, result.specimen_id)
    order = db.get(LabOrder, result.order_id)
    test = db.get(TestCatalogItem, result.test_id)
    patient = db.get(Patient, order.patient_id) if order else None

    def line(text: str, height: float = 8) -> None:
        pdf.cell(0, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    line("LaboraIQ Laboratory Report", 10)
    pdf.set_font("Helvetica", size=11)
    line(f"Report: {result.report_number or 'DRAFT'}")
    line(f"Status: {result.status}")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    line("Patient / Specimen")
    pdf.set_font("Helvetica", size=11)
    line(f"Patient: {patient.full_name if patient else 'Unknown'}", 7)
    line(f"Patient no: {patient.patient_number if patient else 'Unknown'}", 7)
    line(f"Order: {order.order_number if order else 'Unknown'}", 7)
    line(f"Barcode: {specimen.barcode if specimen else 'Unknown'}", 7)
    accession = "-"
    if specimen and specimen.accession_number:
        accession = specimen.accession_number
    line(f"Accession: {accession}", 7)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    line(f"Test: {test.code if test else ''} - {test.name if test else ''}")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(55, 8, "Parameter", border=1)
    pdf.cell(30, 8, "Value", border=1)
    pdf.cell(25, 8, "Unit", border=1)
    pdf.cell(25, 8, "Flag", border=1)
    pdf.cell(55, 8, "Reference", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=10)
    for observation in sorted(result.observations, key=lambda item: item.sequence_no):
        reference = observation.reference_text or ""
        if not reference and (observation.reference_low or observation.reference_high):
            reference = f"{observation.reference_low or ''} - {observation.reference_high or ''}"
        pdf.cell(55, 8, observation.parameter_name[:28], border=1)
        pdf.cell(30, 8, observation.value[:14], border=1)
        pdf.cell(25, 8, (observation.unit or "-")[:10], border=1)
        pdf.cell(25, 8, (observation.flag or "-")[:8], border=1)
        pdf.cell(55, 8, reference[:28], border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(8)
    pdf.set_font("Helvetica", size=10)
    if result.technical_reviewed_at:
        tech_note = result.technical_review_notes or ""
        line(f"Technical review: {result.technical_reviewed_at.isoformat()} {tech_note}", 6)
    if result.pathologist_validated_at:
        path_note = result.pathologist_notes or ""
        line(
            f"Pathologist validation: {result.pathologist_validated_at.isoformat()} {path_note}",
            6,
        )
    if result.released_at:
        line(f"Released: {result.released_at.isoformat()}", 6)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        5,
        "Not for clinical use until validation, security hardening, "
        "and regulatory documentation are complete.",
    )

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()

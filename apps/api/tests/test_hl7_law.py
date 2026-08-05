"""Unit tests for HL7 LAW / MLLP helpers."""

from __future__ import annotations

from app.hl7_law import (
    build_ack,
    build_oml_o33,
    build_oru_r01,
    extract_order_fields,
    is_result_message,
    parse_ack,
    unwrap_mllp,
    wrap_mllp,
)


def test_mllp_round_trip() -> None:
    message = "MSH|^~\\&|LaboraIQ|LAB||||OML^O33|1|P|2.5.1\rPID|1"
    framed = wrap_mllp(message)
    assert framed.startswith(b"\x0b")
    assert framed.endswith(b"\x1c\x0d")
    assert unwrap_mllp(framed) == [message.replace("\n", "\r").rstrip("\r")]


def test_build_oml_and_extract_fields() -> None:
    order = build_oml_o33(
        analyzer_code="MAC-UAT-01",
        barcode="LQ0805063919C2AA0601",
        accession="ACC-1",
        machine_test_code="A4",
        test_name="Androstenedione Test",
        patient_number="PT-1",
        patient_name="UAT Patient One",
        patient_sex="Female",
        order_number="ORD-1",
        correlation_id="corr-123",
        message_control_id="MSG001",
    )
    assert "OML^O33^OML_O33" in order
    barcode, test_code = extract_order_fields(order)
    assert barcode == "LQ0805063919C2AA0601"
    assert test_code == "A4"


def test_parse_ack_aa_and_ae() -> None:
    aa = build_ack(ack_code="AA", message_control_id="MSG001", text="ok")
    parsed = parse_ack(aa)
    assert parsed.ok is True
    assert parsed.code == "AA"

    ae = build_ack(ack_code="AE", message_control_id="MSG001", text="bad barcode")
    parsed_ae = parse_ack(ae)
    assert parsed_ae.ok is False
    assert parsed_ae.code == "AE"
    assert "bad barcode" in parsed_ae.text


def test_oru_detected_as_result() -> None:
    oru = build_oru_r01(
        analyzer_code="MAC-UAT-01",
        barcode="LQ1",
        machine_test_code="A4",
        test_name="Androstenedione",
        observation_code="ANDRO",
        observation_name="Androstenedione",
        value="1.8",
        unit="ng/mL",
        message_control_id="R1",
    )
    assert is_result_message(oru) is True
    assert is_result_message(build_ack(ack_code="AA", message_control_id="1", text="ok")) is False

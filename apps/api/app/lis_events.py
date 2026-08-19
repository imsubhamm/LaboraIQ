"""Helpers for LIS-facing operational HL7 messages.

Phase 3 covers specimen status/storage events and aliquot/sorting request
generation for middleware-style integrations.
"""

from __future__ import annotations

import socket
import re
from dataclasses import dataclass

from app.hl7_law import SEGMENT_SEP, escape_hl7, hl7_timestamp, parse_ack, read_mllp_messages, wrap_mllp


@dataclass(frozen=True)
class RoutingCode:
    code: str
    category: str  # routine | aliquot | sorting


def _msh(message_type: str, control_id: str) -> str:
    ts = hl7_timestamp()
    return f"MSH|^~\\&|LaboraIQ|LAB|||{ts}||{message_type}|{escape_hl7(control_id)}|P|2.4|||AL|NE"


def build_status_dispatch_messages(
    *,
    barcode: str,
    module_id: str,
    control_id: str,
    status_code: str = "I",
    event_code: str = "ARRIV",
    event_value: str = "1",
) -> list[tuple[str, str]]:
    return [
        (
            "SSU^U03",
            SEGMENT_SEP.join(
                [
                    _msh("SSU^U03", control_id),
                    f"EQU|{escape_hl7(module_id)}|{hl7_timestamp()}",
                    f"SAC|||{escape_hl7(barcode)}||||{hl7_timestamp()}|{escape_hl7(status_code)}",
                ]
            ),
        ),
        (
            "ORU^R01",
            SEGMENT_SEP.join(
                [
                    _msh("ORU^R01", f"{control_id}-RESULT"),
                    f"ORC|RE|{escape_hl7(barcode)}|||||^^^^^R|||||",
                    f"OBR|1|{escape_hl7(barcode)}|||||||^||||||^^^^^^P|||{escape_hl7(module_id)}||^^|||||||^^^^^|||||||||||||||||",
                    f"OBX|1|NM|{escape_hl7(event_code)}||{escape_hl7(event_value)}|||||||||{hl7_timestamp()}||||{escape_hl7(module_id)}|{hl7_timestamp()}",
                ]
            ),
        ),
    ]


def build_storage_dispatch_messages(
    *,
    barcode: str,
    module_id: str,
    rack_id: str,
    position: str,
    carrier_type: str,
    control_id: str,
) -> list[tuple[str, str]]:
    return [
        (
            "SSU^U03",
            SEGMENT_SEP.join(
                [
                    _msh("SSU^U03", control_id),
                    f"EQU|{escape_hl7(module_id)}|{hl7_timestamp()}",
                    f"SAC|||{escape_hl7(barcode)}||||{hl7_timestamp()}|R|{escape_hl7(carrier_type)}|{escape_hl7(rack_id)}|A^{escape_hl7(position)}",
                ]
            ),
        ),
        (
            "ORU^R01",
            SEGMENT_SEP.join(
                [
                    _msh("ORU^R01", f"{control_id}-RESULT"),
                    f"ORC|RE|{escape_hl7(barcode)}|||||^^^^^R|||||",
                    f"OBR|1|{escape_hl7(barcode)}|||||||^||||||^^^^^^P|||{escape_hl7(module_id)}||^^|||||||^^^^^R|||||||||||||||||",
                    f"OBX|1|NM|SRACK||{escape_hl7(rack_id)}|||||||||{hl7_timestamp()}||||{escape_hl7(module_id)}|{hl7_timestamp()}",
                    f"OBX|2|NM|SPOS||{escape_hl7(position)}|||||||||{hl7_timestamp()}||||{escape_hl7(module_id)}|{hl7_timestamp()}",
                ]
            ),
        ),
    ]


def classify_routing_code(code: str) -> str:
    if re.fullmatch(r"AT\d{2,3}", code.upper()):
        return "aliquot"
    if re.fullmatch(r"SORT\d{2}", code.upper()):
        return "sorting"
    return "routine"


def build_routing_plan(machine_test_codes: list[str]) -> list[RoutingCode]:
    seen: set[str] = set()
    plan: list[RoutingCode] = []
    for code in machine_test_codes:
        cleaned = code.strip().upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        plan.append(RoutingCode(code=cleaned, category=classify_routing_code(cleaned)))
    return plan


def build_routing_order_message(
    *,
    barcode: str,
    patient_number: str,
    patient_name: str,
    fluid: str,
    ordering_physician: str,
    control_id: str,
    routing_codes: list[RoutingCode],
) -> str:
    segments = [
        _msh("ORU^R01", control_id),
        f"PID|1|{escape_hl7(patient_number)}||{escape_hl7(patient_name)}",
        "PV1|1||^^^^^^Ward||||||||||||||||||||||||||||||||||||",
        f"ORC|XE|{escape_hl7(barcode)}|||||^^^^^R||||||||||||",
    ]
    for index, item in enumerate(routing_codes, start=1):
        segments.append(
            f"OBR|{index}|{escape_hl7(barcode)}||{escape_hl7(item.code)}|R||{hl7_timestamp()}|||^^^^^^|A||||{escape_hl7(fluid)}^^^|{escape_hl7(ordering_physician)}|||||||||||||||||||||||||||"
        )
    return SEGMENT_SEP.join(segments)


def send_lis_message_over_tcp(
    *,
    host: str,
    port: int,
    payload: str,
    use_mllp: bool,
    timeout_seconds: float,
) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as connection:
            outbound = wrap_mllp(payload) if use_mllp else payload.encode("utf-8")
            connection.sendall(outbound)
            connection.settimeout(timeout_seconds)
            if not use_mllp:
                return True, "TCP delivered"
            responses = read_mllp_messages(
                connection.recv,
                timeout_seconds=timeout_seconds,
                max_messages=1,
                idle_rounds=1,
            )
            if not responses:
                return False, "No LIS ACK received"
            ack = parse_ack(responses[0])
            if ack.ok:
                return True, f"ACK {ack.code}"
            return False, f"NAK {ack.code}: {ack.text}"
    except OSError as error:
        return False, (str(error)[:500] or error.__class__.__name__)

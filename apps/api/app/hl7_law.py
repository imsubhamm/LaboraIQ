"""HL7 v2.5.1 / IHE LAW helpers for analyzer order exchange (MLLP + OML/ACK/ORU).

This is a focused UAT implementation: enough structure for barcode + machine test
code routing, MSA acknowledgement, and raw ORU result capture. Full LAW profile
conformance and result normalization belong in later phases.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"
SEGMENT_SEP = "\r"


def hl7_timestamp(moment: datetime | None = None) -> str:
    value = moment or datetime.now(UTC)
    return value.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def escape_hl7(value: str) -> str:
    return (
        value.replace("\\", "\\E\\")
        .replace("|", "\\F\\")
        .replace("^", "\\S\\")
        .replace("&", "\\T\\")
        .replace("~", "\\R\\")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def wrap_mllp(message: str) -> bytes:
    body = message.replace("\n", "\r")
    if not body.endswith("\r"):
        body += "\r"
    return MLLP_START + body.encode("utf-8") + MLLP_END


def unwrap_mllp(payload: bytes) -> list[str]:
    """Extract complete MLLP-framed HL7 messages from a byte buffer."""
    messages: list[str] = []
    remaining = payload
    while True:
        start = remaining.find(MLLP_START)
        if start < 0:
            break
        end = remaining.find(MLLP_END, start + 1)
        if end < 0:
            break
        raw = remaining[start + 1 : end]
        messages.append(raw.decode("utf-8", errors="replace").replace("\n", "\r").strip("\r"))
        remaining = remaining[end + len(MLLP_END) :]
    return messages


def read_mllp_messages(
    receive: Callable[[int], bytes],
    *,
    timeout_seconds: float,
    max_messages: int = 2,
    idle_rounds: int = 1,
) -> list[str]:
    """Read from a socket-like object until one or more complete MLLP frames arrive.

    `receive` is a callable taking a buffer size and returning bytes (e.g. sock.recv).
    After the first frame, keeps reading briefly so a follow-up ORU can arrive.
    """
    del timeout_seconds  # timeout is enforced by the socket; kept for call-site clarity
    buffer = bytearray()
    quiet_rounds = 0
    seen_message = False
    while quiet_rounds < idle_rounds or not seen_message:
        try:
            chunk = receive(4096)
        except TimeoutError:
            messages = unwrap_mllp(bytes(buffer))
            if len(messages) >= max_messages:
                return messages[:max_messages]
            if messages:
                seen_message = True
                quiet_rounds += 1
                continue
            quiet_rounds += 1
            if quiet_rounds >= idle_rounds and not seen_message:
                break
            continue
        except OSError:
            break
        if not chunk:
            break
        buffer.extend(chunk)
        messages = unwrap_mllp(bytes(buffer))
        if messages:
            seen_message = True
        if len(messages) >= max_messages:
            return messages[:max_messages]
        quiet_rounds = 0
    return unwrap_mllp(bytes(buffer))


def segment_map(message: str) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for line in message.replace("\n", "\r").split("\r"):
        if not line:
            continue
        name = line.split("|", 1)[0]
        mapped.setdefault(name, []).append(line)
    return mapped


def field(segment: str, index: int) -> str:
    """1-based HL7 field index (MSH-1 is '|', MSH-2 is '^~\\&', MSH-9 is message type)."""
    parts = segment.split("|")
    if segment.startswith("MSH"):
        # MSH splits oddly: parts[0]=MSH, parts[1]=^~\&, parts[2]=sending app, ...
        # Field N for MSH is parts[N-1] for N>=2, with field 1 being the separator.
        if index == 1:
            return "|"
        if index - 1 < len(parts):
            return parts[index - 1]
        return ""
    if index < len(parts):
        return parts[index]
    return ""


def component(value: str, index: int) -> str:
    parts = value.split("^")
    if 0 <= index < len(parts):
        return parts[index]
    return ""


@dataclass(frozen=True)
class AckResult:
    ok: bool
    code: str
    text: str
    message_control_id: str


def parse_ack(message: str) -> AckResult:
    segments = segment_map(message)
    msa_lines = segments.get("MSA", [])
    msh_lines = segments.get("MSH", [])
    if not msa_lines:
        return AckResult(ok=False, code="", text="ACK missing MSA segment", message_control_id="")
    msa = msa_lines[0]
    code = field(msa, 1).upper()
    control_id = field(msa, 2)
    text = field(msa, 3) or field(msh_lines[0], 9) if msh_lines else field(msa, 3)
    ok = code in {"AA", "CA"}
    return AckResult(ok=ok, code=code or "??", text=text or code, message_control_id=control_id)


def message_type(message: str) -> str:
    msh = segment_map(message).get("MSH", [""])[0]
    return field(msh, 9)


def is_result_message(message: str) -> bool:
    msg_type = message_type(message).upper()
    return msg_type.startswith("ORU")


def extract_order_fields(message: str) -> tuple[str | None, str | None]:
    """Return (barcode, machine_test_code) from a received OML/ORM order."""
    segments = segment_map(message)
    barcode: str | None = None
    test_code: str | None = None
    for spm in segments.get("SPM", []):
        # SPM-2 placer / SPM-3 filler often carry specimen id; SPM-11 can too.
        candidate = component(field(spm, 2), 0) or component(field(spm, 3), 0)
        if candidate:
            barcode = candidate
            break
    if barcode is None:
        for sac in segments.get("SAC", []):
            candidate = component(field(sac, 3), 0)
            if candidate:
                barcode = candidate
                break
    for obr in segments.get("OBR", []):
        candidate = component(field(obr, 4), 0)
        if candidate:
            test_code = candidate
            break
    return barcode, test_code


def build_oml_o33(
    *,
    analyzer_code: str,
    barcode: str,
    accession: str | None,
    machine_test_code: str,
    test_name: str,
    patient_number: str,
    patient_name: str,
    patient_sex: str | None,
    order_number: str,
    correlation_id: str,
    message_control_id: str | None = None,
) -> str:
    control_id = message_control_id or correlation_id.replace("-", "")[:20]
    ts = hl7_timestamp()
    name = escape_hl7(patient_name)
    # PID-5 uses family^given; keep full name in family for UAT simplicity.
    sex = (patient_sex or "U")[:1].upper()
    if sex not in {"M", "F", "O", "U"}:
        sex = "U"
    accession_value = escape_hl7(accession or barcode)
    segments = [
        (
            f"MSH|^~\\&|LaboraIQ|LAB|{escape_hl7(analyzer_code)}|ANALYZER|{ts}"
            f"||OML^O33^OML_O33|{escape_hl7(control_id)}|P|2.5.1"
        ),
        f"PID|1||{escape_hl7(patient_number)}||{name}|||{sex}",
        (f"SPM|1|{escape_hl7(barcode)}^{escape_hl7(barcode)}||{accession_value}^LAB|||||"),
        f"ORC|NW|{escape_hl7(order_number)}|{escape_hl7(control_id)}|||||{ts}",
        (
            f"OBR|1|{escape_hl7(order_number)}|{escape_hl7(control_id)}|"
            f"{escape_hl7(machine_test_code)}^{escape_hl7(test_name)}^L"
        ),
        f"NTE|1||correlation_id={escape_hl7(correlation_id)}",
    ]
    return SEGMENT_SEP.join(segments)


def build_ack(
    *,
    ack_code: str,
    message_control_id: str,
    text: str,
    analyzer_code: str = "SIMULATOR",
) -> str:
    ts = hl7_timestamp()
    control = escape_hl7(message_control_id or "UNKNOWN")
    return SEGMENT_SEP.join(
        [
            (
                f"MSH|^~\\&|{escape_hl7(analyzer_code)}|ANALYZER|LaboraIQ|LAB|{ts}"
                f"||ACK^O33^ACK|{control}|P|2.5.1"
            ),
            f"MSA|{ack_code}|{control}|{escape_hl7(text)}",
        ]
    )


def build_oru_r01(
    *,
    analyzer_code: str,
    barcode: str,
    machine_test_code: str,
    test_name: str,
    observation_code: str,
    observation_name: str,
    value: str,
    unit: str,
    message_control_id: str,
    patient_number: str = "UNKNOWN",
    patient_name: str = "UAT^Patient",
) -> str:
    ts = hl7_timestamp()
    control = escape_hl7(message_control_id)
    return SEGMENT_SEP.join(
        [
            (
                f"MSH|^~\\&|{escape_hl7(analyzer_code)}|ANALYZER|LaboraIQ|LAB|{ts}"
                f"||ORU^R01^ORU_R01|{control}|P|2.5.1"
            ),
            f"PID|1||{escape_hl7(patient_number)}||{escape_hl7(patient_name)}",
            f"OBR|1|{control}|{control}|{escape_hl7(machine_test_code)}^{escape_hl7(test_name)}^L",
            (
                f"OBX|1|NM|{escape_hl7(observation_code)}^{escape_hl7(observation_name)}^L||"
                f"{escape_hl7(value)}|{escape_hl7(unit)}|||||F|||{ts}"
            ),
            f"SPM|1|{escape_hl7(barcode)}^{escape_hl7(barcode)}",
        ]
    )

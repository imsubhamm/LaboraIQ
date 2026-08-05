"""LaboraIQ Mac analyzer simulator: MLLP HL7 LAW order / ACK / ORU exchange.

Accepts OML^O33 (or stub LABORAIQ-ORDER-V0), validates barcode + machine test code
when provided, returns ACK^O33, and optionally sends a synthetic ORU^R01 result.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from pathlib import Path

# Allow importing apps/api HL7 helpers when run from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_ROOT = _REPO_ROOT / "apps" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.hl7_law import (  # noqa: E402
    build_ack,
    build_oru_r01,
    extract_order_fields,
    field,
    segment_map,
    unwrap_mllp,
    wrap_mllp,
)

MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"


def _read_frame(connection: socket.socket, timeout: float) -> bytes:
    connection.settimeout(timeout)
    buffer = bytearray()
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        buffer.extend(chunk)
        if MLLP_START in buffer and MLLP_END in buffer[buffer.find(MLLP_START) + 1 :]:
            break
        if buffer.startswith(b"LABORAIQ-ORDER-V0") and b"END" in buffer:
            break
    return bytes(buffer)


def _parse_stub(payload: bytes) -> tuple[str | None, str | None, str]:
    text = payload.decode("utf-8", errors="replace")
    barcode = None
    test_code = None
    correlation = "SIM"
    for line in text.splitlines():
        if line.startswith("barcode="):
            barcode = line.split("=", 1)[1].strip()
        elif line.startswith("machine_test_code="):
            test_code = line.split("=", 1)[1].strip()
        elif line.startswith("correlation_id="):
            correlation = line.split("=", 1)[1].strip()
    return barcode, test_code, correlation


def handle_connection(
    connection: socket.socket,
    *,
    analyzer_code: str,
    expected_barcode: str | None,
    expected_test_code: str | None,
    send_result: bool,
    result_value: str,
    result_unit: str,
    observation_code: str,
    timeout: float,
) -> None:
    try:
        raw = _read_frame(connection, timeout=timeout)
        if not raw:
            return

        messages = unwrap_mllp(raw)
        if messages:
            order = messages[0]
            barcode, test_code = extract_order_fields(order)
            msh = segment_map(order).get("MSH", [""])[0]
            control_id = field(msh, 10) or "UNKNOWN"
            is_hl7 = True
        else:
            barcode, test_code, control_id = _parse_stub(raw)
            is_hl7 = False

        ack_code = "AA"
        ack_text = "Order accepted"
        if expected_barcode and barcode and barcode != expected_barcode:
            ack_code = "AE"
            ack_text = f"Barcode mismatch: got {barcode}"
        if expected_test_code and test_code and test_code != expected_test_code:
            ack_code = "AE"
            ack_text = f"Test code mismatch: got {test_code}"

        if is_hl7:
            ack = build_ack(
                ack_code=ack_code,
                message_control_id=control_id,
                text=ack_text,
                analyzer_code=analyzer_code,
            )
            connection.sendall(wrap_mllp(ack))
            if ack_code == "AA" and send_result and barcode and test_code:
                oru = build_oru_r01(
                    analyzer_code=analyzer_code,
                    barcode=barcode,
                    machine_test_code=test_code,
                    test_name="Androstenedione",
                    observation_code=observation_code,
                    observation_name="Androstenedione",
                    value=result_value,
                    unit=result_unit,
                    message_control_id=f"R{control_id}"[:20],
                )
                connection.sendall(wrap_mllp(oru))
        else:
            # Stub path: plain ACK line for Phase 2 compatibility.
            connection.sendall(f"ACK|{ack_code}|{ack_text}\n".encode())
    except OSError as error:
        print(f"connection error: {error}", file=sys.stderr)
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--analyzer-code", default="MAC-UAT-01")
    parser.add_argument("--expected-barcode", default=None)
    parser.add_argument("--expected-test-code", default="A4")
    parser.add_argument("--send-result", action="store_true", default=True)
    parser.add_argument("--no-result", action="store_true", help="ACK only, no ORU")
    parser.add_argument("--result-value", default="1.8")
    parser.add_argument("--result-unit", default="ng/mL")
    parser.add_argument("--observation-code", default="ANDRO")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    send_result = not args.no_result

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen()
        print(
            f"LaboraIQ analyzer simulator listening on {args.host}:{args.port} "
            f"(expected test={args.expected_test_code}, send_result={send_result})",
            flush=True,
        )
        while True:
            connection, address = server.accept()
            print(f"accepted {address[0]}:{address[1]}", flush=True)
            thread = threading.Thread(
                target=handle_connection,
                kwargs={
                    "connection": connection,
                    "analyzer_code": args.analyzer_code,
                    "expected_barcode": args.expected_barcode,
                    "expected_test_code": args.expected_test_code,
                    "send_result": send_result,
                    "result_value": args.result_value,
                    "result_unit": args.result_unit,
                    "observation_code": args.observation_code,
                    "timeout": args.timeout,
                },
                daemon=True,
            )
            thread.start()


if __name__ == "__main__":
    main()

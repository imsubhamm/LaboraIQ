"""Phase 4 UAT smoke runner for LaboraIQ.

Exercises the happy path against a running API:
health -> readiness -> intake -> payment -> specimen workflow -> analyzer queue
-> optional LIS operational messages -> result review -> release -> PDF fetch.

This script assumes:
- development auth header is accepted, or the endpoint is otherwise reachable
- the requested test already exists in test master
- an active analyzer mapping exists for the chosen test
- the analyzer endpoint/simulator is reachable when order processing runs
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class ApiClient:
    def __init__(self, base_url: str, dev_auth_email: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.dev_auth_email = dev_auth_email

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        body: dict | None = None,
        expect_json: bool = True,
    ):
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
        headers = {"Accept": "application/json"}
        if self.dev_auth_email:
            headers["X-Dev-User-Email"] = self.dev_auth_email
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                if not expect_json:
                    return payload, dict(response.headers)
                if not payload:
                    return {}
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {error.code} {detail}") from error

    def get(self, path: str, *, params: dict[str, str | int] | None = None):
        return self._request("GET", path, params=params)

    def post(self, path: str, *, body: dict | None = None, params: dict[str, str | int] | None = None):
        return self._request("POST", path, params=params, body=body)

    def get_bytes(self, path: str):
        return self._request("GET", path, expect_json=False)


def require_one(items: list[dict], *, label: str, predicate) -> dict:
    for item in items:
        if predicate(item):
            return item
    raise RuntimeError(f"{label} was not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--dev-auth-email", default="admin@dev.labora.local")
    parser.add_argument("--test-code", default="BIO0231")
    parser.add_argument("--payment-method", default="CASH")
    parser.add_argument("--phase3", action="store_true", help="Generate Phase 3 LIS messages too")
    parser.add_argument(
        "--process-lis-outbox",
        action="store_true",
        help="Process LIS outbox after generating status/storage/routing messages",
    )
    parser.add_argument("--rack-id", default="RACK-07")
    parser.add_argument("--rack-position", default="12")
    args = parser.parse_args()

    client = ApiClient(args.api_base_url, args.dev_auth_email)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = random.randint(1000, 9999)
    phone = f"+9198111{suffix:04d}"
    email = f"phase4-{stamp}-{suffix}@example.com"

    print("== Connectivity ==", flush=True)
    print(client.get("/health"), flush=True)
    print(client.get("/ready"), flush=True)
    print(client.get("/auth/me"), flush=True)

    print("\n== Resolve test ==", flush=True)
    tests = client.get("/test-master", params={"search": args.test_code, "limit": 25})
    test = require_one(
        tests["items"],
        label=f"test {args.test_code}",
        predicate=lambda item: item["code"].upper() == args.test_code.upper(),
    )
    print(f"Using test {test['code']} / {test['name']} ({test['id']})", flush=True)

    print("\n== Create intake ==", flush=True)
    intake = client.post(
        "/intake-workflows",
        body={
            "full_name": f"Phase4 Smoke {stamp}",
            "phone": phone,
            "email": email,
            "age_years": 30,
            "sex": "Female",
            "blood_group": "A+",
            "country": "India",
            "race": "Asian",
            "nationality": "Indian",
            "visit_type": "OP",
            "department": "Medicine",
            "ward": "OP Clinic",
            "doctor_name": "Dr Smoke",
            "diagnosis": "Z00.0",
            "test_ids": [test["id"]],
        },
    )
    print(intake, flush=True)

    print("\n== Record payment ==", flush=True)
    payment = client.post(
        f"/orders/{intake['order_id']}/payment",
        body={"payment_method": args.payment_method},
    )
    barcode = payment["specimens"][0]["barcode"]
    print(f"Barcode: {barcode}", flush=True)

    print("\n== Specimen workflow ==", flush=True)
    print(
        client.post(
            f"/specimens/{barcode}/collect",
            body={"collection_location": "OP", "container_count": 1},
        )["status"],
        flush=True,
    )
    print(client.post(f"/specimens/{barcode}/receive")["status"], flush=True)
    print(client.post(f"/specimens/{barcode}/decision", body={"decision": "accept"})["status"], flush=True)

    print("\n== Analyzer queue ==", flush=True)
    worklist = client.get("/analyzer-worklist", params={"status": "pending", "limit": 100})
    item = require_one(
        worklist["items"],
        label=f"pending worklist item for {barcode}",
        predicate=lambda row: row["specimen_barcode"] == barcode,
    )
    print(f"Worklist item {item['id']} -> {item['machine_test_code']}", flush=True)
    print(client.post(f"/analyzer-worklist/{item['id']}/enqueue")["status"], flush=True)
    processed = client.post("/analyzer-orders/process", params={"limit": 20})
    print(processed, flush=True)

    if args.phase3:
        print("\n== LIS operational messages ==", flush=True)
        status_rows = client.post(
            f"/specimens/{barcode}/lis-status",
            body={"module_id": "90", "event_code": "ARRIV", "event_value": "1"},
        )
        storage_rows = client.post(
            f"/specimens/{barcode}/lis-storage",
            body={
                "module_id": "90",
                "rack_id": args.rack_id,
                "position": args.rack_position,
                "carrier_type": "ESFlex80pos",
            },
        )
        routing_row = client.post(f"/specimens/{barcode}/lis-routing-message")
        print(f"status messages: {len(status_rows)}", flush=True)
        print(f"storage messages: {len(storage_rows)}", flush=True)
        print(f"routing message: {routing_row['id']}", flush=True)
        if args.process_lis_outbox:
            outbox = client.post("/lis-messages/process", params={"limit": 50})
            print(outbox, flush=True)

    print("\n== Result workflow ==", flush=True)
    results = client.get("/results", params={"status": "pending_review", "limit": 100})
    result = require_one(
        results["items"],
        label=f"pending result for {barcode}",
        predicate=lambda row: row["specimen_barcode"] == barcode,
    )
    print(f"Result {result['id']} observations={len(result['observations'])}", flush=True)
    reviewed = client.post(
        f"/results/{result['id']}/technical-review",
        body={"notes": "Phase 4 smoke review"},
    )
    validated = client.post(
        f"/results/{result['id']}/pathologist-validate",
        body={"notes": "Phase 4 smoke approval"},
    )
    released = client.post(f"/results/{result['id']}/release")
    pdf_bytes, pdf_headers = client.get_bytes(f"/results/{result['id']}/pdf")
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("Result PDF did not start with %PDF")

    print(reviewed["status"], flush=True)
    print(validated["status"], flush=True)
    print(released["status"], flush=True)
    print(f"PDF content-type: {pdf_headers.get('Content-Type', '')}", flush=True)

    print("\nSmoke run completed successfully.", flush=True)
    print(
        json.dumps(
            {
                "order_id": intake["order_id"],
                "order_number": intake["order_number"],
                "barcode": barcode,
                "worklist_item_id": item["id"],
                "result_id": result["id"],
                "report_number": released["report_number"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

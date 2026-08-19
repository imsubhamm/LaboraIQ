"""One-command local Phase 4 drill.

Starts the analyzer TCP simulator, runs the Phase 4 UAT smoke script, then
shuts down the simulator. Useful for repeatable local rehearsal.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def wait_for_startup(process: subprocess.Popen[str], timeout_seconds: float = 5.0) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if process.poll() is not None:
            raise RuntimeError("Simulator exited before startup completed")
        time.sleep(0.1)


def api_get(base_url: str, path: str, *, dev_auth_email: str):
    headers = {"Accept": "application/json", "X-Dev-User-Email": dev_auth_email}
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"API preflight failed for {path}: {error}") from error


def preflight_checks(
    *,
    base_url: str,
    dev_auth_email: str,
    analyzer_code: str,
    expected_test_code: str,
    sim_host: str,
    sim_port: int,
) -> None:
    health = api_get(base_url, "/health", dev_auth_email=dev_auth_email)
    if health.get("status") != "ok":
        raise RuntimeError(f"API health check failed: {health}")
    analyzers = api_get(base_url, "/analyzers?limit=100", dev_auth_email=dev_auth_email)["items"]
    analyzer = next((item for item in analyzers if item["code"] == analyzer_code), None)
    if analyzer is None:
        raise RuntimeError(f"Analyzer {analyzer_code} not found")
    if analyzer["host"] != sim_host or int(analyzer["port"]) != sim_port:
        raise RuntimeError(
            f"Analyzer {analyzer_code} points to {analyzer['host']}:{analyzer['port']} "
            f"instead of {sim_host}:{sim_port}"
        )
    mappings = api_get(
        base_url,
        f"/analyzers/{analyzer['id']}/mappings",
        dev_auth_email=dev_auth_email,
    )
    if not any(item["machine_test_code"] == expected_test_code for item in mappings):
        raise RuntimeError(
            f"Analyzer {analyzer_code} has no mapping for machine test code {expected_test_code}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--dev-auth-email", default="admin@dev.labora.local")
    parser.add_argument("--test-code", default="BIO0231")
    parser.add_argument("--sim-host", default="127.0.0.1")
    parser.add_argument("--sim-port", type=int, default=55001)
    parser.add_argument("--analyzer-code", default="MAC-UAT-01")
    parser.add_argument("--expected-test-code", default="A4")
    parser.add_argument("--result-value", default="1.8")
    parser.add_argument("--result-unit", default="ng/mL")
    parser.add_argument("--observation-code", default="ANDRO")
    parser.add_argument("--phase3", action="store_true")
    parser.add_argument("--process-lis-outbox", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    simulator_script = repo_root / "tools" / "analyzer_tcp_simulator.py"
    smoke_script = repo_root / "tools" / "phase4_uat_smoke.py"

    sim_cmd = [
        sys.executable,
        str(simulator_script),
        "--host",
        args.sim_host,
        "--port",
        str(args.sim_port),
        "--analyzer-code",
        args.analyzer_code,
        "--expected-test-code",
        args.expected_test_code,
        "--result-value",
        args.result_value,
        "--result-unit",
        args.result_unit,
        "--observation-code",
        args.observation_code,
    ]
    smoke_cmd = [
        sys.executable,
        str(smoke_script),
        "--api-base-url",
        args.api_base_url,
        "--dev-auth-email",
        args.dev_auth_email,
        "--test-code",
        args.test_code,
    ]
    if args.phase3:
        smoke_cmd.append("--phase3")
    if args.process_lis_outbox:
        smoke_cmd.append("--process-lis-outbox")

    if not args.skip_preflight:
        print("Running preflight checks...", flush=True)
        preflight_checks(
            base_url=args.api_base_url,
            dev_auth_email=args.dev_auth_email,
            analyzer_code=args.analyzer_code,
            expected_test_code=args.expected_test_code,
            sim_host=args.sim_host,
            sim_port=args.sim_port,
        )
        print("Preflight passed.", flush=True)

    print(f"Starting simulator: {shlex.join(sim_cmd)}", flush=True)
    simulator = subprocess.Popen(
        sim_cmd,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_startup(simulator)
        print("Simulator started.", flush=True)
        print(f"Running smoke: {shlex.join(smoke_cmd)}", flush=True)
        completed = subprocess.run(smoke_cmd, cwd=repo_root, check=False)
        return completed.returncode
    finally:
        if simulator.poll() is None:
            simulator.terminate()
            try:
                simulator.wait(timeout=3)
            except subprocess.TimeoutExpired:
                simulator.kill()
        if simulator.stdout is not None:
            output = simulator.stdout.read() or ""
            if output.strip():
                print("\n=== Simulator Output ===", flush=True)
                print(output, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

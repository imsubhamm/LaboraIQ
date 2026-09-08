"""Analyzer machine-health analytics and dashboard API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.analyzer_health import (
    DASHBOARD_QUERY_BATCHES,
    calculate_analyzer_health,
    compute_uptime_intervals,
    percentile,
    ratio,
)
from app.auth import AuthContext
from app.config import get_settings
from app.models import (
    Analyzer,
    AnalyzerConnectionEvent,
    AnalyzerOrderAttempt,
    AnalyzerTestMapping,
    AnalyzerWorklistItem,
    Branch,
    LabOrder,
    LabResult,
    Organization,
    Patient,
    Specimen,
    TestCatalogItem,
    User,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_ratio_and_percentile_edge_cases() -> None:
    assert ratio(1, 0) is None
    assert percentile([], 0.5) is None
    assert percentile([10], 0.95) == 10
    assert percentile([10, 20, 30, 40], 0.5) == 25


def test_uptime_online_then_offline_window() -> None:
    start = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 8, 10, 42, tzinfo=UTC)
    org = uuid4()
    branch = uuid4()
    analyzer = uuid4()
    events = [
        AnalyzerConnectionEvent(
            organization_id=org,
            branch_id=branch,
            analyzer_id=analyzer,
            event_type="heartbeat",
            attempt=1,
            success=True,
            latency_ms=12,
            message="ok",
            correlation_id="c1",
            occurred_at=start,
        ),
        AnalyzerConnectionEvent(
            organization_id=org,
            branch_id=branch,
            analyzer_id=analyzer,
            event_type="heartbeat",
            attempt=1,
            success=False,
            latency_ms=30,
            message="refused",
            correlation_id="c2",
            occurred_at=datetime(2026, 9, 8, 10, 17, tzinfo=UTC),
        ),
        AnalyzerConnectionEvent(
            organization_id=org,
            branch_id=branch,
            analyzer_id=analyzer,
            event_type="heartbeat",
            attempt=1,
            success=True,
            latency_ms=11,
            message="ok",
            correlation_id="c3",
            occurred_at=end,
        ),
    ]
    online, offline, uptime = compute_uptime_intervals(
        events, window_start=start, window_end=end, heartbeat_seconds=3600
    )
    assert round(online / 60) == 17
    assert round(offline / 60) == 25
    assert uptime is not None
    assert abs(uptime - (17 / 42)) < 0.02


def test_health_score_bands_and_reasons() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    healthy = calculate_analyzer_health(
        availability=1,
        order_success=1,
        result_success=1,
        avg_latency_ms=50,
        queue_depth=0,
        connectivity="online",
        settings=settings,
    )
    assert healthy.status == "healthy"
    assert healthy.score >= 90
    degraded = calculate_analyzer_health(
        availability=0.4,
        order_success=0.4,
        result_success=0.4,
        avg_latency_ms=2500,
        queue_depth=25,
        connectivity="online",
        settings=settings,
    )
    assert degraded.status in {"degraded", "critical"}
    assert any("Latency" in reason for reason in degraded.reasons)
    offline = calculate_analyzer_health(
        availability=0,
        order_success=None,
        result_success=None,
        avg_latency_ms=None,
        queue_depth=0,
        connectivity="offline",
        settings=settings,
    )
    assert offline.status == "offline"
    assert "offline" in offline.reasons[0].lower()


def _seed_machine(
    db: Session, context: AuthContext, *, code: str = "HEM-01", vendor: str = "Sysmex"
) -> Analyzer:
    branch = Branch(organization_id=context.organization_id, name="Central", code=f"C-{code}")
    db.add(branch)
    db.flush()
    analyzer = Analyzer(
        organization_id=context.organization_id,
        branch_id=branch.id,
        code=code,
        vendor=vendor,
        model="XN-1000",
        protocol="HL7_LAW",
        host="192.168.10.50",
        port=5000,
        heartbeat_interval_seconds=60,
        created_by=context.user_id,
        updated_by=context.user_id,
    )
    db.add(analyzer)
    db.flush()
    return analyzer


def test_dashboard_empty_never_connected(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    _seed_machine(db, context)
    db.commit()
    response = client.get("/api/v1/analyzer-dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["query_batches"] == DASHBOARD_QUERY_BATCHES
    assert body["summary"]["total_analyzers"] == 1
    assert body["summary"]["offline"] == 1
    assert body["analyzers"][0]["health"]["status"] == "offline"
    assert body["analyzers"][0]["orders"] == 0
    assert body["analyzers"][0]["order_success_percent"] is None
    assert body["analyzers"][0]["avg_latency_ms"] is None
    assert any(alert["type"] == "analyzer_offline" for alert in body["alerts"])


def test_dashboard_connection_success_and_latency(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    analyzer = _seed_machine(db, context)
    now = datetime.now(UTC)
    db.add(
        AnalyzerConnectionEvent(
            organization_id=context.organization_id,
            branch_id=analyzer.branch_id,
            analyzer_id=analyzer.id,
            event_type="heartbeat",
            attempt=1,
            success=True,
            latency_ms=80,
            message="ok",
            correlation_id="ok",
            occurred_at=now,
        )
    )
    db.commit()
    body = client.get("/api/v1/analyzer-dashboard").json()
    row = body["analyzers"][0]
    assert row["connectivity"] == "online"
    assert row["avg_latency_ms"] == 80
    assert body["summary"]["online"] == 1


def test_order_success_retry_queue_and_alerts(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    analyzer = _seed_machine(db, context)
    now = datetime.now(UTC)
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="CBC",
        name="CBC",
        specimen_type="Blood",
        container_type="EDTA",
        price=1,
    )
    patient = Patient(
        organization_id=context.organization_id,
        patient_number="PT-1",
        full_name="Pat",
        phone="9999999999",
    )
    db.add_all([test, patient])
    db.flush()
    order = LabOrder(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        patient_id=patient.id,
        order_number="ORD-1",
        visit_type="OP",
        doctor_name="Dr",
    )
    db.add(order)
    db.flush()
    specimen = Specimen(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        order_id=order.id,
        barcode="LQ1",
        specimen_type="Blood",
        container_type="EDTA",
    )
    db.add(specimen)
    db.flush()
    mapping = AnalyzerTestMapping(
        organization_id=context.organization_id,
        analyzer_id=analyzer.id,
        test_id=test.id,
        machine_test_code="A4",
    )
    db.add(mapping)
    db.flush()
    work = AnalyzerWorklistItem(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        specimen_id=specimen.id,
        order_id=order.id,
        test_id=test.id,
        analyzer_id=analyzer.id,
        mapping_id=mapping.id,
        machine_test_code="A4",
        status="awaiting_result",
        correlation_id="w1",
        created_at=now - timedelta(hours=5),
    )
    db.add(work)
    db.flush()
    db.add_all(
        [
            AnalyzerOrderAttempt(
                organization_id=context.organization_id,
                branch_id=analyzer.branch_id,
                worklist_item_id=work.id,
                analyzer_id=analyzer.id,
                attempt_no=1,
                state="failed",
                correlation_id="a1",
                created_by=context.user_id,
                created_at=now - timedelta(minutes=10),
            ),
            AnalyzerOrderAttempt(
                organization_id=context.organization_id,
                branch_id=analyzer.branch_id,
                worklist_item_id=work.id,
                analyzer_id=analyzer.id,
                attempt_no=2,
                state="failed",
                correlation_id="a2",
                created_by=context.user_id,
                created_at=now - timedelta(minutes=8),
            ),
            AnalyzerOrderAttempt(
                organization_id=context.organization_id,
                branch_id=analyzer.branch_id,
                worklist_item_id=work.id,
                analyzer_id=analyzer.id,
                attempt_no=3,
                state="acknowledged",
                correlation_id="a3",
                created_by=context.user_id,
                created_at=now - timedelta(minutes=5),
            ),
        ]
    )
    db.add(
        AnalyzerConnectionEvent(
            organization_id=context.organization_id,
            branch_id=analyzer.branch_id,
            analyzer_id=analyzer.id,
            event_type="heartbeat",
            attempt=1,
            success=True,
            latency_ms=900,
            message="ok",
            correlation_id="lat",
            occurred_at=now,
        )
    )
    db.commit()
    body = client.get("/api/v1/analyzer-dashboard").json()
    row = body["analyzers"][0]
    assert row["orders"] == 3
    assert row["failed_orders"] == 2
    assert row["order_success_percent"] == 33.33
    assert row["retry_rate"] > 0
    assert row["queue_depth"] == 1
    types = {alert["type"] for alert in body["alerts"]}
    assert "repeated_order_failures" in types
    assert "high_retry_rate" in types
    assert "high_latency" in types
    assert "delayed_results" in types


def test_result_success_and_detail(client: TestClient, db: Session, context: AuthContext) -> None:
    analyzer = _seed_machine(db, context)
    now = datetime.now(UTC)
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="CBC",
        name="CBC",
        specimen_type="Blood",
        container_type="EDTA",
        price=1,
    )
    patient = Patient(
        organization_id=context.organization_id,
        patient_number="PT-2",
        full_name="Pat",
        phone="9999999999",
    )
    db.add_all([test, patient])
    db.flush()
    order = LabOrder(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        patient_id=patient.id,
        order_number="ORD-2",
        visit_type="OP",
        doctor_name="Dr",
    )
    db.add(order)
    db.flush()
    specimen = Specimen(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        order_id=order.id,
        barcode="LQ2",
        specimen_type="Blood",
        container_type="EDTA",
    )
    db.add(specimen)
    db.flush()
    mapping = AnalyzerTestMapping(
        organization_id=context.organization_id,
        analyzer_id=analyzer.id,
        test_id=test.id,
        machine_test_code="A4",
    )
    db.add(mapping)
    db.flush()
    work = AnalyzerWorklistItem(
        organization_id=context.organization_id,
        branch_id=analyzer.branch_id,
        specimen_id=specimen.id,
        order_id=order.id,
        test_id=test.id,
        analyzer_id=analyzer.id,
        mapping_id=mapping.id,
        machine_test_code="A4",
        status="result_received",
        correlation_id="w2",
        created_at=now - timedelta(minutes=30),
    )
    db.add(work)
    db.flush()
    db.add(
        LabResult(
            organization_id=context.organization_id,
            branch_id=analyzer.branch_id,
            worklist_item_id=work.id,
            specimen_id=specimen.id,
            order_id=order.id,
            test_id=test.id,
            analyzer_id=analyzer.id,
            correlation_id="r1",
            status="released",
            created_at=now - timedelta(minutes=10),
            released_at=now,
        )
    )
    db.commit()
    listing = client.get("/api/v1/analyzer-dashboard").json()
    assert listing["analyzers"][0]["result_success_percent"] == 100
    assert listing["detail"] is None
    detail = client.get(f"/api/v1/analyzer-dashboard?analyzer_id={analyzer.id}").json()
    assert detail["detail"]["results_received"] == 1
    assert detail["detail"]["health"]["score"] is not None
    assert detail["query_batches"] == DASHBOARD_QUERY_BATCHES


def test_tenant_isolation_and_fixed_query_batches(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    _seed_machine(db, context, code="LOCAL")
    other = Organization(name="Other", code="OTHER")
    db.add(other)
    db.flush()
    user = User(
        organization_id=other.id,
        email="o@o.test",
        display_name="O",
        auth_provider_id="test:o",
    )
    db.add(user)
    db.flush()
    branch = Branch(organization_id=other.id, name="X", code="X")
    db.add(branch)
    db.flush()
    db.add(
        Analyzer(
            organization_id=other.id,
            branch_id=branch.id,
            code="FOREIGN",
            vendor="OtherCo",
            model="Z",
            protocol="ASTM",
            host="10.0.0.9",
            port=1,
        )
    )
    db.commit()
    body = client.get("/api/v1/analyzer-dashboard").json()
    assert body["summary"]["total_analyzers"] == 1
    assert body["analyzers"][0]["code"] == "LOCAL"
    assert body["query_batches"] == DASHBOARD_QUERY_BATCHES
    _seed_machine(db, context, code="HEM-02", vendor="Abbott")
    db.commit()
    two = client.get("/api/v1/analyzer-dashboard").json()
    assert two["summary"]["total_analyzers"] == 2
    assert two["query_batches"] == DASHBOARD_QUERY_BATCHES
    filtered = client.get("/api/v1/analyzer-dashboard?vendor=Abbott").json()
    assert filtered["summary"]["total_analyzers"] == 1
    assert filtered["analyzers"][0]["vendor"] == "Abbott"


def test_branch_scope_denied(client: TestClient, db: Session, context: AuthContext) -> None:
    analyzer = _seed_machine(db, context)
    db.commit()
    other_branch = Branch(organization_id=context.organization_id, name="B", code="B")
    db.add(other_branch)
    db.commit()
    scoped = AuthContext(
        user_id=context.user_id,
        organization_id=context.organization_id,
        email=context.email,
        branch_ids=frozenset({analyzer.branch_id}),
        permissions=context.permissions,
        is_organization_scoped=False,
    )
    from app.auth import get_auth_context
    from app.main import app

    app.dependency_overrides[get_auth_context] = lambda: scoped
    denied = client.get(f"/api/v1/analyzer-dashboard?branch_id={other_branch.id}")
    assert denied.status_code == 403
    allowed = client.get("/api/v1/analyzer-dashboard")
    assert allowed.status_code == 200
    assert allowed.json()["summary"]["total_analyzers"] == 1

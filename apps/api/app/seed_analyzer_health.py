"""Development-only analyzer telemetry so Machine health has rows to show."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Analyzer,
    AnalyzerConnectionEvent,
    AnalyzerMessage,
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


def _hash(body: str) -> str:
    return sha256(body.encode("utf-8")).hexdigest()


def _heartbeat(
    *,
    organization_id: UUID,
    branch_id: UUID,
    analyzer_id: UUID,
    occurred_at: datetime,
    success: bool,
    latency_ms: int | None,
    suffix: str,
) -> AnalyzerConnectionEvent:
    return AnalyzerConnectionEvent(
        organization_id=organization_id,
        branch_id=branch_id,
        analyzer_id=analyzer_id,
        event_type="heartbeat",
        attempt=1,
        success=success,
        latency_ms=latency_ms,
        message="TCP probe succeeded" if success else "Connection refused",
        correlation_id=f"demo-{suffix}",
        occurred_at=occurred_at,
    )


def _visit(
    db: Session,
    *,
    organization_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    barcode: str,
    order_number: str,
    patient_number: str,
    created_at: datetime,
) -> tuple[Patient, LabOrder, Specimen]:
    patient = Patient(
        organization_id=organization_id,
        patient_number=patient_number,
        full_name=f"Demo Patient {patient_number}",
        phone="9999999999",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(patient)
    db.flush()
    order = LabOrder(
        organization_id=organization_id,
        branch_id=branch_id,
        patient_id=patient.id,
        order_number=order_number,
        visit_type="OP",
        doctor_name="Dr Demo",
        status="registered",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(order)
    db.flush()
    specimen = Specimen(
        organization_id=organization_id,
        branch_id=branch_id,
        order_id=order.id,
        barcode=barcode,
        specimen_type="Whole blood",
        container_type="EDTA lavender tube",
        status="accepted",
        collected_by=user_id,
        collected_at=created_at,
        received_by=user_id,
        received_at=created_at + timedelta(minutes=8),
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(specimen)
    db.flush()
    return patient, order, specimen


def _work_item(
    *,
    organization_id: UUID,
    branch_id: UUID,
    specimen_id: UUID,
    order_id: UUID,
    test_id: UUID,
    analyzer_id: UUID,
    mapping_id: UUID,
    machine_test_code: str,
    status: str,
    created_at: datetime,
    user_id: UUID,
    correlation: str,
) -> AnalyzerWorklistItem:
    return AnalyzerWorklistItem(
        organization_id=organization_id,
        branch_id=branch_id,
        specimen_id=specimen_id,
        order_id=order_id,
        test_id=test_id,
        analyzer_id=analyzer_id,
        mapping_id=mapping_id,
        machine_test_code=machine_test_code,
        status=status,
        correlation_id=correlation,
        created_by=user_id,
        updated_by=user_id,
        created_at=created_at,
        updated_at=created_at,
    )


def seed_analyzer_health_demo(
    db: Session, organization: Organization, branch: Branch, user: User
) -> bool:
    existing = db.scalar(
        select(Analyzer).where(
            Analyzer.organization_id == organization.id,
            Analyzer.code == "DEMO-HEM",
        )
    )
    if existing:
        return False

    now = datetime.now(UTC)
    cbc = db.scalar(
        select(TestCatalogItem).where(
            TestCatalogItem.organization_id == organization.id,
            TestCatalogItem.code == "CBC",
        )
    )
    lft = db.scalar(
        select(TestCatalogItem).where(
            TestCatalogItem.organization_id == organization.id,
            TestCatalogItem.code == "LFT",
        )
    )
    urine = db.scalar(
        select(TestCatalogItem).where(
            TestCatalogItem.organization_id == organization.id,
            TestCatalogItem.code == "URINE",
        )
    )
    if cbc is None or lft is None or urine is None:
        raise RuntimeError("Seed the test catalogue before analyzer health demo data.")

    machines = [
        Analyzer(
            organization_id=organization.id,
            branch_id=branch.id,
            code="DEMO-HEM",
            vendor="Sysmex",
            model="XN-1000",
            protocol="HL7_LAW",
            host="192.168.10.51",
            port=5000,
            connection_mode="bidirectional",
            connection_status="connected",
            heartbeat_interval_seconds=60,
            last_connection_test_at=now - timedelta(minutes=2),
            last_connected_at=now - timedelta(minutes=2),
            created_by=user.id,
            updated_by=user.id,
        ),
        Analyzer(
            organization_id=organization.id,
            branch_id=branch.id,
            code="DEMO-CHEM",
            vendor="Abbott",
            model="Architect c4000",
            protocol="HL7_LAW",
            host="192.168.10.52",
            port=5001,
            connection_mode="bidirectional",
            connection_status="connected",
            heartbeat_interval_seconds=60,
            last_connection_test_at=now - timedelta(minutes=4),
            last_connected_at=now - timedelta(minutes=4),
            created_by=user.id,
            updated_by=user.id,
        ),
        Analyzer(
            organization_id=organization.id,
            branch_id=branch.id,
            code="DEMO-COAG",
            vendor="Siemens",
            model="CS-2500",
            protocol="ASTM",
            host="192.168.10.53",
            port=5002,
            connection_mode="bidirectional",
            connection_status="error",
            heartbeat_interval_seconds=60,
            last_connection_test_at=now - timedelta(hours=3),
            last_connection_error="Connection refused (demo offline analyzer)",
            created_by=user.id,
            updated_by=user.id,
        ),
        Analyzer(
            organization_id=organization.id,
            branch_id=branch.id,
            code="DEMO-UA",
            vendor="Roche",
            model="Cobas u411",
            protocol="HL7_LAW",
            host="192.168.10.54",
            port=5003,
            connection_mode="bidirectional",
            connection_status="connected",
            heartbeat_interval_seconds=60,
            last_connection_test_at=now - timedelta(minutes=1),
            last_connected_at=now - timedelta(minutes=1),
            created_by=user.id,
            updated_by=user.id,
        ),
    ]
    db.add_all(machines)
    db.flush()
    hem, chem, coag, ua = machines

    mappings = [
        AnalyzerTestMapping(
            organization_id=organization.id,
            analyzer_id=hem.id,
            test_id=cbc.id,
            machine_test_code="CBC",
            created_by=user.id,
            updated_by=user.id,
        ),
        AnalyzerTestMapping(
            organization_id=organization.id,
            analyzer_id=chem.id,
            test_id=lft.id,
            machine_test_code="LFT",
            created_by=user.id,
            updated_by=user.id,
        ),
        AnalyzerTestMapping(
            organization_id=organization.id,
            analyzer_id=ua.id,
            test_id=urine.id,
            machine_test_code="UA",
            created_by=user.id,
            updated_by=user.id,
        ),
    ]
    db.add_all(mappings)
    db.flush()
    hem_map, chem_map, ua_map = mappings

    events: list[AnalyzerConnectionEvent] = []
    for hour in range(12, -1, -1):
        stamp = now - timedelta(hours=hour, minutes=3)
        events.append(
            _heartbeat(
                organization_id=organization.id,
                branch_id=branch.id,
                analyzer_id=hem.id,
                occurred_at=stamp,
                success=True,
                latency_ms=45 + hour,
                suffix=f"hem-{hour}",
            )
        )
        chem_ok = hour not in {5, 6}
        events.append(
            _heartbeat(
                organization_id=organization.id,
                branch_id=branch.id,
                analyzer_id=chem.id,
                occurred_at=stamp + timedelta(minutes=1),
                success=chem_ok,
                latency_ms=None if not chem_ok else 420 + hour * 40,
                suffix=f"chem-{hour}",
            )
        )
        events.append(
            _heartbeat(
                organization_id=organization.id,
                branch_id=branch.id,
                analyzer_id=ua.id,
                occurred_at=stamp + timedelta(minutes=2),
                success=True,
                latency_ms=90,
                suffix=f"ua-{hour}",
            )
        )
    events.append(
        _heartbeat(
            organization_id=organization.id,
            branch_id=branch.id,
            analyzer_id=coag.id,
            occurred_at=now - timedelta(hours=10),
            success=True,
            latency_ms=70,
            suffix="coag-old-ok",
        )
    )
    events.append(
        _heartbeat(
            organization_id=organization.id,
            branch_id=branch.id,
            analyzer_id=coag.id,
            occurred_at=now - timedelta(hours=3, minutes=10),
            success=False,
            latency_ms=None,
            suffix="coag-down",
        )
    )
    db.add_all(events)

    for index in range(3):
        created = now - timedelta(hours=2, minutes=15 * index)
        _, order, specimen = _visit(
            db,
            organization_id=organization.id,
            branch_id=branch.id,
            user_id=user.id,
            barcode=f"LQDEMOHEM{index:02d}",
            order_number=f"ORD-DEMO-HEM-{index:02d}",
            patient_number=f"PT-DEMO-HEM-{index:02d}",
            created_at=created,
        )
        work = _work_item(
            organization_id=organization.id,
            branch_id=branch.id,
            specimen_id=specimen.id,
            order_id=order.id,
            test_id=cbc.id,
            analyzer_id=hem.id,
            mapping_id=hem_map.id,
            machine_test_code="CBC",
            status="result_received",
            created_at=created,
            user_id=user.id,
            correlation=f"demo-hem-w{index}",
        )
        db.add(work)
        db.flush()
        started = created + timedelta(minutes=2)
        finished = started + timedelta(seconds=8)
        db.add(
            AnalyzerOrderAttempt(
                organization_id=organization.id,
                branch_id=branch.id,
                worklist_item_id=work.id,
                analyzer_id=hem.id,
                attempt_no=1,
                state="acknowledged",
                correlation_id=f"demo-hem-a{index}",
                started_at=started,
                finished_at=finished,
                created_by=user.id,
                created_at=started,
                updated_at=finished,
            )
        )
        outbound = f"MSH|^~\\&|LIS|DEMO|XN|{index}"
        inbound = f"MSA|AA|{index}"
        db.add_all(
            [
                AnalyzerMessage(
                    organization_id=organization.id,
                    analyzer_id=hem.id,
                    worklist_item_id=work.id,
                    direction="outbound",
                    body=outbound,
                    payload_hash=_hash(outbound),
                    correlation_id=f"demo-hem-w{index}",
                    created_at=started,
                ),
                AnalyzerMessage(
                    organization_id=organization.id,
                    analyzer_id=hem.id,
                    worklist_item_id=work.id,
                    direction="inbound",
                    body=inbound,
                    payload_hash=_hash(inbound),
                    correlation_id=f"demo-hem-w{index}",
                    created_at=finished,
                ),
            ]
        )
        db.add(
            LabResult(
                organization_id=organization.id,
                branch_id=branch.id,
                worklist_item_id=work.id,
                specimen_id=specimen.id,
                order_id=order.id,
                test_id=cbc.id,
                analyzer_id=hem.id,
                correlation_id=f"demo-hem-r{index}",
                status="released",
                created_by=user.id,
                created_at=finished + timedelta(minutes=4),
                released_at=finished + timedelta(minutes=12),
                released_by=user.id,
            )
        )

    delayed_at = now - timedelta(hours=6)
    _, delayed_order, delayed_specimen = _visit(
        db,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=user.id,
        barcode="LQDEMOCHEM00",
        order_number="ORD-DEMO-CHEM-00",
        patient_number="PT-DEMO-CHEM-00",
        created_at=delayed_at,
    )
    delayed_work = _work_item(
        organization_id=organization.id,
        branch_id=branch.id,
        specimen_id=delayed_specimen.id,
        order_id=delayed_order.id,
        test_id=lft.id,
        analyzer_id=chem.id,
        mapping_id=chem_map.id,
        machine_test_code="LFT",
        status="awaiting_result",
        created_at=delayed_at,
        user_id=user.id,
        correlation="demo-chem-delayed",
    )
    db.add(delayed_work)
    db.flush()
    db.add(
        AnalyzerOrderAttempt(
            organization_id=organization.id,
            branch_id=branch.id,
            worklist_item_id=delayed_work.id,
            analyzer_id=chem.id,
            attempt_no=1,
            state="failed",
            error="NAK (demo)",
            correlation_id="demo-chem-a0",
            created_by=user.id,
            created_at=delayed_at + timedelta(minutes=1),
            started_at=delayed_at + timedelta(minutes=1),
            finished_at=delayed_at + timedelta(minutes=1, seconds=4),
        )
    )
    db.add(
        AnalyzerOrderAttempt(
            organization_id=organization.id,
            branch_id=branch.id,
            worklist_item_id=delayed_work.id,
            analyzer_id=chem.id,
            attempt_no=2,
            state="acknowledged",
            correlation_id="demo-chem-a1",
            created_by=user.id,
            created_at=delayed_at + timedelta(minutes=3),
            started_at=delayed_at + timedelta(minutes=3),
            finished_at=delayed_at + timedelta(minutes=3, seconds=9),
        )
    )

    for index in range(2):
        created = now - timedelta(minutes=40 + index * 5)
        _, order, specimen = _visit(
            db,
            organization_id=organization.id,
            branch_id=branch.id,
            user_id=user.id,
            barcode=f"LQDEMOCHEM{index + 1:02d}",
            order_number=f"ORD-DEMO-CHEM-{index + 1:02d}",
            patient_number=f"PT-DEMO-CHEM-{index + 1:02d}",
            created_at=created,
        )
        work = _work_item(
            organization_id=organization.id,
            branch_id=branch.id,
            specimen_id=specimen.id,
            order_id=order.id,
            test_id=lft.id,
            analyzer_id=chem.id,
            mapping_id=chem_map.id,
            machine_test_code="LFT",
            status="failed",
            created_at=created,
            user_id=user.id,
            correlation=f"demo-chem-fail-{index}",
        )
        db.add(work)
        db.flush()
        db.add(
            AnalyzerOrderAttempt(
                organization_id=organization.id,
                branch_id=branch.id,
                worklist_item_id=work.id,
                analyzer_id=chem.id,
                attempt_no=1,
                state="failed",
                error="Timeout (demo)",
                correlation_id=f"demo-chem-fail-a{index}",
                created_by=user.id,
                created_at=created + timedelta(minutes=1),
            )
        )

    for index, status in enumerate(
        ["pending", "queued", "queued", "awaiting_result", "awaiting_result", "pending"]
    ):
        created = now - timedelta(minutes=20 + index)
        _, order, specimen = _visit(
            db,
            organization_id=organization.id,
            branch_id=branch.id,
            user_id=user.id,
            barcode=f"LQDEMOUA{index:02d}",
            order_number=f"ORD-DEMO-UA-{index:02d}",
            patient_number=f"PT-DEMO-UA-{index:02d}",
            created_at=created,
        )
        work = _work_item(
            organization_id=organization.id,
            branch_id=branch.id,
            specimen_id=specimen.id,
            order_id=order.id,
            test_id=urine.id,
            analyzer_id=ua.id,
            mapping_id=ua_map.id,
            machine_test_code="UA",
            status=status,
            created_at=created,
            user_id=user.id,
            correlation=f"demo-ua-w{index}",
        )
        db.add(work)
        db.flush()
        if status == "awaiting_result":
            db.add(
                AnalyzerOrderAttempt(
                    organization_id=organization.id,
                    branch_id=branch.id,
                    worklist_item_id=work.id,
                    analyzer_id=ua.id,
                    attempt_no=1,
                    state="acknowledged",
                    correlation_id=f"demo-ua-a{index}",
                    created_by=user.id,
                    created_at=created + timedelta(minutes=1),
                    started_at=created + timedelta(minutes=1),
                    finished_at=created + timedelta(minutes=1, seconds=6),
                )
            )

    return True


CLINICAL_FLEET = (
    {
        "code": "DEMO-HEM2",
        "vendor": "Beckman Coulter",
        "model": "DxH 900",
        "protocol": "HL7_LAW",
        "host": "192.168.10.55",
        "port": 5004,
        "test_code": "CBC",
        "machine_test_code": "CBC",
        "profile": "healthy",
    },
    {
        "code": "DEMO-CHEM2",
        "vendor": "Roche",
        "model": "cobas c 503",
        "protocol": "HL7_LAW",
        "host": "192.168.10.56",
        "port": 5005,
        "test_code": "LFT",
        "machine_test_code": "LFT",
        "profile": "healthy",
    },
    {
        "code": "DEMO-KFT",
        "vendor": "Siemens",
        "model": "Atellica CH 930",
        "protocol": "HL7_LAW",
        "host": "192.168.10.57",
        "port": 5006,
        "test_code": "KFT",
        "machine_test_code": "KFT",
        "profile": "healthy",
    },
    {
        "code": "DEMO-LIPID",
        "vendor": "Beckman Coulter",
        "model": "AU5800",
        "protocol": "HL7_LAW",
        "host": "192.168.10.58",
        "port": 5007,
        "test_code": "LIPID",
        "machine_test_code": "LIPID",
        "profile": "retries",
    },
    {
        "code": "DEMO-IA",
        "vendor": "Roche",
        "model": "cobas e 801",
        "protocol": "HL7_LAW",
        "host": "192.168.10.59",
        "port": 5008,
        "test_code": "THYROID",
        "machine_test_code": "TFT",
        "profile": "healthy",
    },
    {
        "code": "DEMO-IM",
        "vendor": "Abbott",
        "model": "Alinity i",
        "protocol": "HL7_LAW",
        "host": "192.168.10.60",
        "port": 5009,
        "test_code": "THYROID",
        "machine_test_code": "THY",
        "profile": "latency",
    },
    {
        "code": "DEMO-HBA1C",
        "vendor": "Bio-Rad",
        "model": "D-10",
        "protocol": "ASTM",
        "host": "192.168.10.61",
        "port": 5010,
        "test_code": "HBA1C",
        "machine_test_code": "A1C",
        "profile": "latency",
    },
    {
        "code": "DEMO-COAG2",
        "vendor": "Werfen",
        "model": "ACL TOP 550 CTS",
        "protocol": "HL7_LAW",
        "host": "192.168.10.62",
        "port": 5011,
        "test_code": None,
        "machine_test_code": "COAG",
        "profile": "sparse",
    },
    {
        "code": "DEMO-UA2",
        "vendor": "Siemens",
        "model": "Clinitek Novus",
        "protocol": "HL7_LAW",
        "host": "192.168.10.63",
        "port": 5012,
        "test_code": "URINE",
        "machine_test_code": "UA",
        "profile": "healthy",
    },
    {
        "code": "DEMO-BG",
        "vendor": "Radiometer",
        "model": "ABL90 FLEX PLUS",
        "protocol": "ASTM",
        "host": "192.168.10.64",
        "port": 5013,
        "test_code": None,
        "machine_test_code": "BG",
        "profile": "sparse",
    },
    {
        "code": "DEMO-ISE",
        "vendor": "Medica",
        "model": "EasyLyte",
        "protocol": "ASTM",
        "host": "192.168.10.65",
        "port": 5014,
        "test_code": "KFT",
        "machine_test_code": "ISE",
        "profile": "queue",
    },
    {
        "code": "DEMO-ESR",
        "vendor": "Alifax",
        "model": "Test 1 THL",
        "protocol": "PROPRIETARY",
        "host": "192.168.10.66",
        "port": 5015,
        "test_code": "CBC",
        "machine_test_code": "ESR",
        "profile": "latency",
    },
    {
        "code": "DEMO-BC",
        "vendor": "BD",
        "model": "BACTEC FX40",
        "protocol": "ASTM",
        "host": "192.168.10.67",
        "port": 5016,
        "test_code": None,
        "machine_test_code": "BC",
        "profile": "offline",
    },
    {
        "code": "DEMO-VITEK",
        "vendor": "bioMérieux",
        "model": "VITEK 2 Compact",
        "protocol": "HL7_LAW",
        "host": "192.168.10.68",
        "port": 5017,
        "test_code": None,
        "machine_test_code": "IDAST",
        "profile": "sparse",
    },
    {
        "code": "DEMO-VITD",
        "vendor": "Diasorin",
        "model": "LIAISON XL",
        "protocol": "HL7_LAW",
        "host": "192.168.10.69",
        "port": 5018,
        "test_code": "VITD",
        "machine_test_code": "VITD",
        "profile": "healthy",
    },
)


def _catalog(db: Session, organization_id: UUID, code: str) -> TestCatalogItem:
    item = db.scalar(
        select(TestCatalogItem).where(
            TestCatalogItem.organization_id == organization_id,
            TestCatalogItem.code == code,
        )
    )
    if item is None:
        raise RuntimeError(f"Missing catalogue test {code} for analyzer demo data.")
    return item


def _probes(
    *,
    organization_id: UUID,
    branch_id: UUID,
    analyzer: Analyzer,
    now: datetime,
    profile: str,
) -> list[AnalyzerConnectionEvent]:
    events: list[AnalyzerConnectionEvent] = []
    if profile == "offline":
        events.append(
            _heartbeat(
                organization_id=organization_id,
                branch_id=branch_id,
                analyzer_id=analyzer.id,
                occurred_at=now - timedelta(hours=11),
                success=True,
                latency_ms=80,
                suffix=f"{analyzer.code}-old",
            )
        )
        events.append(
            _heartbeat(
                organization_id=organization_id,
                branch_id=branch_id,
                analyzer_id=analyzer.id,
                occurred_at=now - timedelta(hours=4),
                success=False,
                latency_ms=None,
                suffix=f"{analyzer.code}-down",
            )
        )
        return events
    hours = 6 if profile == "sparse" else 12
    for hour in range(hours, -1, -1):
        stamp = now - timedelta(hours=hour, minutes=5)
        if profile == "latency":
            ok, latency = True, 480 + hour * 35
        elif profile == "retries":
            ok, latency = hour not in {3, 4}, 110
        else:
            ok, latency = True, 38 + (hour % 7) * 4
        events.append(
            _heartbeat(
                organization_id=organization_id,
                branch_id=branch_id,
                analyzer_id=analyzer.id,
                occurred_at=stamp,
                success=ok,
                latency_ms=None if not ok else latency,
                suffix=f"{analyzer.code}-{hour}",
            )
        )
    return events


def _completed_orders(
    db: Session,
    *,
    organization: Organization,
    branch: Branch,
    user: User,
    analyzer: Analyzer,
    mapping: AnalyzerTestMapping,
    test: TestCatalogItem,
    now: datetime,
    count: int,
) -> None:
    slug = analyzer.code.replace("DEMO-", "")
    for index in range(count):
        created = now - timedelta(hours=1, minutes=12 * index)
        _, order, specimen = _visit(
            db,
            organization_id=organization.id,
            branch_id=branch.id,
            user_id=user.id,
            barcode=f"LQ{slug}{index:02d}",
            order_number=f"ORD-{slug}-{index:02d}",
            patient_number=f"PT-{slug}-{index:02d}",
            created_at=created,
        )
        work = _work_item(
            organization_id=organization.id,
            branch_id=branch.id,
            specimen_id=specimen.id,
            order_id=order.id,
            test_id=test.id,
            analyzer_id=analyzer.id,
            mapping_id=mapping.id,
            machine_test_code=mapping.machine_test_code,
            status="result_received",
            created_at=created,
            user_id=user.id,
            correlation=f"demo-{slug}-w{index}",
        )
        db.add(work)
        db.flush()
        started = created + timedelta(minutes=3)
        finished = started + timedelta(seconds=7)
        db.add(
            AnalyzerOrderAttempt(
                organization_id=organization.id,
                branch_id=branch.id,
                worklist_item_id=work.id,
                analyzer_id=analyzer.id,
                attempt_no=1,
                state="acknowledged",
                correlation_id=f"demo-{slug}-a{index}",
                started_at=started,
                finished_at=finished,
                created_by=user.id,
                created_at=started,
                updated_at=finished,
            )
        )
        db.add(
            LabResult(
                organization_id=organization.id,
                branch_id=branch.id,
                worklist_item_id=work.id,
                specimen_id=specimen.id,
                order_id=order.id,
                test_id=test.id,
                analyzer_id=analyzer.id,
                correlation_id=f"demo-{slug}-r{index}",
                status="released",
                created_by=user.id,
                created_at=finished + timedelta(minutes=5),
                released_at=finished + timedelta(minutes=14),
                released_by=user.id,
            )
        )


def seed_clinical_fleet(
    db: Session, organization: Organization, branch: Branch, user: User
) -> int:
    now = datetime.now(UTC)
    created = 0
    for spec in CLINICAL_FLEET:
        already = db.scalar(
            select(Analyzer).where(
                Analyzer.organization_id == organization.id,
                Analyzer.code == spec["code"],
            )
        )
        if already:
            continue
        profile = spec["profile"]
        online = profile != "offline"
        analyzer = Analyzer(
            organization_id=organization.id,
            branch_id=branch.id,
            code=spec["code"],
            vendor=spec["vendor"],
            model=spec["model"],
            protocol=spec["protocol"],
            host=spec["host"],
            port=spec["port"],
            connection_mode="bidirectional",
            connection_status="connected" if online else "error",
            heartbeat_interval_seconds=60,
            last_connection_test_at=now - timedelta(minutes=3 if online else 240),
            last_connected_at=(now - timedelta(minutes=3)) if online else None,
            last_connection_error=None
            if online
            else "No TCP response — instrument offline for service (demo)",
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(analyzer)
        db.flush()
        db.add_all(
            _probes(
                organization_id=organization.id,
                branch_id=branch.id,
                analyzer=analyzer,
                now=now,
                profile=profile,
            )
        )
        mapping = None
        test = None
        if spec["test_code"]:
            test = _catalog(db, organization.id, spec["test_code"])
            mapping = AnalyzerTestMapping(
                organization_id=organization.id,
                analyzer_id=analyzer.id,
                test_id=test.id,
                machine_test_code=spec["machine_test_code"],
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(mapping)
            db.flush()
        if mapping is not None and test is not None and profile == "healthy":
            _completed_orders(
                db,
                organization=organization,
                branch=branch,
                user=user,
                analyzer=analyzer,
                mapping=mapping,
                test=test,
                now=now,
                count=2,
            )
        if mapping is not None and test is not None and profile == "retries":
            created_at = now - timedelta(minutes=35)
            slug = spec["code"].replace("DEMO-", "")
            _, order, specimen = _visit(
                db,
                organization_id=organization.id,
                branch_id=branch.id,
                user_id=user.id,
                barcode=f"LQ{slug}00",
                order_number=f"ORD-{slug}-00",
                patient_number=f"PT-{slug}-00",
                created_at=created_at,
            )
            work = _work_item(
                organization_id=organization.id,
                branch_id=branch.id,
                specimen_id=specimen.id,
                order_id=order.id,
                test_id=test.id,
                analyzer_id=analyzer.id,
                mapping_id=mapping.id,
                machine_test_code=mapping.machine_test_code,
                status="awaiting_result",
                created_at=created_at,
                user_id=user.id,
                correlation=f"demo-{slug}-retry",
            )
            db.add(work)
            db.flush()
            db.add(
                AnalyzerOrderAttempt(
                    organization_id=organization.id,
                    branch_id=branch.id,
                    worklist_item_id=work.id,
                    analyzer_id=analyzer.id,
                    attempt_no=1,
                    state="failed",
                    error="NAK — reagent flag (demo)",
                    correlation_id=f"demo-{slug}-nak",
                    created_by=user.id,
                    created_at=created_at + timedelta(minutes=1),
                )
            )
            db.add(
                AnalyzerOrderAttempt(
                    organization_id=organization.id,
                    branch_id=branch.id,
                    worklist_item_id=work.id,
                    analyzer_id=analyzer.id,
                    attempt_no=2,
                    state="acknowledged",
                    correlation_id=f"demo-{slug}-ack",
                    created_by=user.id,
                    created_at=created_at + timedelta(minutes=4),
                )
            )
        if mapping is not None and test is not None and profile == "latency":
            _completed_orders(
                db,
                organization=organization,
                branch=branch,
                user=user,
                analyzer=analyzer,
                mapping=mapping,
                test=test,
                now=now,
                count=1,
            )
        if profile == "queue" and mapping is not None and test is not None:
            for index, status in enumerate(
                ["pending", "queued", "queued", "awaiting_result", "pending"]
            ):
                created_at = now - timedelta(minutes=8 + index)
                slug = spec["code"].replace("DEMO-", "")
                _, order, specimen = _visit(
                    db,
                    organization_id=organization.id,
                    branch_id=branch.id,
                    user_id=user.id,
                    barcode=f"LQ{slug}Q{index}",
                    order_number=f"ORD-{slug}-Q{index}",
                    patient_number=f"PT-{slug}-Q{index}",
                    created_at=created_at,
                )
                db.add(
                    _work_item(
                        organization_id=organization.id,
                        branch_id=branch.id,
                        specimen_id=specimen.id,
                        order_id=order.id,
                        test_id=test.id,
                        analyzer_id=analyzer.id,
                        mapping_id=mapping.id,
                        machine_test_code=mapping.machine_test_code,
                        status=status,
                        created_at=created_at,
                        user_id=user.id,
                        correlation=f"demo-{slug}-q{index}",
                    )
                )
        created += 1
    return created


OFFLINE_DEMO_CODES = frozenset({"DEMO-COAG", "DEMO-BC"})


def refresh_live_demo_probes(db: Session, organization: Organization, branch: Branch) -> None:
    """Keep demo heartbeats fresh so Machine health does not mark the fleet stale."""
    now = datetime.now(UTC)
    analyzers = list(
        db.scalars(
            select(Analyzer).where(
                Analyzer.organization_id == organization.id,
                Analyzer.code.like("DEMO-%"),
            )
        ).all()
    )
    for analyzer in analyzers:
        if analyzer.code in OFFLINE_DEMO_CODES:
            continue
        db.add(
            _heartbeat(
                organization_id=organization.id,
                branch_id=branch.id,
                analyzer_id=analyzer.id,
                occurred_at=now,
                success=True,
                latency_ms=42,
                suffix=f"{analyzer.code}-live",
            )
        )
        analyzer.connection_status = "connected"
        analyzer.last_connection_test_at = now
        analyzer.last_connected_at = now
        analyzer.last_connection_error = None


def seed_demo_if_ready(db: Session) -> None:
    organization = db.scalar(select(Organization).where(Organization.code == "DEVLAB"))
    if organization is None:
        return
    branch = db.scalar(
        select(Branch).where(Branch.organization_id == organization.id, Branch.code == "KOL")
    )
    user = db.scalar(select(User).where(User.email == "admin@dev.labora.local"))
    if branch is None or user is None:
        return
    seed_analyzer_health_demo(db, organization, branch, user)
    seed_clinical_fleet(db, organization, branch, user)
    refresh_live_demo_probes(db, organization, branch)

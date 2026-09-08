"""Derived analyzer machine-health analytics from existing OLTP tables."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthContext
from app.config import Settings, get_settings
from app.models import (
    Analyzer,
    AnalyzerConnectionEvent,
    AnalyzerMessage,
    AnalyzerOrderAttempt,
    AnalyzerWorklistItem,
    Branch,
    LabResult,
)
from app.schemas import (
    AnalyzerAlertRead,
    AnalyzerDashboardDetailRead,
    AnalyzerDashboardRead,
    AnalyzerDashboardRowRead,
    AnalyzerDashboardSummaryRead,
    AnalyzerHealthAttemptRead,
    AnalyzerHealthEventRead,
    AnalyzerHealthScoreRead,
    AnalyzerTrendPointRead,
)

OPEN_QUEUE_STATUSES = frozenset({"pending", "queued", "awaiting_result"})
COMPLETED_WORK_STATUSES = frozenset({"result_received", "completed"})
RESULT_PIPELINE_STATUSES = frozenset({"awaiting_result", "result_received", "completed"})
TERMINAL_ATTEMPT_STATES = frozenset({"acknowledged", "failed"})
DASHBOARD_QUERY_BATCHES = 6


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value * 100, 2)


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def health_band(score: float, connectivity: str, settings: Settings) -> str:
    if connectivity == "offline":
        return "offline"
    if score >= settings.health_healthy_min:
        return "healthy"
    if score >= settings.health_warning_min:
        return "warning"
    if score >= settings.health_degraded_min:
        return "degraded"
    return "critical"


def component_latency_score(avg_ms: float | None, settings: Settings) -> float:
    if avg_ms is None:
        return 100.0
    good = float(settings.health_latency_good_ms)
    critical = float(settings.health_latency_critical_ms)
    if avg_ms <= good:
        return 100.0
    if avg_ms >= critical:
        return 0.0
    return max(0.0, 100.0 * (1 - (avg_ms - good) / (critical - good)))


def component_queue_score(depth: int, settings: Settings) -> float:
    critical = max(settings.health_queue_critical, 1)
    if depth <= 0:
        return 100.0
    if depth >= critical:
        return 0.0
    return max(0.0, 100.0 * (1 - depth / critical))


def calculate_analyzer_health(
    *,
    availability: float | None,
    order_success: float | None,
    result_success: float | None,
    avg_latency_ms: float | None,
    queue_depth: int,
    connectivity: str,
    settings: Settings | None = None,
) -> AnalyzerHealthScoreRead:
    settings = settings or get_settings()
    availability_score = 0.0 if availability is None else availability * 100
    order_score = 100.0 if order_success is None else order_success * 100
    result_score = 100.0 if result_success is None else result_success * 100
    latency_score = component_latency_score(avg_latency_ms, settings)
    queue_score = component_queue_score(queue_depth, settings)
    score = (
        availability_score * settings.health_availability_weight
        + order_score * settings.health_order_success_weight
        + result_score * settings.health_result_success_weight
        + latency_score * settings.health_latency_weight
        + queue_score * settings.health_queue_weight
    )
    score = round(min(100.0, max(0.0, score)), 1)
    reasons: list[str] = []
    if availability is None or availability < 0.9:
        reasons.append("Low probe availability / uptime")
    if order_success is not None and order_success < 0.9:
        reasons.append("Order ACK success below target")
    if result_success is not None and result_success < 0.9:
        reasons.append("Results delayed or missing after ACK")
    if avg_latency_ms is not None and avg_latency_ms > settings.health_latency_good_ms:
        reasons.append("Latency above threshold")
    if queue_depth >= settings.health_queue_warn:
        reasons.append("Queue backlog increasing")
    if connectivity == "offline":
        reasons.insert(0, "Analyzer offline or heartbeat stale")
    status = health_band(score, connectivity, settings)
    return AnalyzerHealthScoreRead(score=score, status=status, reasons=reasons)


def compute_uptime_intervals(
    events: list[AnalyzerConnectionEvent],
    *,
    window_start: datetime,
    window_end: datetime,
    heartbeat_seconds: int,
) -> tuple[float, float, float | None]:
    """Return (online_seconds, offline_seconds, uptime_ratio) for the window."""
    start = aware(window_start)
    end = aware(window_end)
    if start is None or end is None or end <= start:
        return 0.0, 0.0, None
    window = (end - start).total_seconds()
    ordered = sorted(
        (event for event in events if aware(event.occurred_at)),
        key=lambda item: aware(item.occurred_at) or start,
    )
    stale_after = timedelta(seconds=max(heartbeat_seconds, 1) * 2)

    def is_online(event: AnalyzerConnectionEvent | None) -> bool:
        return bool(event and event.success)

    prior = None
    for event in ordered:
        occurred = aware(event.occurred_at)
        if occurred is not None and occurred <= start:
            prior = event
        else:
            break
    cursor = start
    online_seconds = 0.0
    state_online = is_online(prior)
    last_event_at = aware(prior.occurred_at) if prior else None
    in_window = [
        event
        for event in ordered
        if (occurred := aware(event.occurred_at)) is not None and start < occurred <= end
    ]
    for event in in_window:
        occurred = aware(event.occurred_at)
        if occurred is None:
            continue
        if last_event_at is not None and state_online and occurred - last_event_at > stale_after:
            stale_from = last_event_at + stale_after
            if stale_from < occurred:
                online_end = min(occurred, max(stale_from, cursor))
                if state_online and online_end > cursor:
                    online_seconds += (min(online_end, occurred) - cursor).total_seconds()
                cursor = max(cursor, stale_from)
                state_online = False
        if occurred > cursor:
            if state_online:
                online_seconds += (occurred - cursor).total_seconds()
            cursor = occurred
        state_online = is_online(event)
        last_event_at = occurred
    if cursor < end:
        if state_online and last_event_at is not None and end - last_event_at > stale_after:
            stale_from = last_event_at + stale_after
            if stale_from > cursor:
                online_seconds += (min(stale_from, end) - cursor).total_seconds()
            cursor = min(end, max(cursor, stale_from))
            state_online = False
        if state_online and end > cursor:
            online_seconds += (end - cursor).total_seconds()
    online_seconds = max(0.0, min(online_seconds, window))
    offline_seconds = max(0.0, window - online_seconds)
    return online_seconds, offline_seconds, ratio(online_seconds, window)


def current_connectivity(
    events: list[AnalyzerConnectionEvent],
    *,
    now: datetime,
    heartbeat_seconds: int,
) -> tuple[str, datetime | None, datetime | None, str | None, int | None]:
    if not events:
        return "offline", None, None, None, None
    latest = max(
        events, key=lambda item: aware(item.occurred_at) or datetime.min.replace(tzinfo=UTC)
    )
    last_seen = aware(latest.occurred_at)
    successes = [event for event in events if event.success]
    last_ok = (
        aware(
            max(
                successes,
                key=lambda item: aware(item.occurred_at) or datetime.min.replace(tzinfo=UTC),
            ).occurred_at
        )
        if successes
        else None
    )
    stale_after = timedelta(seconds=max(heartbeat_seconds, 1) * 2)
    error = None if latest.success else latest.message
    latency = latest.latency_ms
    if last_seen is None:
        return "offline", last_seen, last_ok, error, latency
    if latest.success and now - last_seen <= stale_after:
        return "online", last_seen, last_ok, None, latency
    return "offline", last_seen, last_ok, error or "Heartbeat stale", latency


@dataclass
class AnalyzerMetrics:
    probe_attempts: int = 0
    probe_successes: int = 0
    probe_failures: int = 0
    timeouts: int = 0
    latencies: list[float] = field(default_factory=list)
    events: list[AnalyzerConnectionEvent] = field(default_factory=list)
    attempts: int = 0
    acknowledged: int = 0
    failed_orders: int = 0
    retried: int = 0
    order_durations: list[float] = field(default_factory=list)
    queue_waits: list[float] = field(default_factory=list)
    failed_attempt_rows: list[AnalyzerOrderAttempt] = field(default_factory=list)
    work_items: int = 0
    completed_items: int = 0
    pending_items: int = 0
    failed_items: int = 0
    cancelled_items: int = 0
    queue_depth: int = 0
    pipeline_items: int = 0
    delayed_results: int = 0
    backlog_ages: list[float] = field(default_factory=list)
    results: int = 0
    technically_reviewed: int = 0
    validated: int = 0
    released: int = 0
    result_tats: list[float] = field(default_factory=list)
    inbound_messages: int = 0
    outbound_messages: int = 0
    ack_messages: int = 0
    work_timeline: list[tuple[datetime, str]] = field(default_factory=list)


def _is_timeout(message: str) -> bool:
    text = message.lower()
    return "timed out" in text or "timeout" in text or "time out" in text


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _rounded(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _bucket_key(moment: datetime, hourly: bool, zone: ZoneInfo) -> datetime:
    local = moment.astimezone(zone)
    if hourly:
        local = local.replace(minute=0, second=0, microsecond=0)
    else:
        local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local


def _build_trends(
    *,
    analyzers: list[Analyzer],
    metrics: dict[UUID, AnalyzerMetrics],
    window_start: datetime,
    window_end: datetime,
    zone_name: str,
    heartbeat_by_id: dict[UUID, int],
) -> list[AnalyzerTrendPointRead]:
    zone = _zone(zone_name)
    hourly = (window_end - window_start) <= timedelta(hours=48)
    delta = timedelta(hours=1) if hourly else timedelta(days=1)
    buckets: list[datetime] = []
    cursor = _bucket_key(window_start, hourly, zone)
    end_bucket = _bucket_key(window_end, hourly, zone)
    while cursor <= end_bucket:
        buckets.append(cursor)
        cursor = cursor + delta
    if not buckets:
        return []
    points: list[AnalyzerTrendPointRead] = []
    for bucket in buckets:
        bucket_start = bucket.astimezone(UTC)
        bucket_end = (bucket + delta).astimezone(UTC)
        online_total = 0.0
        window_total = 0.0
        fail = 0
        probes = 0
        latencies: list[float] = []
        queue = 0
        for analyzer in analyzers:
            metric = metrics[analyzer.id]
            hb = heartbeat_by_id.get(analyzer.id, 60)
            bucket_events = [
                event
                for event in metric.events
                if (occurred := aware(event.occurred_at)) is not None
                and bucket_start < occurred <= bucket_end
            ]
            online, _, uptime = compute_uptime_intervals(
                metric.events,
                window_start=bucket_start,
                window_end=min(bucket_end, window_end),
                heartbeat_seconds=hb,
            )
            span = (min(bucket_end, window_end) - bucket_start).total_seconds()
            if span > 0:
                online_total += online
                window_total += span
            probes += len(bucket_events)
            fail += sum(1 for event in bucket_events if not event.success)
            latencies.extend(
                float(event.latency_ms) for event in bucket_events if event.latency_ms is not None
            )
            # Throughput uses work_timeline after the hourly loop.
        for analyzer in analyzers:
            metric = metrics[analyzer.id]
            queue += metric.queue_depth
        # Work item completions are not timestamp-filtered per bucket without extra data;
        # count probes' sibling: completed_items distributed is wrong. Leave throughput as
        # connection-event successes per hour as operational activity, plus completed if we
        # tagged them. We store work_items created_at on a side list.
        fmt = "%Y-%m-%d %H:00" if hourly else "%Y-%m-%d"
        points.append(
            AnalyzerTrendPointRead(
                bucket=bucket_start,
                label=bucket.strftime(fmt),
                availability_percent=percent(ratio(online_total, window_total)),
                failure_rate=percent(ratio(fail, probes)),
                avg_latency_ms=_rounded(_mean(latencies)),
                throughput=None,
                queue_depth=round(queue / max(len(analyzers), 1), 2),
            )
        )
    # Fill throughput from worklist created_at stored on metrics via extra field
    created_completed: dict[datetime, int] = defaultdict(int)
    for metric in metrics.values():
        for created_at, status in metric.work_timeline:
            occurred = aware(created_at)
            if occurred is None or not (window_start < occurred <= window_end):
                continue
            if status not in COMPLETED_WORK_STATUSES:
                continue
            created_completed[_bucket_key(occurred, hourly, zone)] += 1
    for point in points:
        local = aware(point.bucket)
        if local is None:
            continue
        key = _bucket_key(local, hourly, zone)
        count = created_completed.get(key, 0)
        point.throughput = round(count / max(delta.total_seconds() / 3600, 1 / 60), 4)
    return points


def get_analyzer_dashboard(
    db: Session,
    context: AuthContext,
    *,
    branch_id: UUID | None = None,
    analyzer_id: UUID | None = None,
    vendor: str | None = None,
    model: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> AnalyzerDashboardRead:
    settings = settings or get_settings()
    now = aware(now) or datetime.now(UTC)
    window_end = aware(date_to) or now
    window_start = aware(date_from) or (window_end - timedelta(hours=24))
    if window_end <= window_start:
        window_start = window_end - timedelta(hours=24)

    analyzer_stmt = (
        select(Analyzer, Branch)
        .join(Branch, Branch.id == Analyzer.branch_id)
        .where(Analyzer.organization_id == context.organization_id)
    )
    if not context.is_organization_scoped:
        analyzer_stmt = analyzer_stmt.where(Analyzer.branch_id.in_(context.branch_ids or set()))
    if branch_id is not None:
        if not context.can_access_branch(branch_id):
            raise HTTPException(status_code=403, detail="Branch access denied")
        analyzer_stmt = analyzer_stmt.where(Analyzer.branch_id == branch_id)
    if analyzer_id is not None:
        analyzer_stmt = analyzer_stmt.where(Analyzer.id == analyzer_id)
    if vendor and vendor.strip():
        analyzer_stmt = analyzer_stmt.where(Analyzer.vendor.ilike(f"%{vendor.strip()}%"))
    if model and model.strip():
        analyzer_stmt = analyzer_stmt.where(Analyzer.model.ilike(f"%{model.strip()}%"))

    rows = list(db.execute(analyzer_stmt.order_by(Analyzer.code, Analyzer.id)).all())
    query_batches = 1
    analyzers = [item[0] for item in rows]
    branches = {item[0].id: item[1] for item in rows}
    empty = AnalyzerDashboardRead(
        window_start=window_start,
        window_end=window_end,
        summary=AnalyzerDashboardSummaryRead(
            total_analyzers=0,
            online=0,
            degraded=0,
            offline=0,
            overall_uptime_percent=None,
            order_success_percent=None,
            result_success_percent=None,
            open_alerts=0,
        ),
        analyzers=[],
        trends=[],
        alerts=[],
        detail=None,
        query_batches=query_batches,
    )
    if not analyzers:
        return empty

    ids = [analyzer.id for analyzer in analyzers]
    lookback = window_start - timedelta(days=7)
    delayed_before = now - timedelta(hours=settings.health_delayed_result_hours)

    events = list(
        db.scalars(
            select(AnalyzerConnectionEvent).where(
                AnalyzerConnectionEvent.organization_id == context.organization_id,
                AnalyzerConnectionEvent.analyzer_id.in_(ids),
                AnalyzerConnectionEvent.occurred_at >= lookback,
                AnalyzerConnectionEvent.occurred_at <= window_end,
            )
        ).all()
    )
    query_batches += 1
    attempts = list(
        db.scalars(
            select(AnalyzerOrderAttempt).where(
                AnalyzerOrderAttempt.organization_id == context.organization_id,
                AnalyzerOrderAttempt.analyzer_id.in_(ids),
                AnalyzerOrderAttempt.created_at >= window_start,
                AnalyzerOrderAttempt.created_at <= window_end,
            )
        ).all()
    )
    query_batches += 1
    work_items = list(
        db.scalars(
            select(AnalyzerWorklistItem).where(
                AnalyzerWorklistItem.organization_id == context.organization_id,
                AnalyzerWorklistItem.analyzer_id.in_(ids),
            )
        ).all()
    )
    query_batches += 1
    results = list(
        db.scalars(
            select(LabResult).where(
                LabResult.organization_id == context.organization_id,
                LabResult.analyzer_id.in_(ids),
                LabResult.created_at >= window_start,
                LabResult.created_at <= window_end,
            )
        ).all()
    )
    query_batches += 1
    messages = list(
        db.scalars(
            select(AnalyzerMessage).where(
                AnalyzerMessage.organization_id == context.organization_id,
                AnalyzerMessage.analyzer_id.in_(ids),
                AnalyzerMessage.created_at >= window_start,
                AnalyzerMessage.created_at <= window_end,
            )
        ).all()
    )
    query_batches += 1

    metrics: dict[UUID, AnalyzerMetrics] = {
        analyzer.id: AnalyzerMetrics() for analyzer in analyzers
    }
    for event in events:
        metric = metrics.get(event.analyzer_id)
        if metric is None:
            continue
        metric.events.append(event)
        occurred = aware(event.occurred_at)
        if occurred is None or not (window_start < occurred <= window_end):
            continue
        metric.probe_attempts += 1
        if event.success:
            metric.probe_successes += 1
        else:
            metric.probe_failures += 1
            if _is_timeout(event.message):
                metric.timeouts += 1
        if event.latency_ms is not None:
            metric.latencies.append(float(event.latency_ms))
    for attempt in attempts:
        metric = metrics.get(attempt.analyzer_id)
        if metric is None:
            continue
        metric.attempts += 1
        if attempt.attempt_no > 1:
            metric.retried += 1
        if attempt.state == "acknowledged":
            metric.acknowledged += 1
        elif attempt.state == "failed":
            metric.failed_orders += 1
            metric.failed_attempt_rows.append(attempt)
        started = aware(attempt.started_at)
        finished = aware(attempt.finished_at)
        created = aware(attempt.created_at)
        if started and finished and finished >= started:
            metric.order_durations.append((finished - started).total_seconds())
        if started and created and started >= created:
            metric.queue_waits.append((started - created).total_seconds())
    worklist_created: dict[UUID, datetime] = {}
    for item in work_items:
        metric = metrics.get(item.analyzer_id)
        if metric is None:
            continue
        created = aware(item.created_at)
        if item.status in OPEN_QUEUE_STATUSES:
            metric.queue_depth += 1
            if created:
                metric.backlog_ages.append((now - created).total_seconds())
        if item.status == "awaiting_result" and created and created <= delayed_before:
            metric.delayed_results += 1
        if created and window_start < created <= window_end:
            metric.work_items += 1
            metric.work_timeline.append((created, item.status))
            if item.status in COMPLETED_WORK_STATUSES:
                metric.completed_items += 1
            if item.status == "pending":
                metric.pending_items += 1
            if item.status == "failed":
                metric.failed_items += 1
            if item.status == "cancelled":
                metric.cancelled_items += 1
            if item.status in RESULT_PIPELINE_STATUSES:
                metric.pipeline_items += 1
        worklist_created[item.id] = created or window_start
    results_by_worklist = {row.worklist_item_id for row in results}
    for item in work_items:
        metric = metrics.get(item.analyzer_id)
        if metric is None:
            continue
        created = aware(item.created_at)
        if created and window_start < created <= window_end and item.id in results_by_worklist:
            if item.status not in RESULT_PIPELINE_STATUSES:
                metric.pipeline_items += 1
    for result in results:
        metric = metrics.get(result.analyzer_id)
        if metric is None:
            continue
        metric.results += 1
        if (
            result.status in {"technically_reviewed", "pathologist_validated", "released"}
            or result.technical_reviewed_at
        ):
            metric.technically_reviewed += 1
        if (
            result.status in {"pathologist_validated", "released"}
            or result.pathologist_validated_at
        ):
            metric.validated += 1
        if result.status == "released" or result.released_at:
            metric.released += 1
        created = aware(result.created_at)
        origin = worklist_created.get(result.worklist_item_id)
        if created and origin and created >= origin:
            metric.result_tats.append((created - origin).total_seconds())
    for message in messages:
        metric = metrics.get(message.analyzer_id)
        if metric is None:
            continue
        if message.direction == "inbound":
            metric.inbound_messages += 1
            if "MSA" in message.body or "ACK" in message.body.upper():
                metric.ack_messages += 1
        else:
            metric.outbound_messages += 1

    hours = max((window_end - window_start).total_seconds() / 3600, 1 / 60)
    heartbeat_by_id = {analyzer.id: analyzer.heartbeat_interval_seconds for analyzer in analyzers}
    table: list[AnalyzerDashboardRowRead] = []
    alerts: list[AnalyzerAlertRead] = []
    fleet_online_seconds = 0.0
    fleet_window_seconds = 0.0
    fleet_ack = 0
    fleet_fail = 0
    fleet_pipeline = 0
    fleet_results = 0

    for analyzer in analyzers:
        metric = metrics[analyzer.id]
        branch = branches[analyzer.id]
        online_s, offline_s, uptime = compute_uptime_intervals(
            metric.events,
            window_start=window_start,
            window_end=window_end,
            heartbeat_seconds=analyzer.heartbeat_interval_seconds,
        )
        connectivity, last_seen, last_ok, current_error, current_latency = current_connectivity(
            metric.events, now=now, heartbeat_seconds=analyzer.heartbeat_interval_seconds
        )
        lat_sorted = sorted(metric.latencies)
        order_success = ratio(metric.acknowledged, metric.acknowledged + metric.failed_orders)
        result_success = ratio(metric.results, max(metric.pipeline_items, metric.results))
        if metric.pipeline_items == 0 and metric.results == 0:
            result_success = None
        retry_rate = ratio(metric.retried, metric.attempts)
        timeout_rate = ratio(metric.timeouts, metric.probe_attempts)
        health = calculate_analyzer_health(
            availability=uptime,
            order_success=order_success,
            result_success=result_success,
            avg_latency_ms=_mean(metric.latencies),
            queue_depth=metric.queue_depth,
            connectivity=connectivity,
            settings=settings,
        )
        row = AnalyzerDashboardRowRead(
            analyzer_id=analyzer.id,
            code=analyzer.code,
            vendor=analyzer.vendor,
            model=analyzer.model,
            branch_id=branch.id,
            branch_code=branch.code,
            branch_name=branch.name,
            time_zone=branch.time_zone,
            configuration_status=analyzer.status.value
            if hasattr(analyzer.status, "value")
            else str(analyzer.status),
            connectivity=connectivity,
            health=health,
            uptime_percent=percent(uptime),
            orders=metric.attempts,
            order_success_percent=percent(order_success),
            result_success_percent=percent(result_success),
            avg_latency_ms=_rounded(_mean(metric.latencies)),
            p50_latency_ms=_rounded(percentile(lat_sorted, 0.5)),
            p95_latency_ms=_rounded(percentile(lat_sorted, 0.95)),
            queue_depth=metric.queue_depth,
            last_seen_at=last_seen,
            last_successful_connection_at=last_ok,
            failed_orders=metric.failed_orders,
            retry_rate=round(retry_rate, 4) if retry_rate is not None else None,
            current_error=current_error,
            timeout_rate=round(timeout_rate, 4) if timeout_rate is not None else None,
            avg_order_duration_seconds=_rounded(_mean(metric.order_durations)),
            avg_result_turnaround_seconds=_rounded(_mean(metric.result_tats)),
            work_items=metric.work_items,
            completed_items=metric.completed_items,
            pending_items=metric.pending_items,
            failed_items=metric.failed_items,
            cancelled_items=metric.cancelled_items,
            results_received=metric.results,
            technically_reviewed=metric.technically_reviewed,
            validated=metric.validated,
            released=metric.released,
            tests_per_hour=round(metric.completed_items / hours, 4),
            inbound_messages=metric.inbound_messages,
            outbound_messages=metric.outbound_messages,
        )
        table.append(row)
        fleet_online_seconds += online_s
        fleet_window_seconds += (window_end - window_start).total_seconds()
        fleet_ack += metric.acknowledged
        fleet_fail += metric.failed_orders
        fleet_pipeline += metric.pipeline_items
        fleet_results += metric.results
        alerts.extend(
            _alerts_for(
                analyzer=analyzer,
                connectivity=connectivity,
                metric=metric,
                order_success=order_success,
                retry_rate=retry_rate,
                avg_latency=_mean(metric.latencies),
                settings=settings,
            )
        )

    online = sum(1 for row in table if row.connectivity == "online")
    offline = sum(1 for row in table if row.connectivity == "offline")
    degraded = sum(
        1 for row in table if row.connectivity == "online" and row.health.status != "healthy"
    )
    summary = AnalyzerDashboardSummaryRead(
        total_analyzers=len(table),
        online=online,
        degraded=degraded,
        offline=offline,
        overall_uptime_percent=percent(ratio(fleet_online_seconds, fleet_window_seconds)),
        order_success_percent=percent(ratio(fleet_ack, fleet_ack + fleet_fail)),
        result_success_percent=percent(ratio(fleet_results, max(fleet_pipeline, fleet_results)))
        if fleet_pipeline or fleet_results
        else None,
        open_alerts=len(alerts),
    )
    default_zone = next(iter(branches.values())).time_zone if branches else "UTC"
    trends = _build_trends(
        analyzers=analyzers,
        metrics=metrics,
        window_start=window_start,
        window_end=window_end,
        zone_name=default_zone,
        heartbeat_by_id=heartbeat_by_id,
    )
    detail = None
    if analyzer_id is not None and table:
        row = table[0]
        metric = metrics[row.analyzer_id]
        analyzer = analyzers[0]
        online_s, offline_s, _ = compute_uptime_intervals(
            metric.events,
            window_start=window_start,
            window_end=window_end,
            heartbeat_seconds=analyzer.heartbeat_interval_seconds,
        )
        _, _, _, _, current_latency = current_connectivity(
            metric.events, now=now, heartbeat_seconds=analyzer.heartbeat_interval_seconds
        )
        recent_events = sorted(
            metric.events, key=lambda item: aware(item.occurred_at) or window_start, reverse=True
        )[:25]
        failed_attempts = sorted(
            metric.failed_attempt_rows,
            key=lambda item: aware(item.created_at) or window_start,
            reverse=True,
        )[:25]
        detail = AnalyzerDashboardDetailRead(
            analyzer_id=row.analyzer_id,
            connectivity=row.connectivity,
            health=row.health,
            last_heartbeat_at=row.last_seen_at,
            last_successful_connection_at=row.last_successful_connection_at,
            current_latency_ms=int(current_latency) if current_latency is not None else None,
            queue_depth=row.queue_depth,
            current_error=row.current_error,
            uptime_seconds=online_s,
            downtime_seconds=offline_s,
            connection_failures=metric.probe_failures,
            failed_orders=metric.failed_orders,
            retry_rate=row.retry_rate,
            timeout_rate=row.timeout_rate,
            avg_latency_ms=row.avg_latency_ms,
            p50_latency_ms=row.p50_latency_ms,
            p95_latency_ms=row.p95_latency_ms,
            avg_order_duration_seconds=row.avg_order_duration_seconds,
            avg_result_turnaround_seconds=row.avg_result_turnaround_seconds,
            orders_received=metric.attempts,
            completed_orders=metric.completed_items,
            results_received=metric.results,
            tests_processed=metric.work_items,
            tests_per_hour=row.tests_per_hour,
            inbound_messages=metric.inbound_messages,
            outbound_messages=metric.outbound_messages,
            ack_messages=metric.ack_messages,
            connection_events=[
                AnalyzerHealthEventRead(
                    occurred_at=aware(event.occurred_at) or window_start,
                    event_type=event.event_type,
                    success=event.success,
                    latency_ms=event.latency_ms,
                    message=event.message,
                )
                for event in recent_events
            ],
            failed_attempts=[
                AnalyzerHealthAttemptRead(
                    created_at=aware(attempt.created_at) or window_start,
                    attempt_no=attempt.attempt_no,
                    state=attempt.state,
                    error=attempt.error,
                )
                for attempt in failed_attempts
            ],
            hourly_trends=_build_trends(
                analyzers=[analyzer],
                metrics={analyzer.id: metric},
                window_start=window_start,
                window_end=window_end,
                zone_name=row.time_zone,
                heartbeat_by_id=heartbeat_by_id,
            ),
        )
    return AnalyzerDashboardRead(
        window_start=window_start,
        window_end=window_end,
        summary=summary,
        analyzers=table,
        trends=trends,
        alerts=alerts,
        detail=detail,
        query_batches=query_batches,
    )


def _alerts_for(
    *,
    analyzer: Analyzer,
    connectivity: str,
    metric: AnalyzerMetrics,
    order_success: float | None,
    retry_rate: float | None,
    avg_latency: float | None,
    settings: Settings,
) -> list[AnalyzerAlertRead]:
    items: list[AnalyzerAlertRead] = []
    if connectivity == "offline":
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="analyzer_offline",
                severity="critical",
                message="Analyzer is offline or the last heartbeat is stale",
            )
        )
    if metric.failed_orders >= settings.health_order_fail_count_warn or (
        order_success is not None
        and order_success < 0.5
        and metric.failed_orders + metric.acknowledged >= 3
    ):
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="repeated_order_failures",
                severity="warning",
                message=f"{metric.failed_orders} failed order attempt(s) in the window",
            )
        )
    if (
        retry_rate is not None
        and retry_rate >= settings.health_retry_rate_warn
        and metric.attempts >= 3
    ):
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="high_retry_rate",
                severity="warning",
                message=f"Retry rate {round(retry_rate * 100, 1)}%",
            )
        )
    if avg_latency is not None and avg_latency > settings.health_latency_good_ms:
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="high_latency",
                severity="warning"
                if avg_latency < settings.health_latency_critical_ms
                else "critical",
                message=f"Average TCP latency {round(avg_latency)} ms",
            )
        )
    if metric.queue_depth >= settings.health_queue_warn:
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="queue_buildup",
                severity="warning"
                if metric.queue_depth < settings.health_queue_critical
                else "critical",
                message=f"Open work queue depth {metric.queue_depth}",
            )
        )
    if metric.delayed_results:
        items.append(
            AnalyzerAlertRead(
                analyzer_id=analyzer.id,
                analyzer_code=analyzer.code,
                type="delayed_results",
                severity="warning",
                message=(
                    f"{metric.delayed_results} item(s) awaiting result longer than "
                    f"{settings.health_delayed_result_hours}h"
                ),
            )
        )
    return items

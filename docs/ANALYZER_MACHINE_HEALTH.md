# Analyzer machine health

Operational dashboard derived from existing LIS tables. It does not invent clinical
quality, reference ranges, or extra fact tables.

## Why no extra tables or APIs

LaboraIQ already records probes (`analyzer_connection_events`), order sends
(`analyzer_order_attempts`), worklist items, raw messages, and normalized results.
The dashboard **aggregates** those rows for a time window. A history table would
duplicate probe data. One `GET /api/v1/analyzer-dashboard` returns KPIs, per-machine
rows, fleet trends, alerts, and optional detail.

## Fact grain

| Fact | Table | Grain |
| --- | --- | --- |
| Connection | `analyzer_connection_events` | One TCP probe/heartbeat/test |
| Order attempt | `analyzer_order_attempts` | One send try for one worklist item |
| Workload | `analyzer_worklist_items` | One analyzer/test/specimen item |
| Result | `lab_results` | One normalized result for one worklist item |
| Message | `analyzer_messages` | One inbound or outbound payload (diagnostics) |

Dimensions are existing entities: organization (from the session), branch, analyzer,
LIS test (`test_id` on worklist/result), mapping, catalog parameter, UTC timestamps.
Branch `time_zone` is used only when labeling hourly detail buckets.

## Distinctions (do not collapse)

1. TCP probe success is not a protocol ACK.
2. `AnalyzerOrderAttempt.state == acknowledged` is not a stored `lab_results` row.
3. Result received is not technical review, pathologist validation, or release.

## KPI formulas

Window defaults to the last 24 hours (`date_from` / `date_to`, UTC).

- **Uptime %** (per analyzer): online seconds / window seconds from probe intervals.
  Consecutive successful probes are ONLINE; failures are OFFLINE. If the last probe
  is older than `2 × heartbeat_interval_seconds`, the tail of the window is OFFLINE
  (stale). This is estimated from probes, not continuous device telemetry.
- **Order success %**: `acknowledged / (acknowledged + failed)`. `queued` and
  `sending` are excluded. `0/0` is `null`.
- **Result success %**: worklist items that have a `lab_results` row / items in
  `awaiting_result` or `result_received` (or that already have a result). `0/0` is
  `null`.
- **Retry rate**: attempts with `attempt_no > 1` / all attempts in the window.
- **Queue depth (now)**: current worklist rows in `pending`, `queued`, or
  `awaiting_result` (not limited to the date window).
- **Avg / P50 / P95 latency**: `latency_ms` on connection events in the window
  (Python percentiles so SQLite and Postgres match).
- **Throughput**: worklist items that reached `result_received` or `completed` in
  the window, expressed per hour of window length.
- **Connectivity**: ONLINE if the latest probe in (or before) the window is a
  success and is not stale; otherwise OFFLINE. `never_tested` with no events is
  OFFLINE.

## Health score

Weights and band cutoffs come from API settings (not the React app):

- Availability 30%, order success 25%, result success 20%, latency 15%, queue 10%.
- Missing order/result samples score as 100 for that component (do not punish idle
  machines). No connection events score availability as 0.
- Latency component: 100 at or below `HEALTH_LATENCY_GOOD_MS`, 0 at or above
  `HEALTH_LATENCY_CRITICAL_MS`.
- Queue component: 100 at depth 0, 0 at or above `HEALTH_QUEUE_CRITICAL`.
- Bands: 90–100 healthy, 75–89 warning, 50–74 degraded, 0–49 critical. Connectivity
  OFFLINE forces status `offline` even if the numeric score is higher.

`reasons[]` lists the components that pulled the score down.

## Alerts (derived)

No alert table. Types: `analyzer_offline`, `repeated_order_failures`,
`high_retry_rate`, `high_latency`, `queue_buildup`, `delayed_results`.

## API

`GET /api/v1/analyzer-dashboard`

Requires `analyzer.read`. Tenant is the authenticated organization. Query:
`branch_id`, `analyzer_id`, `vendor`, `model`, `date_from`, `date_to`.

When `analyzer_id` is set, `detail` includes reasons, recent probes, failed
attempts, message counts, and hourly trends in the branch timezone.

## Indexes

Composite `(organization_id, analyzer_id, time)` indexes support window filters.
They do not change application writes.

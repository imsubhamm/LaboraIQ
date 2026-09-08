import { X } from "lucide-react";
import { HealthStatusBadge } from "@/components/health-status-badge";
import { TrendChart } from "@/components/trend-chart";
import type { AnalyzerDashboardDetail } from "@/lib/analyzer-health";
import { formatNumber, formatWhen } from "@/lib/analyzer-health";

export function AnalyzerHealthDetail({
  detail,
  onClose
}: {
  detail: AnalyzerDashboardDetail;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop">
      <section className="modal health-detail-modal" role="dialog" aria-labelledby="health-detail-title">
        <div className="modal-head">
          <div>
            <p className="eyebrow">MACHINE HEALTH</p>
            <h2 id="health-detail-title">Analyzer detail</h2>
            <small>{detail.connectivity}</small>
          </div>
          <button aria-label="Close health detail" onClick={onClose}>
            <X />
          </button>
        </div>
        <div className="health-detail-body">
          <div className="health-detail-grid">
            <article>
              <HealthStatusBadge status={detail.health.status} score={detail.health.score} />
              <p>Current health</p>
            </article>
            <article>
              <strong>{formatWhen(detail.last_heartbeat_at)}</strong>
              <p>Last heartbeat</p>
            </article>
            <article>
              <strong>{formatWhen(detail.last_successful_connection_at)}</strong>
              <p>Last successful connection</p>
            </article>
            <article>
              <strong>{formatNumber(detail.current_latency_ms, 0)} ms</strong>
              <p>Current latency</p>
            </article>
            <article>
              <strong>{detail.queue_depth}</strong>
              <p>Current queue</p>
            </article>
            <article>
              <strong>{detail.current_error ?? "None"}</strong>
              <p>Current error</p>
            </article>
          </div>
          {detail.health.reasons.length > 0 && (
            <ul className="health-reasons">
              {detail.health.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          <h3>Reliability</h3>
          <p>
            Uptime {Math.round(detail.uptime_seconds / 60)} min · downtime {Math.round(detail.downtime_seconds / 60)} min
            · connection failures {detail.connection_failures} · failed orders {detail.failed_orders} · retry{" "}
            {detail.retry_rate == null ? "—" : `${(detail.retry_rate * 100).toFixed(1)}%`} · timeout{" "}
            {detail.timeout_rate == null ? "—" : `${(detail.timeout_rate * 100).toFixed(1)}%`}
          </p>
          <h3>Performance</h3>
          <p>
            Avg {formatNumber(detail.avg_latency_ms, 0)} ms · P50 {formatNumber(detail.p50_latency_ms, 0)} · P95{" "}
            {formatNumber(detail.p95_latency_ms, 0)} · order duration {formatNumber(detail.avg_order_duration_seconds, 1)}s
            · result TAT {formatNumber(detail.avg_result_turnaround_seconds, 1)}s
          </p>
          <h3>Workload</h3>
          <p>
            Orders {detail.orders_received} · completed {detail.completed_orders} · results {detail.results_received} ·
            tests {detail.tests_processed} · {formatNumber(detail.tests_per_hour, 2)} / hour
          </p>
          <TrendChart
            title="Availability"
            points={detail.hourly_trends}
            valueKey="availability_percent"
            emptyLabel="No probe history in this window."
          />
          <div className="connection-history">
            <h3>Events</h3>
            {detail.connection_events.length === 0 ? (
              <p>No connection events.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Event</th>
                      <th>Outcome</th>
                      <th>Latency</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.connection_events.map((event) => (
                      <tr key={`${event.occurred_at}-${event.event_type}-${event.message}`}>
                        <td>{formatWhen(event.occurred_at)}</td>
                        <td>{event.event_type}</td>
                        <td>{event.success ? "success" : "failed"}</td>
                        <td>{event.latency_ms ?? "—"}</td>
                        <td>{event.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {detail.failed_attempts.length > 0 && (
              <>
                <h3>Failed order attempts</h3>
                <ul>
                  {detail.failed_attempts.map((attempt) => (
                    <li key={`${attempt.created_at}-${attempt.attempt_no}`}>
                      #{attempt.attempt_no} {attempt.state} · {formatWhen(attempt.created_at)} · {attempt.error ?? "—"}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

import { HealthStatusBadge } from "@/components/health-status-badge";
import type { AnalyzerDashboardRow } from "@/lib/analyzer-health";
import { formatNumber, formatPercent, formatWhen } from "@/lib/analyzer-health";

export function AnalyzerHealthTable({
  rows,
  emptyMessage,
  onSelect
}: {
  rows: AnalyzerDashboardRow[];
  emptyMessage: string;
  onSelect: (row: AnalyzerDashboardRow) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <h3>No analyzer health data</h3>
        <p>{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="analyzer-table">
        <thead>
          <tr>
            <th>Analyzer</th>
            <th>Vendor</th>
            <th>Model</th>
            <th>Status</th>
            <th>Health score</th>
            <th>Uptime</th>
            <th>Orders</th>
            <th>Order success</th>
            <th>Avg latency</th>
            <th>Queue</th>
            <th>Last seen</th>
            <th>Failed orders</th>
            <th>Retry rate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.analyzer_id}>
              <td>
                <button type="button" className="linkish" onClick={() => onSelect(row)}>
                  <strong>{row.code}</strong>
                  <span>
                    {row.branch_name} · {row.branch_code}
                  </span>
                </button>
              </td>
              <td>{row.vendor}</td>
              <td>{row.model}</td>
              <td>
                <HealthStatusBadge status={row.health.status} />
                <span className="muted-line">{row.connectivity}</span>
              </td>
              <td>
                <HealthStatusBadge status={row.health.status} score={row.health.score} />
              </td>
              <td>{formatPercent(row.uptime_percent)}</td>
              <td>{row.orders}</td>
              <td>{formatPercent(row.order_success_percent)}</td>
              <td>{formatNumber(row.avg_latency_ms, 0)} ms</td>
              <td>{row.queue_depth}</td>
              <td>{formatWhen(row.last_seen_at)}</td>
              <td>{row.failed_orders}</td>
              <td>{row.retry_rate == null ? "—" : `${(row.retry_rate * 100).toFixed(1)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import { Activity, AlertTriangle, Cpu, HeartPulse } from "lucide-react";
import { formatPercent } from "@/lib/analyzer-health";

export function AnalyzerHealthKpis({
  summary
}: {
  summary: {
    total_analyzers: number;
    online: number;
    degraded: number;
    offline: number;
    overall_uptime_percent: number | null;
    order_success_percent: number | null;
    result_success_percent: number | null;
    open_alerts: number;
  };
}) {
  const cards = [
    ["Total analyzers", String(summary.total_analyzers), "Configured in this scope", Cpu],
    ["Online", String(summary.online), "Recent successful heartbeat", HeartPulse],
    ["Degraded", String(summary.degraded), "Connected but score below healthy", AlertTriangle],
    ["Offline", String(summary.offline), "No recent successful probe", Activity],
    ["Overall uptime", formatPercent(summary.overall_uptime_percent), "Probe-derived window uptime", HeartPulse],
    ["Order success", formatPercent(summary.order_success_percent), "ACK vs failed attempts", Cpu],
    ["Result success", formatPercent(summary.result_success_percent), "Normalized results vs pipeline", Cpu],
    ["Open alerts", String(summary.open_alerts), "Derived operational alerts", AlertTriangle]
  ] as const;
  return (
    <div className="metric-grid health-kpi-grid">
      {cards.map(([label, value, note, Icon]) => (
        <article className="metric" key={label}>
          <div>
            <p>{label}</p>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
          <Icon />
        </article>
      ))}
    </div>
  );
}

import { AlertTriangle } from "lucide-react";
import type { AnalyzerAlert } from "@/lib/analyzer-health";

export function AnalyzerAlertList({
  alerts,
  emptyMessage
}: {
  alerts: AnalyzerAlert[];
  emptyMessage: string;
}) {
  if (alerts.length === 0) {
    return (
      <article className="panel">
        <div className="panel-title">
          <h2>Alerts</h2>
        </div>
        <p className="empty-compact">{emptyMessage}</p>
      </article>
    );
  }
  return (
    <article className="panel">
      <div className="panel-title">
        <h2>Alerts</h2>
        <span>{alerts.length} open</span>
      </div>
      <ul className="health-alert-list">
        {alerts.map((alert, index) => (
          <li key={`${alert.analyzer_id}-${alert.type}-${index}`} className={alert.severity}>
            <AlertTriangle size={16} aria-hidden="true" />
            <span>
              <strong>
                {alert.analyzer_code} · {alert.type.replaceAll("_", " ")}
              </strong>
              <small>
                {alert.severity}: {alert.message}
              </small>
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

"use client";

import type { AuditNamedCount } from "@/lib/quality-audit";

export function AuditCountChart({
  title,
  points,
  emptyLabel,
  valueMode = "count",
}: {
  title: string;
  points: AuditNamedCount[];
  emptyLabel: string;
  valueMode?: "count" | "value";
}) {
  if (points.length === 0) {
    return (
      <article className="panel trend-panel">
        <div className="panel-title">
          <h2>{title}</h2>
        </div>
        <p className="empty-compact">{emptyLabel}</p>
      </article>
    );
  }
  const values = points.map((point) => (valueMode === "value" ? Number(point.value ?? 0) : point.count));
  const max = Math.max(...values, 1);
  return (
    <article className="panel trend-panel">
      <div className="panel-title">
        <h2>{title}</h2>
      </div>
      <ul className="audit-bar-list">
        {points.map((point, index) => {
          const raw = values[index];
          const width = Math.max(4, (raw / max) * 100);
          return (
            <li key={point.key}>
              <span>{point.label}</span>
              <div>
                <i style={{ width: `${width}%` }} />
              </div>
              <strong>{valueMode === "value" ? `${raw}%` : raw}</strong>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

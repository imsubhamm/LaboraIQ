"use client";

import type { AuditDashboardSummary } from "@/lib/quality-audit";
import { formatPercent } from "@/lib/quality-audit";

type Card = { label: string; value: string; hint: string };

export function AuditSummaryCards({
  summary,
  mode,
}: {
  summary: AuditDashboardSummary;
  mode: "NABL" | "INTERNAL";
}) {
  const cards: Card[] =
    mode === "NABL"
      ? [
          { label: "Total audits", value: String(summary.total_audits), hint: "In selected window" },
          { label: "Compliance %", value: formatPercent(summary.compliance_percent), hint: "Applicable checks" },
          { label: "Open findings", value: String(summary.open_findings), hint: "Not closed" },
          { label: "Critical findings", value: String(summary.critical_findings), hint: "Open critical" },
          { label: "Major findings", value: String(summary.major_findings), hint: "Open major" },
          { label: "Minor findings", value: String(summary.minor_findings), hint: "Open minor" },
          { label: "Overdue CAPA", value: String(summary.overdue_capa), hint: "Past due date" },
          { label: "Evidence pending", value: String(summary.evidence_pending), hint: "Awaiting verification" },
          { label: "Closure %", value: formatPercent(summary.closure_percent), hint: "Closed audits" },
        ]
      : [
          { label: "Audits this month", value: String(summary.audits_this_month), hint: "Created this month" },
          { label: "Scheduled", value: String(summary.scheduled), hint: "Upcoming" },
          { label: "In progress", value: String(summary.in_progress), hint: "Active engagements" },
          { label: "Completed", value: String(summary.completed), hint: "Completed or closed" },
          { label: "Open findings", value: String(summary.open_findings), hint: "Not closed" },
          { label: "High-risk findings", value: String(summary.high_risk_findings), hint: "Critical + major" },
          { label: "Overdue CAPA", value: String(summary.overdue_capa), hint: "Past due date" },
          { label: "Closure rate", value: formatPercent(summary.closure_percent), hint: "Closed audits" },
          {
            label: "Avg closure days",
            value: summary.average_closure_days == null ? "—" : String(summary.average_closure_days),
            hint: "Closed engagements",
          },
        ];

  return (
    <div className="health-kpis audit-kpis">
      {cards.map((card) => (
        <article key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <small>{card.hint}</small>
        </article>
      ))}
    </div>
  );
}

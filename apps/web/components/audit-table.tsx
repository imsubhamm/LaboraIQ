"use client";

import type { AuditDashboardRow } from "@/lib/quality-audit";
import { formatPercent, formatStatus } from "@/lib/quality-audit";
import { CapaStatusBadge } from "@/components/capa-status-badge";
import { FindingStatusBadge } from "@/components/finding-status-badge";

export function AuditTable({
  rows,
  mode,
  emptyMessage,
}: {
  rows: AuditDashboardRow[];
  mode: "NABL" | "INTERNAL";
  emptyMessage: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <h3>No audits in this window</h3>
        <p>{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="analyzer-table">
        <thead>
          <tr>
            <th>Audit number</th>
            {mode === "INTERNAL" && <th>Audit type</th>}
            {mode === "INTERNAL" && <th>Department</th>}
            {mode === "INTERNAL" && <th>Process</th>}
            <th>Audit date</th>
            {mode === "NABL" && <th>Scope</th>}
            <th>Auditor</th>
            <th>Status</th>
            <th>Findings</th>
            {mode === "NABL" && <th>Open findings</th>}
            <th>Compliance %</th>
            <th>CAPA status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <strong>{row.audit_number}</strong>
                <span>
                  {row.title}
                  {row.is_demo ? " · DEMO" : ""}
                </span>
              </td>
              {mode === "INTERNAL" && <td>{row.lab_audit_subtype || row.audit_type}</td>}
              {mode === "INTERNAL" && <td>{row.department_name || "—"}</td>}
              {mode === "INTERNAL" && <td>{row.process_name || "—"}</td>}
              <td>{row.audit_date ? new Date(row.audit_date).toLocaleDateString() : "—"}</td>
              {mode === "NABL" && <td>{row.scope || "—"}</td>}
              <td>{row.auditor_name || "—"}</td>
              <td>
                <FindingStatusBadge status={row.status} />
              </td>
              <td>{row.findings}</td>
              {mode === "NABL" && <td>{row.open_findings}</td>}
              <td>{formatPercent(row.compliance_percent)}</td>
              <td>
                <CapaStatusBadge status={row.capa_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="configuration-note">Status labels: {formatStatus("IN_PROGRESS")} shown as plain text badges.</p>
    </div>
  );
}

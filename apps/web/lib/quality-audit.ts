export type AuditType = "NABL" | "INTERNAL";

export type AuditNamedCount = {
  key: string;
  label: string;
  count: number;
  value?: number | null;
};

export type AuditTrendPoint = {
  label: string;
  audits: number;
  findings: number;
  compliance_percent: number | null;
};

export type AuditDashboardSummary = {
  total_audits: number;
  audits_this_month: number;
  scheduled: number;
  in_progress: number;
  completed: number;
  compliance_percent: number | null;
  open_findings: number;
  critical_findings: number;
  major_findings: number;
  minor_findings: number;
  high_risk_findings: number;
  overdue_capa: number;
  evidence_pending: number;
  closure_percent: number | null;
  average_closure_days: number | null;
};

export type AuditDashboardRow = {
  id: string;
  audit_number: string;
  audit_type: string;
  lab_audit_subtype: string | null;
  title: string;
  scope: string | null;
  process_name: string | null;
  department_name: string | null;
  audit_date: string | null;
  auditor_name: string | null;
  status: string;
  findings: number;
  open_findings: number;
  compliance_percent: number | null;
  capa_status: string;
  is_demo: boolean;
};

export type AuditAlert = {
  code: string;
  severity: string;
  message: string;
  entity_type: string;
  entity_id: string | null;
};

export type AuditDashboard = {
  audit_type: AuditType;
  window_start: string;
  window_end: string;
  summary: AuditDashboardSummary;
  trends: AuditTrendPoint[];
  findings_by_clause: AuditNamedCount[];
  findings_by_department: AuditNamedCount[];
  findings_by_severity: AuditNamedCount[];
  findings_open_vs_closed: AuditNamedCount[];
  compliance_by_department: AuditNamedCount[];
  compliance_by_process: AuditNamedCount[];
  capa_aging: AuditNamedCount[];
  audits: AuditDashboardRow[];
  alerts: AuditAlert[];
  query_batches: number;
};

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "—" : `${value}%`;
}

export function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}

"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { AuditCountChart } from "@/components/audit-count-chart";
import { AuditSummaryCards } from "@/components/audit-summary-cards";
import { AuditTable } from "@/components/audit-table";
import { TrendChart } from "@/components/trend-chart";
import { api, Page } from "@/lib/api";
import type { AuditDashboard, AuditType } from "@/lib/quality-audit";

type BranchOption = { id: string; code: string; name: string };
type DepartmentOption = { id: string; name: string; branch_id: string };
type StandardOption = { id: string; code: string; name: string; version: string };

export function AuditReportPanel({
  auditType,
  title,
  description,
}: {
  auditType: AuditType;
  title: string;
  description: string;
}) {
  const [dashboard, setDashboard] = useState<AuditDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);
  const [standards, setStandards] = useState<StandardOption[]>([]);
  const [branchId, setBranchId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [standardId, setStandardId] = useState("");
  const [processName, setProcessName] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadMeta = useCallback(async () => {
    try {
      const [branchPage, departmentPage] = await Promise.all([
        api<Page<BranchOption>>("/branches?limit=100&offset=0"),
        api<Page<DepartmentOption>>("/departments?limit=100&offset=0"),
      ]);
      setBranches(branchPage.items);
      setDepartments(departmentPage.items);
      if (auditType === "NABL") {
        const std = await api<StandardOption[]>("/audit-standards");
        setStandards(std);
      }
    } catch {
      // Filters degrade gracefully; dashboard load reports the main error.
    }
  }, [auditType]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ audit_type: auditType });
      if (branchId) params.set("branch_id", branchId);
      if (departmentId) params.set("department_id", departmentId);
      if (status) params.set("status", status);
      if (severity) params.set("severity", severity);
      if (standardId) params.set("standard_id", standardId);
      if (processName.trim()) params.set("process_name", processName.trim());
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const payload = await api<AuditDashboard>(`/audit-dashboard?${params}`);
      setDashboard(payload);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load audit report");
    } finally {
      setLoading(false);
    }
  }, [auditType, branchId, departmentId, status, severity, standardId, processName, dateFrom, dateTo]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    void load();
    // Initial + branch scope changes; other filters apply on submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditType, branchId]);

  return (
    <div className="health-panel">
      <div className="page-heading">
        <div>
          <p className="eyebrow">QUALITY MANAGEMENT</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </div>
      <form
        className="health-filters"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          void load();
        }}
      >
        <label>
          Branch
          <select aria-label="Filter by branch" value={branchId} onChange={(event) => setBranchId(event.target.value)}>
            <option value="">All branches</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name} · {branch.code}
              </option>
            ))}
          </select>
        </label>
        <label>
          Department
          <select
            aria-label="Filter by department"
            value={departmentId}
            onChange={(event) => setDepartmentId(event.target.value)}
          >
            <option value="">All departments</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            {["DRAFT", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "FINDINGS_REVIEW", "CAPA_PENDING", "VERIFICATION", "CLOSED"].map(
              (value) => (
                <option key={value} value={value}>
                  {value.replaceAll("_", " ")}
                </option>
              )
            )}
          </select>
        </label>
        <label>
          Severity
          <select aria-label="Filter by severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="">All severities</option>
            {["CRITICAL", "MAJOR", "MINOR", "OBSERVATION"].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        {auditType === "NABL" && (
          <label>
            Standard
            <select
              aria-label="Filter by standard"
              value={standardId}
              onChange={(event) => setStandardId(event.target.value)}
            >
              <option value="">All standards</option>
              {standards.map((standard) => (
                <option key={standard.id} value={standard.id}>
                  {standard.code} · {standard.version}
                </option>
              ))}
            </select>
          </label>
        )}
        {auditType === "INTERNAL" && (
          <label>
            Process
            <input
              aria-label="Filter by process"
              value={processName}
              onChange={(event) => setProcessName(event.target.value)}
              placeholder="e.g. Analytical testing"
            />
          </label>
        )}
        <label>
          From
          <input
            aria-label="From date"
            type="datetime-local"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label>
          To
          <input aria-label="To date" type="datetime-local" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </label>
        <button className="primary" type="submit">
          Apply filters
        </button>
      </form>
      {error && (
        <div className="error-state">
          <AlertCircle size={18} />
          {error}
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      )}
      {loading && !dashboard ? (
        <div className="loading">
          <i />
          <i />
          <i />
        </div>
      ) : dashboard ? (
        <>
          <AuditSummaryCards summary={dashboard.summary} mode={auditType} />
          {dashboard.alerts.length > 0 && (
            <div className="panel">
              <div className="toolbar">
                <span>Alerts</span>
                <span>{dashboard.alerts.length}</span>
              </div>
              <ul className="audit-alert-list">
                {dashboard.alerts.map((alert, index) => (
                  <li key={`${alert.code}-${alert.entity_id ?? index}`}>
                    <strong>{alert.severity}</strong> {alert.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="health-trend-grid">
            <TrendChart title="Audit trend" points={dashboard.trends} valueKey="audits" emptyLabel="No audit trend samples." />
            <TrendChart
              title="Findings trend"
              points={dashboard.trends}
              valueKey="findings"
              emptyLabel="No findings trend samples."
            />
            <TrendChart
              title="Compliance trend"
              points={dashboard.trends}
              valueKey="compliance_percent"
              emptyLabel="No compliance trend samples."
            />
            {auditType === "NABL" ? (
              <AuditCountChart
                title="Findings by clause"
                points={dashboard.findings_by_clause}
                emptyLabel="No clause findings."
              />
            ) : (
              <AuditCountChart
                title="Compliance by process"
                points={dashboard.compliance_by_process}
                emptyLabel="No process compliance samples."
                valueMode="value"
              />
            )}
            <AuditCountChart
              title="Findings by department"
              points={dashboard.findings_by_department}
              emptyLabel="No department findings."
            />
            <AuditCountChart
              title="Findings by severity"
              points={dashboard.findings_by_severity}
              emptyLabel="No severity samples."
            />
            <AuditCountChart
              title="Open vs closed findings"
              points={dashboard.findings_open_vs_closed}
              emptyLabel="No finding status samples."
            />
            <AuditCountChart title="CAPA aging" points={dashboard.capa_aging} emptyLabel="No CAPA aging samples." />
            {auditType === "INTERNAL" && (
              <AuditCountChart
                title="Compliance by department"
                points={dashboard.compliance_by_department}
                emptyLabel="No department compliance samples."
                valueMode="value"
              />
            )}
          </div>
          <div className="panel">
            <div className="toolbar">
              <span>{auditType === "NABL" ? "NABL audits" : "LAB audits"}</span>
              <span>{dashboard.audits.length} audit(s)</span>
            </div>
            <AuditTable
              rows={dashboard.audits}
              mode={auditType}
              emptyMessage="Create an audit or widen the date range. Demo seeds are marked DEMO."
            />
          </div>
        </>
      ) : (
        <div className="empty-state">
          <h3>No audit report data</h3>
          <p>Retry the request or confirm the API is running.</p>
        </div>
      )}
    </div>
  );
}

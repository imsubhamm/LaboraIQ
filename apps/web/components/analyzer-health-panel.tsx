"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { AnalyzerAlertList } from "@/components/analyzer-alert-list";
import { AnalyzerHealthDetail } from "@/components/analyzer-health-detail";
import { AnalyzerHealthKpis } from "@/components/analyzer-health-kpis";
import { AnalyzerHealthTable } from "@/components/analyzer-health-table";
import { TrendChart } from "@/components/trend-chart";
import { api } from "@/lib/api";
import type { AnalyzerDashboard, AnalyzerDashboardDetail, AnalyzerDashboardRow } from "@/lib/analyzer-health";

type BranchOption = { id: string; code: string; name: string };

export function AnalyzerHealthPanel({ branches }: { branches: BranchOption[] }) {
  const [dashboard, setDashboard] = useState<AnalyzerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [branchId, setBranchId] = useState("");
  const [vendor, setVendor] = useState("");
  const [model, setModel] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [detail, setDetail] = useState<AnalyzerDashboardDetail | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (branchId) params.set("branch_id", branchId);
      if (vendor.trim()) params.set("vendor", vendor.trim());
      if (model.trim()) params.set("model", model.trim());
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const query = params.toString();
      const payload = await api<AnalyzerDashboard>(`/analyzer-dashboard${query ? `?${query}` : ""}`);
      setDashboard(payload);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load machine health");
    } finally {
      setLoading(false);
    }
  }, [branchId, vendor, model, dateFrom, dateTo]);

  useEffect(() => {
    void load();
    // Reload when the branch scope changes; vendor/model/dates apply on submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchId]);

  async function openDetail(row: AnalyzerDashboardRow) {
    try {
      setError("");
      const params = new URLSearchParams({ analyzer_id: row.analyzer_id });
      if (branchId) params.set("branch_id", branchId);
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const payload = await api<AnalyzerDashboard>(`/analyzer-dashboard?${params}`);
      setDetail(payload.detail);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load analyzer detail");
    }
  }

  return (
    <div className="health-panel">
      <form
        className="health-filters"
        onSubmit={(event) => {
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
          Vendor
          <input aria-label="Filter by vendor" value={vendor} onChange={(event) => setVendor(event.target.value)} />
        </label>
        <label>
          Model
          <input aria-label="Filter by model" value={model} onChange={(event) => setModel(event.target.value)} />
        </label>
        <label>
          From
          <input aria-label="From date" type="datetime-local" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
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
          <AnalyzerHealthKpis summary={dashboard.summary} />
          <div className="health-trend-grid">
            <TrendChart title="Availability over time" points={dashboard.trends} valueKey="availability_percent" emptyLabel="No availability samples." />
            <TrendChart title="Failure rate over time" points={dashboard.trends} valueKey="failure_rate" emptyLabel="No failure samples." />
            <TrendChart title="Latency over time" points={dashboard.trends} valueKey="avg_latency_ms" emptyLabel="No latency samples." />
            <TrendChart title="Throughput over time" points={dashboard.trends} valueKey="throughput" emptyLabel="No throughput samples." />
            <TrendChart title="Queue depth over time" points={dashboard.trends} valueKey="queue_depth" emptyLabel="No queue samples." />
          </div>
          <AnalyzerAlertList alerts={dashboard.alerts} emptyMessage="No derived alerts in this window." />
          <div className="panel">
            <div className="toolbar">
              <span>Machine health</span>
              <span>{dashboard.analyzers.length} analyzer(s)</span>
            </div>
            <AnalyzerHealthTable
              rows={dashboard.analyzers}
              emptyMessage="Configure an analyzer or widen the date range."
              onSelect={(row) => void openDetail(row)}
            />
          </div>
        </>
      ) : (
        <div className="empty-state">
          <h3>No analyzer health data</h3>
          <p>Retry the request or confirm the API is running on port 8000.</p>
        </div>
      )}
      {detail && <AnalyzerHealthDetail detail={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

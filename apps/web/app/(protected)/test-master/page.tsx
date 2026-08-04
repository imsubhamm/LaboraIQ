"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, Search, Upload } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Parameter = { id: string; name: string; external_code: string; display_order: number };
type TestMaster = {
  id: string; code: string; name: string; service_type: string; department: string;
  sub_department: string; specimen_type: string; container_type: string; price: string;
  is_panel: boolean; validation_status: string; status: string; parameters: Parameter[];
};
type ImportSummary = {
  rows_received: number; tests_created: number; tests_updated: number;
  parameters_imported: number; rows_rejected: number; review_required: number; errors: string[];
};

export default function TestMasterPage() {
  const [records, setRecords] = useState<TestMaster[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportSummary | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const query = new URLSearchParams({ limit: "100", offset: "0" });
      if (search.trim()) query.set("search", search.trim());
      if (reviewOnly) query.set("review_only", "true");
      const result = await api<Page<TestMaster>>(`/test-master?${query}`);
      setRecords(result.items); setTotal(result.total); setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the test master");
    } finally { setLoading(false); }
  }, [search, reviewOnly]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function upload(file: File) {
    const data = new FormData(); data.append("file", file);
    try {
      setUploading(true); setError("");
      const result = await api<ImportSummary>("/test-master/import", { method: "POST", body: data });
      setSummary(result); await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Import failed");
    } finally { setUploading(false); }
  }

  return <section>
    <div className="page-heading test-master-heading">
      <div><p className="eyebrow">LIS · HIS CONFIGURATION</p><h1>Test master</h1>
        <p>Manage orderable laboratory services, specimen requirements, and panel parameters.</p></div>
      {can("test_master.manage") && <label className="primary upload-button">
        <Upload size={17}/>{uploading ? "Importing…" : "Import Excel"}
        <input aria-label="Import LIS HIS test master" type="file" accept=".xlsx" disabled={uploading}
          onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }}/>
      </label>}
    </div>

    {summary && <div className="import-summary panel">
      <CheckCircle2 size={22}/><div><strong>Workbook imported</strong><p>{summary.rows_received} rows processed · {summary.tests_created} tests created · {summary.tests_updated} updated · {summary.parameters_imported} parameters mapped</p></div>
      <div className="import-flags"><span>{summary.review_required} need review</span><span>{summary.rows_rejected} rejected</span></div>
    </div>}
    {error && <div className="error-state"><AlertCircle size={18}/>{error}<button onClick={() => void load()}>Retry</button></div>}

    <div className="test-master-metrics">
      <article><FileSpreadsheet/><span><strong>{total}</strong><small>matching services</small></span></article>
      <article><strong>{records.filter(item => item.is_panel).length}</strong><small>panels in view</small></article>
      <article className="review-metric"><strong>{records.filter(item => item.validation_status === "needs_review").length}</strong><small>need review in view</small></article>
    </div>

    <div className="panel">
      <div className="toolbar test-master-toolbar">
        <label className="search"><Search size={17}/><input aria-label="Search test master" placeholder="Code, test, department, specimen…" value={search} onChange={event => setSearch(event.target.value)}/></label>
        <label className="review-toggle"><input type="checkbox" checked={reviewOnly} onChange={event => setReviewOnly(event.target.checked)}/> Needs review only</label>
      </div>
      {loading ? <div className="loading" aria-label="Loading"><i/><i/><i/></div> : records.length === 0 ?
        <div className="empty-state"><span>0</span><h3>No tests found</h3><p>Import the LIS/HIS workbook or change the current filters.</p></div> :
        <div className="table-wrap"><table className="test-master-table"><thead><tr><th>Code & service</th><th>Classification</th><th>Specimen</th><th>Mapping</th><th>Review</th></tr></thead>
          <tbody>{records.map(item => <tr key={item.id}>
            <td><strong>{item.code}</strong><span>{item.name}</span></td>
            <td><strong>{item.sub_department || item.department}</strong><span>{item.service_type} · {item.department}</span></td>
            <td>{item.specimen_type}</td>
            <td>{item.is_panel ? <><strong>{item.parameters.length} parameters</strong><span>{item.parameters.slice(0, 3).map(parameter => parameter.name).join(", ")}{item.parameters.length > 3 ? "…" : ""}</span></> : <span>Standalone test</span>}</td>
            <td><span className={`mapping-status ${item.validation_status}`}>{item.validation_status === "needs_review" ? "Needs review" : "Validated"}</span></td>
          </tr>)}</tbody></table></div>}
      <div className="pagination"><span>Showing {records.length} of {total}</span><span>First 100 matching records</span></div>
    </div>
  </section>;
}

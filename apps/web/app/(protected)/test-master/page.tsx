"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, Search, Upload } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Parameter = {
  id: string; name: string; external_code: string; display_order: number;
  unit: string | null; reference_low: string | null; reference_high: string | null; reference_text: string | null;
};
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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [editing, setEditing] = useState<TestMaster | null>(null);

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

  async function saveParameter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = new FormData(event.currentTarget);
    const payload = {
      name: String(data.get("name") || "").trim(),
      external_code: String(data.get("external_code") || "").trim(),
      display_order: Number(data.get("display_order") || 0),
      unit: String(data.get("unit") || "").trim() || null,
      reference_low: String(data.get("reference_low") || "").trim() || null,
      reference_high: String(data.get("reference_high") || "").trim() || null,
      reference_text: String(data.get("reference_text") || "").trim() || null,
    };
    const parameterId = String(data.get("parameter_id") || "");
    try {
      setSaving(true); setError("");
      if (parameterId) {
        await api(`/test-master/${editing.id}/parameters/${parameterId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/test-master/${editing.id}/parameters`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      await load();
      const refreshed = await api<Page<TestMaster>>(`/test-master?search=${encodeURIComponent(editing.code)}&limit=5&offset=0`);
      setEditing(refreshed.items.find(item => item.id === editing.id) ?? null);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save parameter");
    } finally {
      setSaving(false);
    }
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
        <div className="table-wrap"><table className="test-master-table"><thead><tr><th>Code & service</th><th>Classification</th><th>Specimen</th><th>Mapping</th><th>Review</th><th>Actions</th></tr></thead>
          <tbody>{records.map(item => <tr key={item.id}>
            <td><strong>{item.code}</strong><span>{item.name}</span></td>
            <td><strong>{item.sub_department || item.department}</strong><span>{item.service_type} · {item.department}</span></td>
            <td>{item.specimen_type}</td>
            <td>{item.parameters.length > 0 ? <><strong>{item.parameters.length} parameters</strong><span>{item.parameters.slice(0, 3).map(parameter => parameter.name).join(", ")}{item.parameters.length > 3 ? "…" : ""}</span></> : <span>No parameters</span>}</td>
            <td><span className={`mapping-status ${item.validation_status}`}>{item.validation_status === "needs_review" ? "Needs review" : "Validated"}</span></td>
            <td>{can("test_master.manage") && <button className="mapping-button" onClick={() => setEditing(item)}>Parameters</button>}</td>
          </tr>)}</tbody></table></div>}
      <div className="pagination"><span>Showing {records.length} of {total}</span><span>First 100 matching records</span></div>
    </div>

    {editing && <div className="modal-backdrop"><section className="modal mapping-modal">
      <div className="modal-head"><div><p className="eyebrow">TEST PARAMETERS</p><h2>{editing.code}</h2><small>{editing.name}</small></div><button aria-label="Close parameters" onClick={() => setEditing(null)}>×</button></div>
      <div className="mapping-layout">
        <aside>
          <h3>Existing parameters</h3>
          {editing.parameters.length === 0 ? <p>No parameters yet.</p> : editing.parameters.map(parameter => (
            <div key={parameter.id} className="mapping-chip-row">
              <button type="button" className="active" onClick={() => {
                const form = document.getElementById("parameter-form") as HTMLFormElement | null;
                if (!form) return;
                (form.elements.namedItem("parameter_id") as HTMLInputElement).value = parameter.id;
                (form.elements.namedItem("name") as HTMLInputElement).value = parameter.name;
                (form.elements.namedItem("external_code") as HTMLInputElement).value = parameter.external_code;
                (form.elements.namedItem("display_order") as HTMLInputElement).value = String(parameter.display_order);
                (form.elements.namedItem("unit") as HTMLInputElement).value = parameter.unit ?? "";
                (form.elements.namedItem("reference_low") as HTMLInputElement).value = parameter.reference_low ?? "";
                (form.elements.namedItem("reference_high") as HTMLInputElement).value = parameter.reference_high ?? "";
                (form.elements.namedItem("reference_text") as HTMLInputElement).value = parameter.reference_text ?? "";
              }}>
                <strong>{parameter.external_code}</strong>
                <span>{parameter.name}{parameter.unit ? ` · ${parameter.unit}` : ""}</span>
              </button>
            </div>
          ))}
        </aside>
        <form id="parameter-form" onSubmit={saveParameter}>
          <input type="hidden" name="parameter_id" defaultValue="" />
          <label>Parameter name *<input name="name" required maxLength={200} /></label>
          <label>External code *<input name="external_code" required maxLength={255} placeholder="ANDRO" /></label>
          <div className="analyzer-form-grid">
            <label>Display order<input name="display_order" type="number" min={0} defaultValue={0} /></label>
            <label>Unit<input name="unit" maxLength={40} placeholder="ng/mL" /></label>
            <label>Reference low<input name="reference_low" maxLength={40} /></label>
            <label>Reference high<input name="reference_high" maxLength={40} /></label>
          </div>
          <label>Reference text<input name="reference_text" maxLength={200} placeholder="Optional qualitative range note" /></label>
          <p className="configuration-note">Do not invent clinical reference ranges. Leave blank until an approved source is available.</p>
          <div className="form-actions">
            <button type="button" onClick={() => setEditing(null)}>Close</button>
            <button className="primary" disabled={saving}>{saving ? "Saving…" : "Save parameter"}</button>
          </div>
        </form>
      </div>
    </section></div>}
  </section>;
}

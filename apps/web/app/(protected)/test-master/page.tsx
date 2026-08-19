"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, Search, Upload } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Parameter = {
  id: string;
  name: string;
  external_code: string;
  display_order: number;
  unit: string | null;
  reference_low: string | null;
  reference_high: string | null;
  reference_text: string | null;
  critical_low: string | null;
  critical_high: string | null;
  reference_source: string | null;
};

type TestMaster = {
  id: string;
  code: string;
  name: string;
  service_type: string;
  department: string;
  sub_department: string;
  specimen_type: string;
  container_type: string;
  price: string;
  is_panel: boolean;
  validation_status: string;
  status: string;
  parameters: Parameter[];
};

type ImportSummary = {
  rows_received: number;
  tests_created: number;
  tests_updated: number;
  parameters_imported: number;
  rows_rejected: number;
  review_required: number;
  errors: string[];
};

function money(value: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) return value;
  return `₹${amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

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
  const [tab, setTab] = useState<"meta" | "parameters">("meta");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const query = new URLSearchParams({ limit: "100", offset: "0" });
      if (search.trim()) query.set("search", search.trim());
      if (reviewOnly) query.set("review_only", "true");
      const result = await api<Page<TestMaster>>(`/test-master?${query}`);
      setRecords(result.items);
      setTotal(result.total);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the test master");
    } finally {
      setLoading(false);
    }
  }, [search, reviewOnly]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function refreshEditing(code: string, id: string) {
    const refreshed = await api<Page<TestMaster>>(
      `/test-master?search=${encodeURIComponent(code)}&limit=5&offset=0`
    );
    const next = refreshed.items.find((item) => item.id === id) ?? null;
    setEditing(next);
    await load();
    return next;
  }

  async function upload(file: File) {
    const data = new FormData();
    data.append("file", file);
    try {
      setUploading(true);
      setError("");
      const result = await api<ImportSummary>("/test-master/import", { method: "POST", body: data });
      setSummary(result);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Import failed");
    } finally {
      setUploading(false);
    }
  }

  async function saveMeta(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = new FormData(event.currentTarget);
    const payload = {
      name: String(data.get("name") || "").trim(),
      service_type: String(data.get("service_type") || "").trim(),
      department: String(data.get("department") || "").trim(),
      sub_department: String(data.get("sub_department") || "").trim(),
      specimen_type: String(data.get("specimen_type") || "").trim(),
      container_type: String(data.get("container_type") || "").trim(),
      price: String(data.get("price") || "0").trim(),
    };
    try {
      setSaving(true);
      setError("");
      await api(`/test-master/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await refreshEditing(editing.code, editing.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save test metadata");
    } finally {
      setSaving(false);
    }
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
      critical_low: String(data.get("critical_low") || "").trim() || null,
      critical_high: String(data.get("critical_high") || "").trim() || null,
      reference_source: String(data.get("reference_source") || "").trim() || null,
    };
    const parameterId = String(data.get("parameter_id") || "");
    try {
      setSaving(true);
      setError("");
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
      await refreshEditing(editing.code, editing.id);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save parameter");
    } finally {
      setSaving(false);
    }
  }

  function openEditor(item: TestMaster, nextTab: "meta" | "parameters" = "meta") {
    setEditing(item);
    setTab(nextTab);
  }

  return (
    <section>
      <div className="page-heading test-master-heading">
        <div>
          <p className="eyebrow">LIS · HIS CONFIGURATION</p>
          <h1>Test master</h1>
          <p>Manage orderable services, specimen/container pricing, and clinical reference limits.</p>
        </div>
        {can("test_master.manage") && (
          <label className="primary upload-button">
            <Upload size={17} />
            {uploading ? "Importing…" : "Import Excel"}
            <input
              aria-label="Import LIS HIS test master"
              type="file"
              accept=".xlsx"
              disabled={uploading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
                event.target.value = "";
              }}
            />
          </label>
        )}
      </div>

      {summary && (
        <div className="import-summary panel">
          <CheckCircle2 size={22} />
          <div>
            <strong>Workbook imported</strong>
            <p>
              {summary.rows_received} rows · {summary.tests_created} created · {summary.tests_updated}{" "}
              updated · {summary.parameters_imported} parameters
            </p>
          </div>
          <div className="import-flags">
            <span>{summary.review_required} need review</span>
            <span>{summary.rows_rejected} rejected</span>
          </div>
        </div>
      )}
      {error && (
        <div className="error-state">
          <AlertCircle size={18} />
          {error}
          <button onClick={() => void load()}>Retry</button>
        </div>
      )}

      <div className="test-master-metrics">
        <article>
          <FileSpreadsheet />
          <span>
            <strong>{total}</strong>
            <small>matching services</small>
          </span>
        </article>
        <article>
          <strong>{records.filter((item) => item.is_panel).length}</strong>
          <small>panels in view</small>
        </article>
        <article className="review-metric">
          <strong>{records.filter((item) => item.validation_status === "needs_review").length}</strong>
          <small>need review in view</small>
        </article>
      </div>

      <div className="panel">
        <div className="toolbar test-master-toolbar">
          <label className="search">
            <Search size={17} />
            <input
              aria-label="Search test master"
              placeholder="Code, test, department, specimen…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="review-toggle">
            <input
              type="checkbox"
              checked={reviewOnly}
              onChange={(event) => setReviewOnly(event.target.checked)}
            />{" "}
            Needs review only
          </label>
        </div>
        {loading ? (
          <div className="loading" aria-label="Loading">
            <i />
            <i />
            <i />
          </div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <span>0</span>
            <h3>No tests found</h3>
            <p>Import the LIS/HIS workbook or change the current filters.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="test-master-table">
              <thead>
                <tr>
                  <th>Code & service</th>
                  <th>Specimen meta</th>
                  <th>Price</th>
                  <th>Parameters</th>
                  <th>Review</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.code}</strong>
                      <span>{item.name}</span>
                      <span>
                        {item.sub_department || item.department} · {item.service_type}
                      </span>
                    </td>
                    <td>
                      <strong>{item.specimen_type}</strong>
                      <span>{item.container_type}</span>
                    </td>
                    <td>
                      <strong>{money(item.price)}</strong>
                    </td>
                    <td>
                      {item.parameters.length > 0 ? (
                        <>
                          <strong>{item.parameters.length} parameters</strong>
                          <span>
                            {item.parameters
                              .slice(0, 2)
                              .map((parameter) =>
                                parameter.reference_low || parameter.reference_high
                                  ? `${parameter.external_code} ${parameter.reference_low ?? "…"}–${parameter.reference_high ?? "…"}`
                                  : parameter.external_code
                              )
                              .join(", ")}
                            {item.parameters.length > 2 ? "…" : ""}
                          </span>
                        </>
                      ) : (
                        <span>No parameters</span>
                      )}
                    </td>
                    <td>
                      <span className={`mapping-status ${item.validation_status}`}>
                        {item.validation_status === "needs_review" ? "Needs review" : "Validated"}
                      </span>
                    </td>
                    <td>
                      {can("test_master.manage") && (
                        <div className="row-actions">
                          <button className="mapping-button" onClick={() => openEditor(item, "meta")}>
                            Edit meta
                          </button>
                          <button
                            className="mapping-button"
                            onClick={() => openEditor(item, "parameters")}
                          >
                            Ranges
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span>
            Showing {records.length} of {total}
          </span>
          <span>First 100 matching records</span>
        </div>
      </div>

      {editing && (
        <div className="modal-backdrop">
          <section className="modal mapping-modal">
            <div className="modal-head">
              <div>
                <p className="eyebrow">TEST MASTER</p>
                <h2>{editing.code}</h2>
                <small>{editing.name}</small>
              </div>
              <button aria-label="Close editor" onClick={() => setEditing(null)}>
                ×
              </button>
            </div>
            <div className="test-master-tabs">
              <button
                type="button"
                className={tab === "meta" ? "active" : ""}
                onClick={() => setTab("meta")}
              >
                Specimen & price
              </button>
              <button
                type="button"
                className={tab === "parameters" ? "active" : ""}
                onClick={() => setTab("parameters")}
              >
                Clinical ranges
              </button>
            </div>
            {tab === "meta" ? (
              <form className="test-master-meta-form" onSubmit={saveMeta}>
                <label>
                  Service name *
                  <input name="name" required maxLength={200} defaultValue={editing.name} />
                </label>
                <div className="analyzer-form-grid">
                  <label>
                    Service type
                    <input
                      name="service_type"
                      required
                      maxLength={80}
                      defaultValue={editing.service_type}
                    />
                  </label>
                  <label>
                    Department
                    <input
                      name="department"
                      required
                      maxLength={120}
                      defaultValue={editing.department}
                    />
                  </label>
                  <label>
                    Sub-department
                    <input
                      name="sub_department"
                      maxLength={120}
                      defaultValue={editing.sub_department}
                    />
                  </label>
                  <label>
                    Price (INR) *
                    <input
                      name="price"
                      type="number"
                      min={0}
                      step="0.01"
                      required
                      defaultValue={editing.price}
                    />
                  </label>
                  <label>
                    Specimen type *
                    <input
                      name="specimen_type"
                      required
                      maxLength={80}
                      defaultValue={editing.specimen_type}
                      placeholder="Serum"
                    />
                  </label>
                  <label>
                    Container type *
                    <input
                      name="container_type"
                      required
                      maxLength={100}
                      defaultValue={editing.container_type}
                      placeholder="SST clot activator"
                    />
                  </label>
                </div>
                <p className="configuration-note">
                  Placeholder specimen/container values or zero price keep the test in Needs review.
                </p>
                <div className="form-actions">
                  <button type="button" onClick={() => setEditing(null)}>
                    Close
                  </button>
                  <button className="primary" disabled={saving}>
                    {saving ? "Saving…" : "Save metadata"}
                  </button>
                </div>
              </form>
            ) : (
              <div className="mapping-layout">
                <aside>
                  <h3>Existing parameters</h3>
                  {editing.parameters.length === 0 ? (
                    <p>No parameters yet.</p>
                  ) : (
                    editing.parameters.map((parameter) => (
                      <div key={parameter.id} className="mapping-chip-row">
                        <button
                          type="button"
                          className="active"
                          onClick={() => {
                            const form = document.getElementById(
                              "parameter-form"
                            ) as HTMLFormElement | null;
                            if (!form) return;
                            (form.elements.namedItem("parameter_id") as HTMLInputElement).value =
                              parameter.id;
                            (form.elements.namedItem("name") as HTMLInputElement).value =
                              parameter.name;
                            (form.elements.namedItem("external_code") as HTMLInputElement).value =
                              parameter.external_code;
                            (form.elements.namedItem("display_order") as HTMLInputElement).value =
                              String(parameter.display_order);
                            (form.elements.namedItem("unit") as HTMLInputElement).value =
                              parameter.unit ?? "";
                            (form.elements.namedItem("reference_low") as HTMLInputElement).value =
                              parameter.reference_low ?? "";
                            (form.elements.namedItem("reference_high") as HTMLInputElement).value =
                              parameter.reference_high ?? "";
                            (form.elements.namedItem("reference_text") as HTMLInputElement).value =
                              parameter.reference_text ?? "";
                            (form.elements.namedItem("critical_low") as HTMLInputElement).value =
                              parameter.critical_low ?? "";
                            (form.elements.namedItem("critical_high") as HTMLInputElement).value =
                              parameter.critical_high ?? "";
                            (form.elements.namedItem("reference_source") as HTMLInputElement).value =
                              parameter.reference_source ?? "";
                          }}
                        >
                          <strong>{parameter.external_code}</strong>
                          <span>
                            {parameter.name}
                            {parameter.unit ? ` · ${parameter.unit}` : ""}
                            {parameter.reference_low || parameter.reference_high
                              ? ` · ${parameter.reference_low ?? "…"}–${parameter.reference_high ?? "…"}`
                              : ""}
                          </span>
                        </button>
                      </div>
                    ))
                  )}
                </aside>
                <form id="parameter-form" onSubmit={saveParameter}>
                  <input type="hidden" name="parameter_id" defaultValue="" />
                  <label>
                    Parameter name *
                    <input name="name" required maxLength={200} />
                  </label>
                  <label>
                    External code *
                    <input name="external_code" required maxLength={255} placeholder="ANDRO" />
                  </label>
                  <div className="analyzer-form-grid">
                    <label>
                      Display order
                      <input name="display_order" type="number" min={0} defaultValue={0} />
                    </label>
                    <label>
                      Unit
                      <input name="unit" maxLength={40} placeholder="ng/mL" />
                    </label>
                    <label>
                      Reference low
                      <input name="reference_low" maxLength={40} />
                    </label>
                    <label>
                      Reference high
                      <input name="reference_high" maxLength={40} />
                    </label>
                    <label>
                      Critical low
                      <input name="critical_low" maxLength={40} />
                    </label>
                    <label>
                      Critical high
                      <input name="critical_high" maxLength={40} />
                    </label>
                  </div>
                  <label>
                    Reference text
                    <input
                      name="reference_text"
                      maxLength={200}
                      placeholder="Optional qualitative range note"
                    />
                  </label>
                  <label>
                    Approved source *
                    <input
                      name="reference_source"
                      maxLength={200}
                      placeholder="Lab method sheet / package insert / pathologist memo"
                    />
                  </label>
                  <p className="configuration-note">
                    Enter limits only with an approved laboratory source. Values without a source stay
                    in Needs review. Critical limits raise LL/HH flags during normalization.
                  </p>
                  <div className="form-actions">
                    <button type="button" onClick={() => setEditing(null)}>
                      Close
                    </button>
                    <button className="primary" disabled={saving}>
                      {saving ? "Saving…" : "Save parameter"}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}

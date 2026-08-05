"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileText, Search } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";
import { readBrowserAccessToken } from "@/lib/session";

type Observation = {
  id: string;
  sequence_no: number;
  machine_parameter_code: string;
  parameter_name: string;
  value: string;
  unit: string | null;
  reference_low: string | null;
  reference_high: string | null;
  reference_text: string | null;
  flag: string | null;
};

type LabResult = {
  id: string;
  specimen_barcode: string;
  accession_number: string | null;
  order_number: string;
  patient_number: string;
  patient_name: string;
  lis_test_code: string;
  test_name: string;
  analyzer_code: string;
  status: string;
  report_number: string | null;
  technical_review_notes: string | null;
  pathologist_notes: string | null;
  released_at: string | null;
  observations: Observation[];
  created_at: string;
};

const statusLabel: Record<string, string> = {
  pending_review: "Pending review",
  technically_reviewed: "Technically reviewed",
  pathologist_validated: "Pathologist validated",
  released: "Released",
};

export default function ResultsPage() {
  const [items, setItems] = useState<LabResult[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [selected, setSelected] = useState<LabResult | null>(null);
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const query = new URLSearchParams({ limit: "50", offset: "0" });
      if (status) query.set("status", status);
      const page = await api<Page<LabResult>>(`/results?${query}`);
      setItems(page.items);
      setTotal(page.total);
      setError("");
      setSelected((current) =>
        current ? page.items.find((item) => item.id === current.id) ?? current : null
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load results");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function act(path: string, body?: object) {
    if (!selected) return;
    try {
      setBusyId(selected.id);
      setError("");
      const updated = await api<LabResult>(path, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      });
      setSelected(updated);
      setNotes("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update result");
    } finally {
      setBusyId("");
    }
  }

  async function downloadPdf() {
    if (!selected) return;
    try {
      setBusyId(selected.id);
      const token = readBrowserAccessToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/results/${selected.id}/pdf`,
        {
          headers: token
            ? { Authorization: `Bearer ${token}` }
            : process.env.NEXT_PUBLIC_DEV_AUTH_HEADER === "true"
              ? {
                  "X-Dev-User-Email":
                    process.env.NEXT_PUBLIC_DEV_AUTH_EMAIL?.trim() || "admin@dev.labora.local"
                }
              : {}
        }
      );
      if (!response.ok) throw new Error("Unable to download PDF");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${selected.report_number || selected.id}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to download PDF");
    } finally {
      setBusyId("");
    }
  }

  function onNotesSubmit(event: FormEvent) {
    event.preventDefault();
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CLINICAL RESULTS</p>
          <h1>Results</h1>
          <p>Normalize analyzer ORU values, review, validate, release, and download PDFs.</p>
        </div>
      </div>
      {error && (
        <div className="error-state">
          <AlertCircle size={18} />
          {error}
          <button onClick={() => void load()}>Retry</button>
        </div>
      )}
      <div className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={17} />
            <select
              aria-label="Filter result status"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {Object.entries(statusLabel).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <span>{total} results</span>
        </div>
        {loading ? (
          <div className="loading">
            <i />
            <i />
            <i />
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <FileText />
            <h3>No results yet</h3>
            <p>Process an HL7 order with an ORU response, then normalize from the worklist.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Specimen</th>
                  <th>Test</th>
                  <th>Analyzer</th>
                  <th>Status</th>
                  <th>Report</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.patient_name}</strong>
                      <span>{item.patient_number}</span>
                    </td>
                    <td>
                      <code>{item.specimen_barcode}</code>
                      <span>{item.accession_number || "—"}</span>
                    </td>
                    <td>
                      <strong>{item.lis_test_code}</strong>
                      <span>{item.test_name}</span>
                    </td>
                    <td>{item.analyzer_code}</td>
                    <td>
                      <span className={`status ${item.status}`}>
                        {statusLabel[item.status] ?? item.status}
                      </span>
                    </td>
                    <td>{item.report_number || "—"}</td>
                    <td>
                      <button className="mapping-button" onClick={() => setSelected(item)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <div className="modal-backdrop">
          <section className="modal mapping-modal">
            <div className="modal-head">
              <div>
                <p className="eyebrow">RESULT REVIEW</p>
                <h2>
                  {selected.lis_test_code} · {selected.patient_name}
                </h2>
                <small>
                  {selected.specimen_barcode} · {statusLabel[selected.status] ?? selected.status}
                </small>
              </div>
              <button aria-label="Close result" onClick={() => setSelected(null)}>
                ×
              </button>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                    <th>Unit</th>
                    <th>Flag</th>
                    <th>Reference</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.observations.map((observation) => (
                    <tr key={observation.id}>
                      <td>
                        <strong>{observation.parameter_name}</strong>
                        <span>{observation.machine_parameter_code}</span>
                      </td>
                      <td>{observation.value}</td>
                      <td>{observation.unit || "—"}</td>
                      <td>{observation.flag || "—"}</td>
                      <td>
                        {observation.reference_text ||
                          (observation.reference_low || observation.reference_high
                            ? `${observation.reference_low ?? ""} – ${observation.reference_high ?? ""}`
                            : "—")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <form onSubmit={onNotesSubmit}>
              <label>
                Review notes
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder="Optional notes for technical or pathologist review"
                />
              </label>
            </form>
            <div className="form-actions">
              <button type="button" onClick={() => setSelected(null)}>
                Close
              </button>
              {can("result.review") && selected.status === "pending_review" && (
                <button
                  className="primary"
                  disabled={busyId === selected.id}
                  onClick={() =>
                    void act(`/results/${selected.id}/technical-review`, { notes: notes || null })
                  }
                >
                  Technical review
                </button>
              )}
              {can("result.validate") && selected.status === "technically_reviewed" && (
                <button
                  className="primary"
                  disabled={busyId === selected.id}
                  onClick={() =>
                    void act(`/results/${selected.id}/pathologist-validate`, {
                      notes: notes || null,
                    })
                  }
                >
                  Pathologist validate
                </button>
              )}
              {can("result.release") && selected.status === "pathologist_validated" && (
                <button
                  className="primary"
                  disabled={busyId === selected.id}
                  onClick={() => void act(`/results/${selected.id}/release`)}
                >
                  Release report
                </button>
              )}
              {selected.status === "released" && (
                <button
                  className="primary"
                  disabled={busyId === selected.id}
                  onClick={() => void downloadPdf()}
                >
                  <CheckCircle2 size={16} /> Download PDF
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

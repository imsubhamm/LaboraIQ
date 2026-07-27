"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Plus, Search, X } from "lucide-react";
import { api, ApiRecord, Page } from "@/lib/api";
import type { Permission } from "@/lib/auth";
import { can } from "@/lib/auth";

type Field = { name: string; label: string; required?: boolean; type?: string };

export function ResourcePage({
  title, description, endpoint, columns, fields = [], managePermission, emptyMessage
}: {
  title: string; description: string; endpoint: string;
  columns: Array<{ key: string; label: string }>;
  fields?: Field[]; managePermission?: Permission; emptyMessage: string;
}) {
  const [records, setRecords] = useState<ApiRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(false);

  const load = useCallback(async function load() {
    try {
      setLoading(true);
      const result = await api<Page<ApiRecord>>(`/${endpoint}?limit=25&offset=0`);
      setRecords(result.items);
      setTotal(result.total);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load records");
    } finally { setLoading(false); }
  }, [endpoint]);
  useEffect(() => {
    const task = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(task);
  }, [load]);

  async function submit(formData: FormData) {
    const payload = Object.fromEntries(formData.entries());
    try {
      await api(`/${endpoint}`, { method: "POST", body: JSON.stringify(payload) });
      setOpen(false);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save"); }
  }

  const filtered = records.filter((record) =>
    Object.values(record).some((value) => String(value ?? "").toLowerCase().includes(filter.toLowerCase()))
  );
  return (
    <section>
      <div className="page-heading">
        <div><p className="eyebrow">PLATFORM FOUNDATION</p><h1>{title}</h1><p>{description}</p></div>
        {fields.length > 0 && (!managePermission || can(managePermission)) &&
          <button className="primary" onClick={() => setOpen(true)}><Plus size={17}/> Add {title.replace(/s$/, "")}</button>}
      </div>
      <div className="panel">
        <div className="toolbar">
          <label className="search"><Search size={17}/><input aria-label={`Filter ${title}`} placeholder={`Filter ${title.toLowerCase()}…`} value={filter} onChange={e => setFilter(e.target.value)}/></label>
          <span>{total} records</span>
        </div>
        {error && <div className="error-state"><AlertCircle size={18}/>{error}<button onClick={load}>Retry</button></div>}
        {loading ? <div className="loading" aria-label="Loading"><i/><i/><i/></div> :
          filtered.length === 0 ? <div className="empty-state"><span>0</span><h3>No records found</h3><p>{emptyMessage}</p></div> :
          <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead>
          <tbody>{filtered.map((record, index) => <tr key={String(record.id ?? index)}>{columns.map(c =>
            <td key={c.key}>{c.key === "status" ? <span className={`status ${record[c.key]}`}>{String(record[c.key])}</span> : String(record[c.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>}
        <div className="pagination"><span>Showing {filtered.length} of {total}</span><div><button disabled>Previous</button><button disabled={total <= 25}>Next</button></div></div>
      </div>
      {open && <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="form-title">
        <div className="modal-head"><div><p className="eyebrow">NEW CONFIGURATION</p><h2 id="form-title">Add {title.replace(/s$/, "")}</h2></div><button aria-label="Close form" onClick={() => setOpen(false)}><X/></button></div>
        <form action={submit}>{fields.map(field => <label key={field.name}>{field.label}<input name={field.name} type={field.type ?? "text"} required={field.required}/></label>)}
          <div className="form-actions"><button type="button" onClick={() => setOpen(false)}>Cancel</button><button className="primary" type="submit">Save configuration</button></div>
        </form>
      </section></div>}
    </section>
  );
}

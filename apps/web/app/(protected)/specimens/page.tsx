"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, FlaskConical, PackageCheck, ScanBarcode, Search, X } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Specimen = {
  id:string; barcode:string; specimen_type:string; container_type:string; status:string;
  order_number:string; patient_number:string; patient_name:string;
  laboratory_department:string|null; accession_number:string|null;
  collection_location:string|null; container_count:number; collected_at:string|null;
  received_at:string|null; reviewed_at:string|null; rejection_reason:string|null;
};
type Action = "collect" | "reject" | null;

const statuses = ["", "awaiting_collection", "collected", "received", "accepted", "rejected"];
const rejectionReasons = ["Wrong container", "Insufficient quantity", "Haemolysed", "Clotted", "Leaking container", "Mislabeled or unlabeled", "Delayed transport", "Incorrect specimen", "Other"];

export default function SpecimensPage() {
  const [records,setRecords] = useState<Specimen[]>([]);
  const [total,setTotal] = useState(0);
  const [search,setSearch] = useState("");
  const [status,setStatus] = useState("");
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState("");
  const [selected,setSelected] = useState<Specimen|null>(null);
  const [action,setAction] = useState<Action>(null);
  const [saving,setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const query = new URLSearchParams({limit:"50",offset:"0"});
      if(search.trim()) query.set("search",search.trim());
      if(status) query.set("status",status);
      const result = await api<Page<Specimen>>(`/specimens?${query}`);
      setRecords(result.items); setTotal(result.total); setError("");
    } catch(reason) { setError(reason instanceof Error ? reason.message : "Unable to load specimens"); }
    finally { setLoading(false); }
  },[search,status]);
  useEffect(()=>{ const timer=window.setTimeout(()=>void load(),200); return()=>window.clearTimeout(timer); },[load]);

  async function transition(specimen:Specimen, endpoint:string, body?:object) {
    try {
      setSaving(true); setError("");
      await api(`/specimens/${encodeURIComponent(specimen.barcode)}/${endpoint}`,{method:"POST",body:body ? JSON.stringify(body) : undefined});
      setSelected(null); setAction(null); await load();
    } catch(reason) { setError(reason instanceof Error ? reason.message : "Unable to update specimen"); }
    finally { setSaving(false); }
  }

  function open(specimen:Specimen,next:Action){setSelected(specimen);setAction(next);}
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault(); if(!selected||!action)return;
    const data=new FormData(event.currentTarget);
    if(action==="collect") await transition(selected,"collect",{collection_location:data.get("location"),container_count:Number(data.get("count")),collection_notes:data.get("notes")||null});
    else await transition(selected,"decision",{decision:"reject",rejection_reason:data.get("reason"),notes:data.get("notes")||null});
  }

  return <section>
    <div className="page-heading"><div><p className="eyebrow">PRE-ANALYTICAL WORKFLOW</p><h1>Specimens</h1><p>Scan, collect, receive, accession, and review laboratory specimens.</p></div></div>
    <div className="specimen-metrics">
      <article><ScanBarcode/><span><strong>{total}</strong><small>specimens in view</small></span></article>
      <article><strong>{records.filter(item=>item.status==="awaiting_collection").length}</strong><small>awaiting collection</small></article>
      <article><strong>{records.filter(item=>item.status==="received").length}</strong><small>awaiting review</small></article>
    </div>
    {error&&<div className="error-state"><AlertCircle size={18}/>{error}<button onClick={()=>void load()}>Retry</button></div>}
    <div className="panel">
      <div className="toolbar specimen-toolbar">
        <label className="search"><Search size={17}/><input aria-label="Scan or search specimens" autoFocus placeholder="Scan barcode, accession, patient, or order…" value={search} onChange={event=>setSearch(event.target.value)}/></label>
        <select aria-label="Filter specimen status" value={status} onChange={event=>setStatus(event.target.value)}>{statuses.map(value=><option value={value} key={value}>{value?value.replaceAll("_"," "):"All statuses"}</option>)}</select>
      </div>
      {loading?<div className="loading"><i/><i/><i/></div>:records.length===0?<div className="empty-state"><span>0</span><h3>No specimens found</h3><p>Generate a barcode after payment or change the filters.</p></div>:
      <div className="table-wrap"><table className="specimen-table"><thead><tr><th>Barcode</th><th>Patient & order</th><th>Specimen</th><th>Department</th><th>Status</th><th>Action</th></tr></thead><tbody>
        {records.map(item=><tr key={item.id}><td><strong>{item.barcode}</strong><span>{item.accession_number||"Not accessioned"}</span></td><td><strong>{item.patient_name}</strong><span>{item.patient_number} · {item.order_number}</span></td><td><strong>{item.specimen_type}</strong><span>{item.container_type} · {item.container_count} container(s)</span></td><td>{item.laboratory_department||"Unassigned"}</td><td><span className={`workflow-status ${item.status}`}>{item.status.replaceAll("_"," ")}</span>{item.rejection_reason&&<small>{item.rejection_reason}</small>}</td><td><div className="row-actions">{can("branch.manage")&&item.status==="awaiting_collection"&&<button onClick={()=>open(item,"collect")}>Collect</button>}{can("branch.manage")&&item.status==="collected"&&<button onClick={()=>void transition(item,"receive")}>Receive</button>}{can("branch.manage")&&item.status==="received"&&<><button className="accept" onClick={()=>void transition(item,"decision",{decision:"accept"})}>Accept</button><button className="reject" onClick={()=>open(item,"reject")}>Reject</button></>}</div></td></tr>)}
      </tbody></table></div>}
      <div className="pagination"><span>Showing {records.length} of {total}</span><span>Latest 50 matching specimens</span></div>
    </div>
    {selected&&action&&<div className="modal-backdrop"><section className="modal"><div className="modal-head"><div><p className="eyebrow">{action==="collect"?"COLLECTION":"REJECTION"}</p><h2>{selected.barcode}</h2></div><button aria-label="Close" onClick={()=>{setSelected(null);setAction(null)}}><X/></button></div><form onSubmit={submit}>
      {action==="collect"?<><label>Collection location<input name="location" required defaultValue="Collection desk"/></label><label>Number of containers<input name="count" type="number" min="1" max="20" required defaultValue="1"/></label></>:<label>Rejection reason<select name="reason" required defaultValue=""><option value="" disabled>Select reason</option>{rejectionReasons.map(reason=><option key={reason}>{reason}</option>)}</select></label>}
      <label>Notes<textarea name="notes" rows={3} placeholder="Optional notes"/></label><div className="form-actions"><button type="button" onClick={()=>{setSelected(null);setAction(null)}}>Cancel</button><button className="primary" disabled={saving}>{action==="collect"?<><PackageCheck size={16}/>Record collection</>:<><FlaskConical size={16}/>Reject specimen</>}</button></div>
    </form></section></div>}
  </section>;
}

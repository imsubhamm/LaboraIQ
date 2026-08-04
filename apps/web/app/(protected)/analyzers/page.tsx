"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, Cpu, Network, Plus, Search, X } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Analyzer = { id:string; branch_id:string; code:string; vendor:string; model:string; protocol:string; host:string; port:number; connection_mode:string; status:string };
type Branch = { id:string; code:string; name:string };

const protocolLabels:Record<string,string> = { ASTM:"ASTM / CLSI LIS01–LIS02", HL7_LAW:"HL7 v2.5.1 / IHE LAW", PROPRIETARY:"Vendor proprietary" };

export default function AnalyzersPage() {
  const [records,setRecords]=useState<Analyzer[]>([]);
  const [branches,setBranches]=useState<Branch[]>([]);
  const [total,setTotal]=useState(0);
  const [filter,setFilter]=useState("");
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [open,setOpen]=useState(false);
  const [saving,setSaving]=useState(false);

  const load=useCallback(async()=>{
    try {
      setLoading(true);
      const [machines,branchPage]=await Promise.all([api<Page<Analyzer>>("/analyzers?limit=100&offset=0"),api<Page<Branch>>("/branches?limit=100&offset=0")]);
      setRecords(machines.items); setTotal(machines.total); setBranches(branchPage.items); setError("");
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to load analyzers");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);

  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault(); const data=new FormData(event.currentTarget);
    try {
      setSaving(true); setError("");
      await api("/analyzers",{method:"POST",body:JSON.stringify({branch_id:data.get("branch_id"),code:String(data.get("code")).trim().toUpperCase(),vendor:data.get("vendor"),model:data.get("model"),protocol:data.get("protocol"),host:String(data.get("host")).trim(),port:Number(data.get("port")),connection_mode:data.get("connection_mode")})});
      setOpen(false); await load();
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to save analyzer");}
    finally{setSaving(false);}
  }
  const shown=records.filter(item=>`${item.code} ${item.vendor} ${item.model} ${item.host}`.toLowerCase().includes(filter.toLowerCase()));
  const branchName=(id:string)=>{const branch=branches.find(item=>item.id===id);return branch?`${branch.name} · ${branch.code}`:"Unknown branch"};

  return <section>
    <div className="page-heading"><div><p className="eyebrow">INSTRUMENT INTERFACE</p><h1>Analyzers</h1><p>Configure laboratory machines and the network protocol used to exchange orders and results.</p></div>{can("analyzer.manage")&&<button className="primary" onClick={()=>setOpen(true)}><Plus size={17}/> Add analyzer</button>}</div>
    <div className="analyzer-metrics"><article><Cpu/><span><strong>{total}</strong><small>configured analyzers</small></span></article><article><Network/><span><strong>{records.filter(item=>item.status==="active").length}</strong><small>active connections</small></span></article></div>
    {error&&<div className="error-state"><AlertCircle size={18}/>{error}<button onClick={()=>void load()}>Retry</button></div>}
    <div className="panel"><div className="toolbar"><label className="search"><Search size={17}/><input aria-label="Filter analyzers" placeholder="Filter by code, vendor, model, or IP…" value={filter} onChange={event=>setFilter(event.target.value)}/></label><span>{total} records</span></div>
      {loading?<div className="loading"><i/><i/><i/></div>:shown.length===0?<div className="empty-state"><Cpu/><h3>No analyzers configured</h3><p>Add the first analyzer using its manufacturer interface manual.</p></div>:<div className="table-wrap"><table className="analyzer-table"><thead><tr><th>Analyzer</th><th>Branch</th><th>Protocol</th><th>Network endpoint</th><th>Mode</th><th>Status</th></tr></thead><tbody>{shown.map(item=><tr key={item.id}><td><strong>{item.vendor} {item.model}</strong><span>{item.code}</span></td><td>{branchName(item.branch_id)}</td><td>{protocolLabels[item.protocol]??item.protocol}</td><td><code>{item.host}:{item.port}</code></td><td>{item.connection_mode}</td><td><span className={`status ${item.status}`}>{item.status}</span></td></tr>)}</tbody></table></div>}
      <div className="pagination"><span>Showing {shown.length} of {total}</span></div>
    </div>
    {open&&<div className="modal-backdrop"><section className="modal analyzer-modal"><div className="modal-head"><div><p className="eyebrow">NEW CONNECTION</p><h2>Configure analyzer</h2></div><button aria-label="Close" onClick={()=>setOpen(false)}><X/></button></div><form onSubmit={submit}>
      <label>Branch *<select name="branch_id" required defaultValue=""><option value="" disabled>Select branch</option>{branches.map(branch=><option key={branch.id} value={branch.id}>{branch.name} · {branch.code}</option>)}</select></label>
      <div className="analyzer-form-grid"><label>Machine code *<input name="code" required minLength={2} maxLength={40} placeholder="HEM-01" pattern="[A-Za-z0-9_-]+"/></label><label>Vendor *<input name="vendor" required placeholder="e.g. Sysmex"/></label><label>Model *<input name="model" required placeholder="e.g. XN-1000"/></label><label>Protocol *<select name="protocol" required defaultValue=""><option value="" disabled>Select from interface manual</option>{Object.entries(protocolLabels).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label><label>IP address *<input name="host" required inputMode="decimal" placeholder="192.168.1.50"/></label><label>Port *<input name="port" required type="number" min="1" max="65535" placeholder="5000"/></label><label>Communication *<select name="connection_mode" defaultValue="bidirectional"><option value="bidirectional">Bidirectional (orders + results)</option><option value="unidirectional">Unidirectional (results only)</option></select></label></div>
      <p className="configuration-note">Use the static IP, port, and protocol from the analyzer interface manual. Saving this record does not open a machine connection yet.</p>
      <div className="form-actions"><button type="button" onClick={()=>setOpen(false)}>Cancel</button><button className="primary" disabled={saving}>{saving?"Saving…":"Save analyzer"}</button></div>
    </form></section></div>}
  </section>;
}

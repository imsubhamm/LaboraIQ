"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Activity, AlertCircle, Cable, Cpu, Network, Plus, Search, Trash2, X } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type Analyzer = { id:string; branch_id:string; code:string; vendor:string; model:string; protocol:string; host:string; port:number; connection_mode:string; status:string; connection_status:string; connection_timeout_seconds:number; retry_limit:number; heartbeat_interval_seconds:number; last_connection_test_at:string|null; last_connected_at:string|null; last_connection_error:string|null };
type Branch = { id:string; code:string; name:string };
type TestParameter = { id:string; name:string; external_code:string };
type LisTest = { id:string; code:string; name:string; parameters:TestParameter[] };
type ParameterMapping = { id:string; parameter_id:string; parameter_name:string; lis_parameter_code:string; machine_parameter_code:string; unit:string|null };
type TestMapping = { id:string; test_id:string; lis_test_code:string; test_name:string; machine_test_code:string; status:string; parameters:ParameterMapping[] };
type ConnectionEvent = { id:string; event_type:string; attempt:number; success:boolean; latency_ms:number|null; message:string; correlation_id:string; occurred_at:string };
type ConnectionResult = { connection_status:string; attempts:number; success:boolean; latency_ms:number|null; message:string; tested_at:string };

const protocolLabels:Record<string,string> = { ASTM:"ASTM / CLSI LIS01–LIS02", HL7_LAW:"HL7 v2.5.1 / IHE LAW", PROPRIETARY:"Vendor proprietary" };

export default function AnalyzersPage() {
  const [records,setRecords]=useState<Analyzer[]>([]);
  const [branches,setBranches]=useState<Branch[]>([]);
  const [tests,setTests]=useState<LisTest[]>([]);
  const [total,setTotal]=useState(0);
  const [filter,setFilter]=useState("");
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [open,setOpen]=useState(false);
  const [saving,setSaving]=useState(false);
  const [mappingAnalyzer,setMappingAnalyzer]=useState<Analyzer|null>(null);
  const [mappings,setMappings]=useState<TestMapping[]>([]);
  const [selectedTestId,setSelectedTestId]=useState("");
  const [testSearch,setTestSearch]=useState("");
  const [searchingTests,setSearchingTests]=useState(false);
  const [connectionAnalyzer,setConnectionAnalyzer]=useState<Analyzer|null>(null);
  const [connectionEvents,setConnectionEvents]=useState<ConnectionEvent[]>([]);
  const [testingConnection,setTestingConnection]=useState(false);
  const [connectionResult,setConnectionResult]=useState<ConnectionResult|null>(null);

  const load=useCallback(async()=>{
    try {
      setLoading(true);
      const [machines,branchPage]=await Promise.all([
        api<Page<Analyzer>>("/analyzers?limit=100&offset=0"),
        api<Page<Branch>>("/branches?limit=100&offset=0"),
      ]);
      setRecords(machines.items); setTotal(machines.total); setBranches(branchPage.items); setError("");
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to load analyzers");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
  useEffect(()=>{
    if(!mappingAnalyzer)return;
    let active=true;
    const timer=window.setTimeout(async()=>{
      try {
        setSearchingTests(true);
        const query=new URLSearchParams({limit:"100",offset:"0"});
        if(testSearch.trim())query.set("search",testSearch.trim());
        const page=await api<Page<LisTest>>(`/test-master?${query}`);
        if(active)setTests(page.items);
      } catch(reason){if(active)setError(reason instanceof Error?reason.message:"Unable to search LIS tests");}
      finally{if(active)setSearchingTests(false);}
    },250);
    return()=>{active=false;window.clearTimeout(timer)};
  },[mappingAnalyzer,testSearch]);

  async function submitAnalyzer(event:FormEvent<HTMLFormElement>){
    event.preventDefault(); const data=new FormData(event.currentTarget);
    try {
      setSaving(true); setError("");
      await api("/analyzers",{method:"POST",body:JSON.stringify({branch_id:data.get("branch_id"),code:String(data.get("code")).trim().toUpperCase(),vendor:data.get("vendor"),model:data.get("model"),protocol:data.get("protocol"),host:String(data.get("host")).trim(),port:Number(data.get("port")),connection_mode:data.get("connection_mode"),connection_timeout_seconds:Number(data.get("connection_timeout_seconds")),retry_limit:Number(data.get("retry_limit")),heartbeat_interval_seconds:Number(data.get("heartbeat_interval_seconds"))})});
      setOpen(false); await load();
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to save analyzer");}
    finally{setSaving(false);}
  }

  async function openMappings(analyzer:Analyzer){
    try {
      setError(""); setMappingAnalyzer(analyzer); setSelectedTestId(""); setTestSearch(""); setTests([]);
      setMappings(await api<TestMapping[]>(`/analyzers/${analyzer.id}/mappings`));
    } catch(reason){setMappingAnalyzer(null);setError(reason instanceof Error?reason.message:"Unable to load mappings");}
  }

  async function submitMapping(event:FormEvent<HTMLFormElement>){
    event.preventDefault(); if(!mappingAnalyzer||!selectedTestId)return;
    const data=new FormData(event.currentTarget); const selectedTest=tests.find(item=>item.id===selectedTestId);
    if(!selectedTest)return;
    try {
      setSaving(true); setError("");
      await api(`/analyzers/${mappingAnalyzer.id}/mappings`,{method:"POST",body:JSON.stringify({
        test_id:selectedTest.id,
        machine_test_code:data.get("machine_test_code"),
        parameters:selectedTest.parameters.map(parameter=>({parameter_id:parameter.id,machine_parameter_code:data.get(`machine_${parameter.id}`),unit:data.get(`unit_${parameter.id}`)||null})),
      })});
      setMappings(await api<TestMapping[]>(`/analyzers/${mappingAnalyzer.id}/mappings`));
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to save test mapping");}
    finally{setSaving(false);}
  }

  async function removeMapping(mapping:TestMapping){
    if(!mappingAnalyzer)return;
    if(!window.confirm(`Delete mapping ${mapping.lis_test_code} → ${mapping.machine_test_code}?`))return;
    try {
      setSaving(true); setError("");
      await api(`/analyzers/${mappingAnalyzer.id}/mappings/${mapping.id}`,{method:"DELETE"});
      if(selectedTestId===mapping.test_id)setSelectedTestId("");
      setMappings(await api<TestMapping[]>(`/analyzers/${mappingAnalyzer.id}/mappings`));
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to delete mapping");}
    finally{setSaving(false);}
  }

  async function deactivateMapping(mapping:TestMapping){
    if(!mappingAnalyzer)return;
    try {
      setSaving(true); setError("");
      await api(`/analyzers/${mappingAnalyzer.id}/mappings/${mapping.id}`,{
        method:"PATCH",
        body:JSON.stringify({status: mapping.status==="active"?"inactive":"active"}),
      });
      setMappings(await api<TestMapping[]>(`/analyzers/${mappingAnalyzer.id}/mappings`));
    } catch(reason){setError(reason instanceof Error?reason.message:"Unable to update mapping status");}
    finally{setSaving(false);}
  }

  async function openConnection(analyzer:Analyzer){
    try {
      setError(""); setConnectionAnalyzer(analyzer); setConnectionResult(null);
      setConnectionEvents(await api<ConnectionEvent[]>(`/analyzers/${analyzer.id}/connection-events?limit=25`));
    } catch(reason){setConnectionAnalyzer(null);setError(reason instanceof Error?reason.message:"Unable to load connection history");}
  }

  async function runConnectionProbe(kind:"connection-test"|"heartbeat"){
    if(!connectionAnalyzer)return;
    try {
      setTestingConnection(true); setError("");
      const result=await api<ConnectionResult>(`/analyzers/${connectionAnalyzer.id}/${kind}`,{method:"POST"});
      setConnectionResult(result);
      const [machinePage,events]=await Promise.all([api<Page<Analyzer>>("/analyzers?limit=100&offset=0"),api<ConnectionEvent[]>(`/analyzers/${connectionAnalyzer.id}/connection-events?limit=25`)]);
      setRecords(machinePage.items); setConnectionEvents(events);
      setConnectionAnalyzer(machinePage.items.find(item=>item.id===connectionAnalyzer.id)??connectionAnalyzer);
    } catch(reason){setError(reason instanceof Error?reason.message:"Connection test failed");}
    finally{setTestingConnection(false);}
  }

  const shown=records.filter(item=>`${item.code} ${item.vendor} ${item.model} ${item.host}`.toLowerCase().includes(filter.toLowerCase()));
  const branchName=(id:string)=>{const branch=branches.find(item=>item.id===id);return branch?`${branch.name} · ${branch.code}`:"Unknown branch"};
  const selectedTest=tests.find(item=>item.id===selectedTestId);
  const existingMapping=mappings.find(item=>item.test_id===selectedTestId);
  const parameterDefault=(parameterId:string,key:"machine_parameter_code"|"unit")=>existingMapping?.parameters.find(item=>item.parameter_id===parameterId)?.[key]??"";

  return <section>
    <div className="page-heading"><div><p className="eyebrow">INSTRUMENT INTERFACE</p><h1>Analyzers</h1><p>Configure laboratory machines and map LIS tests to machine identifiers.</p></div>{can("analyzer.manage")&&<button className="primary" onClick={()=>setOpen(true)}><Plus size={17}/> Add analyzer</button>}</div>
    <div className="analyzer-metrics"><article><Cpu/><span><strong>{total}</strong><small>configured analyzers</small></span></article><article><Network/><span><strong>{records.filter(item=>item.connection_status==="connected").length}</strong><small>connected analyzers</small></span></article></div>
    {error&&<div className="error-state"><AlertCircle size={18}/>{error}<button onClick={()=>void load()}>Retry</button></div>}
    <div className="panel"><div className="toolbar"><label className="search"><Search size={17}/><input aria-label="Filter analyzers" placeholder="Filter by code, vendor, model, or IP…" value={filter} onChange={event=>setFilter(event.target.value)}/></label><span>{total} records</span></div>
      {loading?<div className="loading"><i/><i/><i/></div>:shown.length===0?<div className="empty-state"><Cpu/><h3>No analyzers configured</h3><p>Add the first analyzer using its manufacturer interface manual.</p></div>:<div className="table-wrap"><table className="analyzer-table"><thead><tr><th>Analyzer</th><th>Branch</th><th>Protocol</th><th>Network endpoint</th><th>Connection</th><th>Configuration</th><th>Actions</th></tr></thead><tbody>{shown.map(item=><tr key={item.id}><td><strong>{item.vendor} {item.model}</strong><span>{item.code}</span></td><td>{branchName(item.branch_id)}</td><td>{protocolLabels[item.protocol]??item.protocol}</td><td><code>{item.host}:{item.port}</code><span>{item.connection_mode}</span></td><td><span className={`connection-status ${item.connection_status}`}>{item.connection_status.replaceAll("_"," ")}</span>{item.last_connection_test_at&&<span>{new Date(item.last_connection_test_at).toLocaleString()}</span>}</td><td><span className={`status ${item.status}`}>{item.status}</span></td><td><div className="analyzer-actions"><button className="mapping-button" onClick={()=>void openConnection(item)}><Activity size={14}/> Connection</button><button className="mapping-button" onClick={()=>void openMappings(item)}><Cable size={14}/> Map tests</button></div></td></tr>)}</tbody></table></div>}
      <div className="pagination"><span>Showing {shown.length} of {total}</span></div>
    </div>
    {open&&<div className="modal-backdrop"><section className="modal analyzer-modal"><div className="modal-head"><div><p className="eyebrow">NEW CONNECTION</p><h2>Configure analyzer</h2></div><button aria-label="Close" onClick={()=>setOpen(false)}><X/></button></div><form onSubmit={submitAnalyzer}>
      <label>Branch *<select name="branch_id" required defaultValue=""><option value="" disabled>Select branch</option>{branches.map(branch=><option key={branch.id} value={branch.id}>{branch.name} · {branch.code}</option>)}</select></label>
      <div className="analyzer-form-grid"><label>Machine code *<input name="code" required minLength={2} maxLength={40} placeholder="HEM-01" pattern="[A-Za-z0-9_-]+"/></label><label>Vendor *<input name="vendor" required placeholder="e.g. Sysmex"/></label><label>Model *<input name="model" required placeholder="e.g. XN-1000"/></label><label>Protocol *<select name="protocol" required defaultValue=""><option value="" disabled>Select from interface manual</option>{Object.entries(protocolLabels).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label><label>Private IP address *<input name="host" required inputMode="decimal" placeholder="192.168.1.50"/></label><label>Port *<input name="port" required type="number" min="1" max="65535" placeholder="5000"/></label><label>Communication *<select name="connection_mode" defaultValue="bidirectional"><option value="bidirectional">Bidirectional (orders + results)</option><option value="unidirectional">Unidirectional (results only)</option></select></label><label>Timeout (seconds) *<input name="connection_timeout_seconds" required type="number" min="1" max="15" defaultValue="3"/></label><label>Retry limit *<input name="retry_limit" required type="number" min="0" max="5" defaultValue="2"/></label><label>Heartbeat interval (seconds) *<input name="heartbeat_interval_seconds" required type="number" min="15" max="3600" defaultValue="60"/></label></div>
      <p className="configuration-note">Use the static IP, port, and protocol from the analyzer interface manual.</p><div className="form-actions"><button type="button" onClick={()=>setOpen(false)}>Cancel</button><button className="primary" disabled={saving}>{saving?"Saving…":"Save analyzer"}</button></div>
    </form></section></div>}
    {mappingAnalyzer&&<div className="modal-backdrop"><section className="modal mapping-modal"><div className="modal-head"><div><p className="eyebrow">TEST-CODE MAPPING</p><h2>{mappingAnalyzer.vendor} {mappingAnalyzer.model}</h2><small>{mappingAnalyzer.code} · {mappings.length} mapped test(s)</small></div><button aria-label="Close mappings" onClick={()=>setMappingAnalyzer(null)}><X/></button></div>
      <div className="mapping-layout"><aside><h3>Mapped tests</h3>{mappings.length===0?<p>No tests mapped yet.</p>:mappings.map(mapping=><div key={mapping.id} className="mapping-chip-row"><button className={selectedTestId===mapping.test_id?"active":""} onClick={()=>setSelectedTestId(mapping.test_id)}><strong>{mapping.lis_test_code} → {mapping.machine_test_code}</strong><span>{mapping.test_name} · {mapping.parameters.length} parameters · {mapping.status}</span></button>{can("analyzer.manage")&&<div className="mapping-chip-actions"><button type="button" onClick={()=>void deactivateMapping(mapping)} disabled={saving}>{mapping.status==="active"?"Deactivate":"Activate"}</button><button type="button" aria-label={`Delete ${mapping.lis_test_code}`} onClick={()=>void removeMapping(mapping)} disabled={saving}><Trash2 size={14}/></button></div>}</div>)}</aside>
      <form key={selectedTestId} onSubmit={submitMapping}><label>Search LIS tests<div className="mapping-test-search"><Search size={16}/><input aria-label="Search LIS tests" placeholder="Type test code or name, e.g. BIO0231" value={testSearch} onChange={event=>{setTestSearch(event.target.value);setSelectedTestId("")}}/></div><small>{searchingTests?"Searching catalogue…":`${tests.length} result(s) shown`}</small></label><label>LIS test *<select required value={selectedTestId} onChange={event=>setSelectedTestId(event.target.value)} disabled={searchingTests}><option value="" disabled>{searchingTests?"Searching…":"Select test"}</option>{tests.map(test=><option key={test.id} value={test.id}>{test.code} · {test.name}</option>)}</select></label>{selectedTest&&<><label>Machine test code *<input name="machine_test_code" required maxLength={100} defaultValue={existingMapping?.machine_test_code??""} placeholder="CBC"/></label><div className="parameter-map-head"><strong>Parameter mapping</strong><span>LIS parameter → Machine identifier → Unit</span></div>{selectedTest.parameters.length===0?<p className="configuration-note">This LIS test has no parameters configured in Test master.</p>:<div className="parameter-map-list">{selectedTest.parameters.map(parameter=><div key={parameter.id}><label><span>{parameter.name}<small>{parameter.external_code}</small></span><input name={`machine_${parameter.id}`} required maxLength={100} defaultValue={parameterDefault(parameter.id,"machine_parameter_code")} placeholder={parameter.external_code}/></label><input aria-label={`${parameter.name} unit`} name={`unit_${parameter.id}`} maxLength={40} defaultValue={parameterDefault(parameter.id,"unit")} placeholder="Unit, e.g. g/dL"/></div>)}</div>}<div className="form-actions"><button type="button" onClick={()=>setMappingAnalyzer(null)}>Close</button><button className="primary" disabled={saving}>{saving?"Saving…":existingMapping?"Update mapping":"Save mapping"}</button></div></>}</form></div>
    </section></div>}
    {connectionAnalyzer&&<div className="modal-backdrop"><section className="modal connection-modal"><div className="modal-head"><div><p className="eyebrow">CONNECTION MONITOR</p><h2>{connectionAnalyzer.vendor} {connectionAnalyzer.model}</h2><small>{connectionAnalyzer.host}:{connectionAnalyzer.port} · {protocolLabels[connectionAnalyzer.protocol]}</small></div><button aria-label="Close connection monitor" onClick={()=>setConnectionAnalyzer(null)}><X/></button></div><div className="connection-summary"><article><span className={`connection-status ${connectionAnalyzer.connection_status}`}>{connectionAnalyzer.connection_status.replaceAll("_"," ")}</span><small>Current state</small></article><article><strong>{connectionAnalyzer.connection_timeout_seconds}s</strong><small>Timeout · {connectionAnalyzer.retry_limit} retries</small></article><article><strong>{connectionAnalyzer.heartbeat_interval_seconds}s</strong><small>Heartbeat interval</small></article></div>{connectionAnalyzer.last_connection_error&&<div className="connection-error"><AlertCircle size={16}/><span><strong>Last error</strong>{connectionAnalyzer.last_connection_error}</span></div>}{connectionResult&&<div className={`probe-result ${connectionResult.success?"success":"failed"}`}><Activity size={16}/><span><strong>{connectionResult.message}</strong><small>{connectionResult.attempts} attempt(s) · {connectionResult.latency_ms??"—"} ms</small></span></div>}<div className="connection-controls"><button onClick={()=>void runConnectionProbe("heartbeat")} disabled={testingConnection}>Run heartbeat</button><button className="primary" onClick={()=>void runConnectionProbe("connection-test")} disabled={testingConnection}>{testingConnection?"Testing…":"Test connection"}</button></div><div className="connection-history"><h3>Connection events</h3>{connectionEvents.length===0?<p>No connection attempts recorded.</p>:<div className="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>Attempt</th><th>Latency</th><th>Outcome</th><th>Message</th></tr></thead><tbody>{connectionEvents.map(event=><tr key={event.id}><td>{new Date(event.occurred_at).toLocaleString()}</td><td>{event.event_type.replaceAll("_"," ")}</td><td>{event.attempt}</td><td>{event.latency_ms??"—"} ms</td><td><span className={`connection-status ${event.success?"connected":"error"}`}>{event.success?"success":"failed"}</span></td><td>{event.message}</td></tr>)}</tbody></table></div>}</div></section></div>}
  </section>;
}

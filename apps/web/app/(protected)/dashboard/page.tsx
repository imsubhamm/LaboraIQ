import { Activity, Building2, GitBranch, ShieldCheck, Users, ScrollText } from "lucide-react";

const metrics = [
  ["Organizations", "1", Building2, "Tenant isolation active"],
  ["Branches", "1", GitBranch, "Asia/Kolkata"],
  ["Active users", "1", Users, "OIDC-ready identities"],
  ["Roles", "8", ShieldCheck, "Configurable templates"]
] as const;

export default function Dashboard() {
  return <section>
    <div className="page-heading"><div><p className="eyebrow">CORE PLATFORM FOUNDATION</p><h1>Operations overview</h1><p>Configuration health and governance controls across your laboratory network.</p></div><span className="verified"><Activity size={16}/> Foundation environment</span></div>
    <div className="metric-grid">{metrics.map(([label, value, Icon, note]) => <article className="metric" key={label}><div><p>{label}</p><strong>{value}</strong><small>{note}</small></div><Icon/></article>)}</div>
    <div className="dashboard-grid">
      <article className="panel governance"><div className="panel-title"><div><p className="eyebrow">GOVERNANCE</p><h2>Control posture</h2></div><span className="status active">Operational</span></div>
        {[["Tenant isolation","Service + query scoped"],["Role-based access","Granular permissions"],["Audit trail","Append-only events"],["Authentication","Development OIDC adapter"]].map(([a,b])=><div className="control" key={a}><ShieldCheck size={18}/><span><strong>{a}</strong><small>{b}</small></span><b>Enabled</b></div>)}
      </article>
      <article className="panel"><div className="panel-title"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Audit stream</h2></div><ScrollText size={20}/></div><div className="empty-compact"><span>01</span><p>Configuration events appear here as the team begins work.</p></div></article>
    </div>
  </section>;
}


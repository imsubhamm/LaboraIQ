"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, Building2, GitBranch, LayoutDashboard, LogOut, Settings,
  ShieldCheck, Users, ScrollText, FlaskConical, ClipboardPlus, TestTubes, ContactRound, ScanBarcode, Cpu, ListChecks
} from "lucide-react";
import { can, Permission } from "@/lib/auth";

const navigation: Array<[string, string, React.ComponentType<{size?: number}>, Permission?]> = [
  ["/dashboard", "Overview", LayoutDashboard, undefined],
  ["/patients/new", "Patient intake", ClipboardPlus, "branch.manage"],
  ["/patients", "Patients", ContactRound, "branch.read"],
  ["/specimens", "Specimens", ScanBarcode, "branch.read"],
  ["/analyzers", "Analyzers", Cpu, "analyzer.read"],
  ["/analyzers/worklist", "Analyzer worklist", ListChecks, "analyzer.read"],
  ["/organizations", "Organizations", Building2, "organization.read"],
  ["/branches", "Branches", GitBranch, "branch.read"],
  ["/departments", "Departments", FlaskConical, "branch.read"],
  ["/test-master", "Test master", TestTubes, "test_master.read"],
  ["/users", "Users", Users, "user.read"],
  ["/roles", "Roles & access", ShieldCheck, "role.read"],
  ["/audit", "Audit trail", ScrollText, "audit.read"],
  ["/settings", "Settings", Settings, undefined]
];

export function visibleNavigation() {
  return navigation.filter(([, , , permission]) => !permission || can(permission));
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  async function logout() {
    await fetch("/auth/logout", { method: "POST" });
    window.location.assign("/login");
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span>LQ</span><div>LaboraIQ<small>CONTROL CENTRE</small></div></div>
        <nav aria-label="Primary navigation">
          {visibleNavigation().map(([href, label, Icon]) => (
            <Link key={href} href={href} className={path === href ? "active" : ""}>
              <Icon size={18}/><span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="system-state"><Activity size={16}/><div><strong>Systems normal</strong><small>API · Database · Audit</small></div></div>
      </aside>
      <div className="workspace">
        <header>
          <div className="context">
            <span>ORGANIZATION<strong>LaboraIQ Development</strong></span>
            <span>BRANCH<strong>Kolkata · KOL</strong></span>
          </div>
          <div className="user-menu">
            <div className="avatar">DA</div>
            <div><strong>Development Admin</strong><small>Laboratory Administrator</small></div>
            <button aria-label="Log out" onClick={logout}><LogOut size={17}/></button>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}

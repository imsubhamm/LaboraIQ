"use client";

import { AuditReportPanel } from "@/components/audit-report-panel";

export default function NablAuditReportPage() {
  return (
    <section>
      <AuditReportPanel
        auditType="NABL"
        title="NABL Audit Report"
        description="Accreditation-style quality audits using the shared audit engine. Clause content is configurable; demo rows are synthetic."
      />
    </section>
  );
}

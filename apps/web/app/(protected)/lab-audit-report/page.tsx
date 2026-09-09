"use client";

import { AuditReportPanel } from "@/components/audit-report-panel";

export default function LabAuditReportPage() {
  return (
    <section>
      <AuditReportPanel
        auditType="INTERNAL"
        title="LAB Audit Report"
        description="Internal laboratory process audits using the same audit engine as NABL. Demo rows are synthetic."
      />
    </section>
  );
}

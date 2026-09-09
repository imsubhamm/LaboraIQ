"""Quality audit domain tables for NABL and internal LAB audits.

Revision ID: 20260909_0017
Revises: 20260908_0016
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0017"
down_revision = "20260908_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_standards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", "version", name="uq_audit_standard"),
    )
    op.create_index("ix_audit_standards_organization_id", "audit_standards", ["organization_id"])

    op.create_table(
        "audit_clauses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("standard_id", sa.Uuid(), nullable=False),
        sa.Column("parent_clause_id", sa.Uuid(), nullable=True),
        sa.Column("clause_code", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["parent_clause_id"], ["audit_clauses.id"]),
        sa.ForeignKeyConstraint(["standard_id"], ["audit_standards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("standard_id", "clause_code", name="uq_audit_clause_code"),
    )
    op.create_index("ix_audit_clauses_organization_id", "audit_clauses", ["organization_id"])
    op.create_index("ix_audit_clauses_standard_id", "audit_clauses", ["standard_id"])
    op.create_index("ix_audit_clause_standard_seq", "audit_clauses", ["standard_id", "sequence"])

    op.create_table(
        "audit_checklists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("audit_type", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", "version", name="uq_audit_checklist"),
    )
    op.create_index("ix_audit_checklists_organization_id", "audit_checklists", ["organization_id"])
    op.create_index("ix_audit_checklist_org_type", "audit_checklists", ["organization_id", "audit_type"])

    op.create_table(
        "audit_checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=120), nullable=True),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_evidence", sa.Text(), nullable=True),
        sa.Column("severity_if_failed", sa.String(length=20), nullable=False),
        sa.Column("applicable_department", sa.String(length=120), nullable=True),
        sa.Column("clause_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["audit_checklists.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["audit_clauses.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_checklist_items_organization_id", "audit_checklist_items", ["organization_id"])
    op.create_index("ix_audit_checklist_items_checklist_id", "audit_checklist_items", ["checklist_id"])
    op.create_index("ix_checklist_item_checklist_seq", "audit_checklist_items", ["checklist_id", "sequence"])

    op.create_table(
        "audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("checklist_id", sa.Uuid(), nullable=True),
        sa.Column("standard_id", sa.Uuid(), nullable=True),
        sa.Column("audit_number", sa.String(length=40), nullable=False),
        sa.Column("audit_type", sa.String(length=20), nullable=False),
        sa.Column("lab_audit_subtype", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("process_name", sa.String(length=120), nullable=True),
        sa.Column("auditor_user_id", sa.Uuid(), nullable=True),
        sa.Column("audit_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["auditor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["audit_owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["checklist_id"], ["audit_checklists.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["standard_id"], ["audit_standards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "audit_number", name="uq_audit_number"),
    )
    op.create_index("ix_audits_organization_id", "audits", ["organization_id"])
    op.create_index("ix_audits_branch_id", "audits", ["branch_id"])
    op.create_index("ix_audits_department_id", "audits", ["department_id"])
    op.create_index("ix_audits_org_type_status", "audits", ["organization_id", "audit_type", "status"])
    op.create_index(
        "ix_audits_org_branch_planned", "audits", ["organization_id", "branch_id", "planned_start_at"]
    )

    op.create_table(
        "audit_check_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_item_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("evidence_required", sa.Boolean(), nullable=False),
        sa.Column("evidence_provided", sa.Boolean(), nullable=False),
        sa.Column("evaluated_by", sa.Uuid(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.ForeignKeyConstraint(["checklist_item_id"], ["audit_checklist_items.id"]),
        sa.ForeignKeyConstraint(["evaluated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", "checklist_item_id", name="uq_audit_check_item"),
    )
    op.create_index("ix_audit_check_results_organization_id", "audit_check_results", ["organization_id"])
    op.create_index("ix_audit_check_results_audit_id", "audit_check_results", ["audit_id"])
    op.create_index("ix_check_results_audit", "audit_check_results", ["organization_id", "audit_id"])

    op.create_table(
        "audit_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_result_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("standard_id", sa.Uuid(), nullable=True),
        sa.Column("clause_id", sa.Uuid(), nullable=True),
        sa.Column("analyzer_id", sa.Uuid(), nullable=True),
        sa.Column("specimen_id", sa.Uuid(), nullable=True),
        sa.Column("lab_result_id", sa.Uuid(), nullable=True),
        sa.Column("worklist_item_id", sa.Uuid(), nullable=True),
        sa.Column("referenced_entity_type", sa.String(length=80), nullable=True),
        sa.Column("referenced_entity_id", sa.String(length=100), nullable=True),
        sa.Column("finding_number", sa.String(length=40), nullable=False),
        sa.Column("finding_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("corrective_action_required", sa.Boolean(), nullable=False),
        sa.Column("preventive_action_required", sa.Boolean(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_name", sa.String(length=120), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"]),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["checklist_result_id"], ["audit_check_results.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["audit_clauses.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["lab_result_id"], ["lab_results.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["specimen_id"], ["specimens.id"]),
        sa.ForeignKeyConstraint(["standard_id"], ["audit_standards.id"]),
        sa.ForeignKeyConstraint(["worklist_item_id"], ["analyzer_worklist_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "finding_number", name="uq_finding_number"),
    )
    op.create_index("ix_audit_findings_organization_id", "audit_findings", ["organization_id"])
    op.create_index("ix_audit_findings_branch_id", "audit_findings", ["branch_id"])
    op.create_index("ix_audit_findings_audit_id", "audit_findings", ["audit_id"])
    op.create_index(
        "ix_findings_org_audit_status", "audit_findings", ["organization_id", "audit_id", "status"]
    )
    op.create_index(
        "ix_findings_org_severity", "audit_findings", ["organization_id", "severity", "status"]
    )
    op.create_index("ix_findings_due", "audit_findings", ["organization_id", "due_at"])

    op.create_table(
        "audit_capas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("capa_number", sa.String(length=40), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("immediate_correction", sa.Text(), nullable=True),
        sa.Column("corrective_action", sa.Text(), nullable=True),
        sa.Column("preventive_action", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("effectiveness_check_required", sa.Boolean(), nullable=False),
        sa.Column("effectiveness_verified", sa.Boolean(), nullable=False),
        sa.Column("effectiveness_notes", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["audit_findings.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "capa_number", name="uq_capa_number"),
    )
    op.create_index("ix_audit_capas_organization_id", "audit_capas", ["organization_id"])
    op.create_index("ix_capa_finding", "audit_capas", ["finding_id"])
    op.create_index("ix_capa_org_status_due", "audit_capas", ["organization_id", "status", "due_at"])

    op.create_table(
        "audit_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=True),
        sa.Column("finding_id", sa.Uuid(), nullable=True),
        sa.Column("capa_id", sa.Uuid(), nullable=True),
        sa.Column("document_reference", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.ForeignKeyConstraint(["capa_id"], ["audit_capas.id"]),
        sa.ForeignKeyConstraint(["finding_id"], ["audit_findings.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_evidence_organization_id", "audit_evidence", ["organization_id"])
    op.create_index("ix_evidence_org_audit", "audit_evidence", ["organization_id", "audit_id"])
    op.create_index("ix_evidence_finding", "audit_evidence", ["finding_id"])
    op.create_index("ix_evidence_capa", "audit_evidence", ["capa_id"])


def downgrade() -> None:
    op.drop_table("audit_evidence")
    op.drop_table("audit_capas")
    op.drop_table("audit_findings")
    op.drop_table("audit_check_results")
    op.drop_table("audits")
    op.drop_table("audit_checklist_items")
    op.drop_table("audit_checklists")
    op.drop_table("audit_clauses")
    op.drop_table("audit_standards")

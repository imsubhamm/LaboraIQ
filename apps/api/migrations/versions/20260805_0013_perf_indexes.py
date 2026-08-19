"""Add composite indexes for list/auth hot paths.

Revision ID: 20260805_0013
Revises: 20260805_0012
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op

revision = "20260805_0013"
down_revision = "20260805_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_patients_org_updated", "patients", ["organization_id", "updated_at"])
    op.create_index("ix_patients_email", "patients", ["email"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index(
        "ix_ura_user_org_active",
        "user_role_assignments",
        ["user_id", "organization_id", "active"],
    )
    op.create_index(
        "ix_lab_orders_org_patient",
        "lab_orders",
        ["organization_id", "patient_id"],
    )
    op.create_index(
        "ix_specimens_org_status_updated",
        "specimens",
        ["organization_id", "status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_specimens_org_status_updated", table_name="specimens")
    op.drop_index("ix_lab_orders_org_patient", table_name="lab_orders")
    op.drop_index("ix_ura_user_org_active", table_name="user_role_assignments")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_patients_email", table_name="patients")
    op.drop_index("ix_patients_org_updated", table_name="patients")

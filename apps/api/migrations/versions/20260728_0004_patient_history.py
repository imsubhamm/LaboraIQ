"""Persistent returning-patient identity and demographic history.

Revision ID: 20260728_0004
Revises: 20260727_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20260728_0004"
down_revision = "20260727_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("race", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("nationality", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("additional_patient_data", sa.JSON(), nullable=True))
    op.create_index("ix_patients_org_phone", "patients", ["organization_id", "phone"])
    op.create_index("ix_patients_org_email", "patients", ["organization_id", "email"])
    op.create_table(
        "patient_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("demographics", sa.JSON(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_history_organization_id", "patient_history", ["organization_id"])
    op.create_index("ix_patient_history_patient_id", "patient_history", ["patient_id"])
    op.create_index("ix_patient_history_order_id", "patient_history", ["order_id"])
    op.create_index(
        "ix_patient_history_patient_recorded",
        "patient_history",
        ["patient_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("patient_history")
    op.drop_index("ix_patients_org_email", table_name="patients")
    op.drop_index("ix_patients_org_phone", table_name="patients")
    op.drop_column("patients", "nationality")
    op.drop_column("patients", "additional_patient_data")
    op.drop_column("patients", "race")
    op.drop_column("patients", "country")

"""LAB-4 registration, billing and specimen workflow.

Revision ID: 20260727_0002
Revises: 20260727_0001
"""

import sqlalchemy as sa
from alembic import op
from app.models import Invoice, LabOrder, OrderTest, Patient, Specimen, TestCatalogItem

revision = "20260727_0002"
down_revision = "20260727_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("patient_number", sa.String(length=40), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("age_years", sa.Integer(), nullable=True),
        sa.Column("sex", sa.String(length=30), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("blood_group", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "patient_number", name="uq_patient_number"),
    )
    op.create_index("ix_patients_organization_id", "patients", ["organization_id"])
    for table in [
        TestCatalogItem.__table__,
        LabOrder.__table__,
        OrderTest.__table__,
        Specimen.__table__,
    ]:
        table.create(bind=bind, checkfirst=True)
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_number"),
    )
    op.create_index(
        op.f("ix_invoices_organization_id"),
        "invoices",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in [
        Specimen.__table__,
        Invoice.__table__,
        OrderTest.__table__,
        LabOrder.__table__,
        TestCatalogItem.__table__,
        Patient.__table__,
    ]:
        table.drop(bind=bind, checkfirst=True)

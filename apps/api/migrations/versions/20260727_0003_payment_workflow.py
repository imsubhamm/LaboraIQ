"""LAB-4 payment confirmation before barcode generation.

Revision ID: 20260727_0003
Revises: 20260727_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20260727_0003"
down_revision = "20260727_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("payment_method", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("transaction_id", sa.String(length=120), nullable=True))
    op.add_column("invoices", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "paid_at")
    op.drop_column("invoices", "transaction_id")
    op.drop_column("invoices", "payment_method")

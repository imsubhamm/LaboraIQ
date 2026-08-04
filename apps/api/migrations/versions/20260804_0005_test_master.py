"""LIS/HIS test master classification and panel parameters.

Revision ID: 20260804_0005
Revises: 20260728_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260804_0005"
down_revision = "20260728_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("test_catalog_items")
    }
    columns = [
        sa.Column("service_type", sa.String(80), nullable=False, server_default="Pathology"),
        sa.Column("department", sa.String(120), nullable=False, server_default="Laboratory"),
        sa.Column("sub_department", sa.String(120), nullable=False, server_default=""),
        sa.Column("is_panel", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("validation_status", sa.String(30), nullable=False, server_default="validated"),
    ]
    for column in columns:
        if column.name not in existing:
            op.add_column("test_catalog_items", column)
    op.create_table(
        "test_catalog_parameters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("external_code", sa.String(255), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["test_id"], ["test_catalog_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_id", "external_code", name="uq_test_parameter_external_code"),
    )
    op.create_index("ix_test_catalog_parameters_test_id", "test_catalog_parameters", ["test_id"])


def downgrade() -> None:
    op.drop_table("test_catalog_parameters")
    op.drop_column("test_catalog_items", "validation_status")
    op.drop_column("test_catalog_items", "is_panel")
    op.drop_column("test_catalog_items", "sub_department")
    op.drop_column("test_catalog_items", "department")
    op.drop_column("test_catalog_items", "service_type")

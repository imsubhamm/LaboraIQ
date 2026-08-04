"""Specimen collection, accession and review workflow.

Revision ID: 20260804_0006
Revises: 20260804_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "20260804_0006"
down_revision = "20260804_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        sa.Column("laboratory_department", sa.String(120), nullable=True),
        sa.Column("accession_number", sa.String(60), nullable=True),
        sa.Column("collection_location", sa.String(200), nullable=True),
        sa.Column("container_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("collection_notes", sa.Text(), nullable=True),
        sa.Column("collected_by", sa.Uuid(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(120), nullable=True),
        sa.Column("rejection_notes", sa.Text(), nullable=True),
    ]
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("specimens")}
    for column in columns:
        if column.name not in existing:
            op.add_column("specimens", column)
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("specimens")}
    if "ix_specimens_laboratory_department" not in indexes:
        op.create_index(
            "ix_specimens_laboratory_department", "specimens", ["laboratory_department"]
        )
    if "ix_specimens_accession_number" not in indexes:
        op.create_index("ix_specimens_accession_number", "specimens", ["accession_number"])


def downgrade() -> None:
    op.drop_index("ix_specimens_accession_number", table_name="specimens")
    op.drop_index("ix_specimens_laboratory_department", table_name="specimens")
    for name in [
        "rejection_notes",
        "rejection_reason",
        "reviewed_at",
        "reviewed_by",
        "received_at",
        "received_by",
        "collected_at",
        "collected_by",
        "collection_notes",
        "container_count",
        "collection_location",
        "accession_number",
        "laboratory_department",
    ]:
        op.drop_column("specimens", name)

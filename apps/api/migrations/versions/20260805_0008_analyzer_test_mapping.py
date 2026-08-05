"""Analyzer test and parameter code mapping.

Revision ID: 20260805_0008
Revises: 20260804_0007
"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_0008"
down_revision = "20260804_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyzer_test_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("machine_test_code", sa.String(100), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="status"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_id"], ["test_catalog_items.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analyzer_id", "test_id", name="uq_analyzer_test_mapping"),
        sa.UniqueConstraint(
            "analyzer_id", "machine_test_code", name="uq_analyzer_machine_test_code"
        ),
    )
    op.create_index(
        "ix_analyzer_test_mappings_organization_id",
        "analyzer_test_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_analyzer_test_mappings_analyzer_id",
        "analyzer_test_mappings",
        ["analyzer_id"],
    )
    op.create_index("ix_analyzer_test_mappings_test_id", "analyzer_test_mappings", ["test_id"])
    op.create_table(
        "analyzer_parameter_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("test_mapping_id", sa.Uuid(), nullable=False),
        sa.Column("parameter_id", sa.Uuid(), nullable=False),
        sa.Column("machine_parameter_code", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_mapping_id"], ["analyzer_test_mappings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["parameter_id"], ["test_catalog_parameters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_mapping_id", "parameter_id", name="uq_mapping_parameter"),
        sa.UniqueConstraint(
            "test_mapping_id", "machine_parameter_code", name="uq_mapping_machine_parameter"
        ),
    )
    op.create_index(
        "ix_analyzer_parameter_mappings_test_mapping_id",
        "analyzer_parameter_mappings",
        ["test_mapping_id"],
    )
    op.create_index(
        "ix_analyzer_parameter_mappings_parameter_id",
        "analyzer_parameter_mappings",
        ["parameter_id"],
    )


def downgrade() -> None:
    op.drop_table("analyzer_parameter_mappings")
    op.drop_table("analyzer_test_mappings")

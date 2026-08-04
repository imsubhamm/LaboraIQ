"""Analyzer connection configuration.

Revision ID: 20260804_0007
Revises: 20260804_0006
"""

import sqlalchemy as sa
from alembic import op

revision = "20260804_0007"
down_revision = "20260804_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyzers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("vendor", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("protocol", sa.String(30), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column(
            "connection_mode", sa.String(20), nullable=False, server_default="bidirectional"
        ),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "branch_id", "code", name="uq_analyzer_scope_code"),
    )
    op.create_index("ix_analyzers_organization_id", "analyzers", ["organization_id"])
    op.create_index("ix_analyzers_branch_id", "analyzers", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_analyzers_branch_id", table_name="analyzers")
    op.drop_index("ix_analyzers_organization_id", table_name="analyzers")
    op.drop_table("analyzers")

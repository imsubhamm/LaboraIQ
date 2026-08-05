"""Analyzer TCP connection monitoring and event log.

Revision ID: 20260805_0009
Revises: 20260805_0008
"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_0009"
down_revision = "20260805_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analyzers",
        sa.Column(
            "connection_status",
            sa.String(30),
            nullable=False,
            server_default="never_tested",
        ),
    )
    op.add_column(
        "analyzers",
        sa.Column("connection_timeout_seconds", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "analyzers", sa.Column("retry_limit", sa.Integer(), nullable=False, server_default="2")
    )
    op.add_column(
        "analyzers",
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column("analyzers", sa.Column("last_connection_test_at", sa.DateTime(timezone=True)))
    op.add_column("analyzers", sa.Column("last_connected_at", sa.DateTime(timezone=True)))
    op.add_column("analyzers", sa.Column("last_connection_error", sa.String(500)))
    op.create_table(
        "analyzer_connection_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analyzer_connection_events_organization_id",
        "analyzer_connection_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_analyzer_connection_events_branch_id",
        "analyzer_connection_events",
        ["branch_id"],
    )
    op.create_index(
        "ix_analyzer_connection_events_analyzer_id",
        "analyzer_connection_events",
        ["analyzer_id"],
    )
    op.create_index(
        "ix_analyzer_connection_events_event_type",
        "analyzer_connection_events",
        ["event_type"],
    )
    op.create_index(
        "ix_analyzer_connection_events_correlation_id",
        "analyzer_connection_events",
        ["correlation_id"],
    )
    op.create_index(
        "ix_analyzer_connection_events_recent",
        "analyzer_connection_events",
        ["analyzer_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("analyzer_connection_events")
    for column in [
        "last_connection_error",
        "last_connected_at",
        "last_connection_test_at",
        "heartbeat_interval_seconds",
        "retry_limit",
        "connection_timeout_seconds",
        "connection_status",
    ]:
        op.drop_column("analyzers", column)

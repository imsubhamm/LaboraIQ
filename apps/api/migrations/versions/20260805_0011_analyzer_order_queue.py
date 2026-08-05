"""Analyzer worklist order queue, attempts, and immutable message store.

Revision ID: 20260805_0011
Revises: 20260805_0010
"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_0011"
down_revision = "20260805_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyzer_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("worklist_item_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["worklist_item_id"], ["analyzer_worklist_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyzer_messages_organization_id", "analyzer_messages", ["organization_id"])
    op.create_index("ix_analyzer_messages_analyzer_id", "analyzer_messages", ["analyzer_id"])
    op.create_index(
        "ix_analyzer_messages_worklist_item_id", "analyzer_messages", ["worklist_item_id"]
    )
    op.create_index("ix_analyzer_messages_attempt_id", "analyzer_messages", ["attempt_id"])
    op.create_index("ix_analyzer_messages_payload_hash", "analyzer_messages", ["payload_hash"])
    op.create_index("ix_analyzer_messages_correlation_id", "analyzer_messages", ["correlation_id"])
    op.create_index(
        "ix_analyzer_messages_correlation",
        "analyzer_messages",
        ["organization_id", "correlation_id"],
    )

    op.create_table(
        "analyzer_order_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("worklist_item_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("request_message_id", sa.Uuid(), nullable=True),
        sa.Column("response_message_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["request_message_id"], ["analyzer_messages.id"]),
        sa.ForeignKeyConstraint(["response_message_id"], ["analyzer_messages.id"]),
        sa.ForeignKeyConstraint(["worklist_item_id"], ["analyzer_worklist_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worklist_item_id", "attempt_no", name="uq_worklist_attempt_no"),
    )
    op.create_index(
        "ix_analyzer_order_attempts_organization_id",
        "analyzer_order_attempts",
        ["organization_id"],
    )
    op.create_index("ix_analyzer_order_attempts_branch_id", "analyzer_order_attempts", ["branch_id"])
    op.create_index(
        "ix_analyzer_order_attempts_worklist_item_id",
        "analyzer_order_attempts",
        ["worklist_item_id"],
    )
    op.create_index(
        "ix_analyzer_order_attempts_analyzer_id", "analyzer_order_attempts", ["analyzer_id"]
    )
    op.create_index("ix_analyzer_order_attempts_state", "analyzer_order_attempts", ["state"])
    op.create_index(
        "ix_analyzer_order_attempts_correlation_id",
        "analyzer_order_attempts",
        ["correlation_id"],
    )
    op.create_index(
        "ix_order_attempts_queue",
        "analyzer_order_attempts",
        ["organization_id", "state", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_attempts_queue", table_name="analyzer_order_attempts")
    op.drop_index("ix_analyzer_order_attempts_correlation_id", table_name="analyzer_order_attempts")
    op.drop_index("ix_analyzer_order_attempts_state", table_name="analyzer_order_attempts")
    op.drop_index("ix_analyzer_order_attempts_analyzer_id", table_name="analyzer_order_attempts")
    op.drop_index(
        "ix_analyzer_order_attempts_worklist_item_id", table_name="analyzer_order_attempts"
    )
    op.drop_index("ix_analyzer_order_attempts_branch_id", table_name="analyzer_order_attempts")
    op.drop_index(
        "ix_analyzer_order_attempts_organization_id", table_name="analyzer_order_attempts"
    )
    op.drop_table("analyzer_order_attempts")
    op.drop_index("ix_analyzer_messages_correlation", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_correlation_id", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_payload_hash", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_attempt_id", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_worklist_item_id", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_analyzer_id", table_name="analyzer_messages")
    op.drop_index("ix_analyzer_messages_organization_id", table_name="analyzer_messages")
    op.drop_table("analyzer_messages")

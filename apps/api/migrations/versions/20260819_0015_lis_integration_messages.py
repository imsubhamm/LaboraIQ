"""LIS integration messages for status/storage/routing.

Revision ID: 20260819_0015
Revises: 20260806_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0015"
down_revision = "20260806_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lis_integration_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("specimen_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("event_category", sa.String(length=30), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("delivery_state", sa.String(length=20), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["specimen_id"], ["specimens.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lis_integration_messages_organization_id",
        "lis_integration_messages",
        ["organization_id"],
    )
    op.create_index(
        "ix_lis_integration_messages_branch_id",
        "lis_integration_messages",
        ["branch_id"],
    )
    op.create_index(
        "ix_lis_integration_messages_specimen_id",
        "lis_integration_messages",
        ["specimen_id"],
    )
    op.create_index(
        "ix_lis_integration_messages_order_id",
        "lis_integration_messages",
        ["order_id"],
    )
    op.create_index(
        "ix_lis_integration_messages_event_category",
        "lis_integration_messages",
        ["event_category"],
    )
    op.create_index(
        "ix_lis_integration_messages_payload_hash",
        "lis_integration_messages",
        ["payload_hash"],
    )
    op.create_index(
        "ix_lis_integration_messages_correlation_id",
        "lis_integration_messages",
        ["correlation_id"],
    )
    op.create_index(
        "ix_lis_integration_messages_delivery_state",
        "lis_integration_messages",
        ["delivery_state"],
    )
    op.create_index(
        "ix_lis_messages_specimen_created",
        "lis_integration_messages",
        ["organization_id", "specimen_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lis_messages_specimen_created", table_name="lis_integration_messages")
    op.drop_index(
        "ix_lis_integration_messages_delivery_state",
        table_name="lis_integration_messages",
    )
    op.drop_index(
        "ix_lis_integration_messages_correlation_id",
        table_name="lis_integration_messages",
    )
    op.drop_index(
        "ix_lis_integration_messages_payload_hash",
        table_name="lis_integration_messages",
    )
    op.drop_index(
        "ix_lis_integration_messages_event_category",
        table_name="lis_integration_messages",
    )
    op.drop_index("ix_lis_integration_messages_order_id", table_name="lis_integration_messages")
    op.drop_index(
        "ix_lis_integration_messages_specimen_id",
        table_name="lis_integration_messages",
    )
    op.drop_index("ix_lis_integration_messages_branch_id", table_name="lis_integration_messages")
    op.drop_index(
        "ix_lis_integration_messages_organization_id",
        table_name="lis_integration_messages",
    )
    op.drop_table("lis_integration_messages")

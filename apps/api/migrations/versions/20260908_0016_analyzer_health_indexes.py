"""Composite indexes for analyzer machine-health window queries.

Revision ID: 20260908_0016
Revises: 20260819_0015
"""

from alembic import op

revision = "20260908_0016"
down_revision = "20260819_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ace_org_analyzer_occurred",
        "analyzer_connection_events",
        ["organization_id", "analyzer_id", "occurred_at"],
    )
    op.create_index(
        "ix_order_attempts_org_analyzer_created",
        "analyzer_order_attempts",
        ["organization_id", "analyzer_id", "created_at"],
    )
    op.create_index(
        "ix_worklist_org_analyzer_created",
        "analyzer_worklist_items",
        ["organization_id", "analyzer_id", "created_at"],
    )
    op.create_index(
        "ix_lab_results_org_analyzer_created",
        "lab_results",
        ["organization_id", "analyzer_id", "created_at"],
    )
    op.create_index(
        "ix_analyzer_messages_org_analyzer_created",
        "analyzer_messages",
        ["organization_id", "analyzer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analyzer_messages_org_analyzer_created", table_name="analyzer_messages")
    op.drop_index("ix_lab_results_org_analyzer_created", table_name="lab_results")
    op.drop_index("ix_worklist_org_analyzer_created", table_name="analyzer_worklist_items")
    op.drop_index("ix_order_attempts_org_analyzer_created", table_name="analyzer_order_attempts")
    op.drop_index("ix_ace_org_analyzer_occurred", table_name="analyzer_connection_events")

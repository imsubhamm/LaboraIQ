"""Lab results normalization and clinical review workflow.

Revision ID: 20260805_0012
Revises: 20260805_0011
"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_0012"
down_revision = "20260805_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("worklist_item_id", sa.Uuid(), nullable=False),
        sa.Column("specimen_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("technical_reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("technical_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("technical_review_notes", sa.String(length=500), nullable=True),
        sa.Column("pathologist_validated_by", sa.Uuid(), nullable=True),
        sa.Column("pathologist_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pathologist_notes", sa.String(length=500), nullable=True),
        sa.Column("released_by", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_number", sa.String(length=40), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["pathologist_validated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["analyzer_messages.id"]),
        sa.ForeignKeyConstraint(["specimen_id"], ["specimens.id"]),
        sa.ForeignKeyConstraint(["technical_reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["test_id"], ["test_catalog_items.id"]),
        sa.ForeignKeyConstraint(["worklist_item_id"], ["analyzer_worklist_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worklist_item_id", name="uq_lab_result_worklist_item"),
    )
    op.create_index("ix_lab_results_organization_id", "lab_results", ["organization_id"])
    op.create_index("ix_lab_results_branch_id", "lab_results", ["branch_id"])
    op.create_index("ix_lab_results_worklist_item_id", "lab_results", ["worklist_item_id"])
    op.create_index("ix_lab_results_specimen_id", "lab_results", ["specimen_id"])
    op.create_index("ix_lab_results_order_id", "lab_results", ["order_id"])
    op.create_index("ix_lab_results_test_id", "lab_results", ["test_id"])
    op.create_index("ix_lab_results_analyzer_id", "lab_results", ["analyzer_id"])
    op.create_index("ix_lab_results_source_message_id", "lab_results", ["source_message_id"])
    op.create_index("ix_lab_results_correlation_id", "lab_results", ["correlation_id"])
    op.create_index("ix_lab_results_status", "lab_results", ["status"])
    op.create_index("ix_lab_results_report_number", "lab_results", ["report_number"])
    op.create_index(
        "ix_lab_results_status_created",
        "lab_results",
        ["organization_id", "status", "created_at"],
    )

    op.create_table(
        "lab_result_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("parameter_id", sa.Uuid(), nullable=True),
        sa.Column("machine_parameter_code", sa.String(length=100), nullable=False),
        sa.Column("parameter_name", sa.String(length=200), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("reference_low", sa.String(length=40), nullable=True),
        sa.Column("reference_high", sa.String(length=40), nullable=True),
        sa.Column("reference_text", sa.String(length=200), nullable=True),
        sa.Column("flag", sa.String(length=20), nullable=True),
        sa.Column("raw_obx", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parameter_id"], ["test_catalog_parameters.id"]),
        sa.ForeignKeyConstraint(["result_id"], ["lab_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id", "sequence_no", name="uq_result_observation_sequence"),
    )
    op.create_index(
        "ix_lab_result_observations_result_id", "lab_result_observations", ["result_id"]
    )
    op.create_index(
        "ix_lab_result_observations_parameter_id", "lab_result_observations", ["parameter_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_lab_result_observations_parameter_id", table_name="lab_result_observations")
    op.drop_index("ix_lab_result_observations_result_id", table_name="lab_result_observations")
    op.drop_table("lab_result_observations")
    op.drop_index("ix_lab_results_status_created", table_name="lab_results")
    op.drop_index("ix_lab_results_report_number", table_name="lab_results")
    op.drop_index("ix_lab_results_status", table_name="lab_results")
    op.drop_index("ix_lab_results_correlation_id", table_name="lab_results")
    op.drop_index("ix_lab_results_source_message_id", table_name="lab_results")
    op.drop_index("ix_lab_results_analyzer_id", table_name="lab_results")
    op.drop_index("ix_lab_results_test_id", table_name="lab_results")
    op.drop_index("ix_lab_results_order_id", table_name="lab_results")
    op.drop_index("ix_lab_results_specimen_id", table_name="lab_results")
    op.drop_index("ix_lab_results_worklist_item_id", table_name="lab_results")
    op.drop_index("ix_lab_results_branch_id", table_name="lab_results")
    op.drop_index("ix_lab_results_organization_id", table_name="lab_results")
    op.drop_table("lab_results")

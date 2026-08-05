"""Analyzer worklist, mapping cleanup, and test parameter ranges.

Revision ID: 20260805_0010
Revises: 20260805_0009
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260805_0010"
down_revision = "20260805_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_catalog_parameters", sa.Column("unit", sa.String(length=40), nullable=True))
    op.add_column(
        "test_catalog_parameters", sa.Column("reference_low", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "test_catalog_parameters", sa.Column("reference_high", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "test_catalog_parameters", sa.Column("reference_text", sa.String(length=200), nullable=True)
    )

    op.create_table(
        "analyzer_worklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("specimen_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("machine_test_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("cancelled_reason", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analyzer_id"], ["analyzers.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["mapping_id"], ["analyzer_test_mappings.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["specimen_id"], ["specimens.id"]),
        sa.ForeignKeyConstraint(["test_id"], ["test_catalog_items.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "specimen_id",
            "analyzer_id",
            "test_id",
            name="uq_worklist_specimen_analyzer_test",
        ),
    )
    op.create_index(
        "ix_analyzer_worklist_items_organization_id",
        "analyzer_worklist_items",
        ["organization_id"],
    )
    op.create_index(
        "ix_analyzer_worklist_items_branch_id", "analyzer_worklist_items", ["branch_id"]
    )
    op.create_index(
        "ix_analyzer_worklist_items_specimen_id", "analyzer_worklist_items", ["specimen_id"]
    )
    op.create_index("ix_analyzer_worklist_items_order_id", "analyzer_worklist_items", ["order_id"])
    op.create_index("ix_analyzer_worklist_items_test_id", "analyzer_worklist_items", ["test_id"])
    op.create_index(
        "ix_analyzer_worklist_items_analyzer_id", "analyzer_worklist_items", ["analyzer_id"]
    )
    op.create_index(
        "ix_analyzer_worklist_items_mapping_id", "analyzer_worklist_items", ["mapping_id"]
    )
    op.create_index("ix_analyzer_worklist_items_status", "analyzer_worklist_items", ["status"])
    op.create_index(
        "ix_analyzer_worklist_items_correlation_id",
        "analyzer_worklist_items",
        ["correlation_id"],
    )
    op.create_index(
        "ix_worklist_status_created",
        "analyzer_worklist_items",
        ["organization_id", "status", "created_at"],
    )

    # Remove incorrect UAT mapping BIO0231 -> A4 on Sysmex / HEM-01.
    op.execute(
        sa.text(
            """
            DELETE FROM analyzer_parameter_mappings
            WHERE test_mapping_id IN (
                SELECT m.id
                FROM analyzer_test_mappings m
                JOIN analyzers a ON a.id = m.analyzer_id
                JOIN test_catalog_items t ON t.id = m.test_id
                WHERE t.code = 'BIO0231'
                  AND (a.code = 'HEM-01' OR lower(a.vendor) LIKE '%sysmex%')
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM analyzer_test_mappings
            WHERE id IN (
                SELECT m.id
                FROM analyzer_test_mappings m
                JOIN analyzers a ON a.id = m.analyzer_id
                JOIN test_catalog_items t ON t.id = m.test_id
                WHERE t.code = 'BIO0231'
                  AND (a.code = 'HEM-01' OR lower(a.vendor) LIKE '%sysmex%')
            )
            """
        )
    )

    # Ensure BIO0231 has an Androstenedione parameter for UAT result shape.
    # Reference limits intentionally left null until clinically approved.
    bind = op.get_bind()
    tests = bind.execute(
        sa.text("SELECT id FROM test_catalog_items WHERE code = 'BIO0231'")
    ).fetchall()
    for (test_id,) in tests:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM test_catalog_parameters "
                "WHERE test_id = :test_id AND external_code = 'ANDRO'"
            ),
            {"test_id": test_id},
        ).fetchone()
        if exists:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO test_catalog_parameters (
                    id, test_id, name, external_code, display_order, unit,
                    reference_low, reference_high, reference_text, created_at, updated_at
                ) VALUES (
                    :id, :test_id, 'Androstenedione', 'ANDRO', 1, 'ng/mL',
                    NULL, NULL, 'Reference range pending clinical approval',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"id": uuid.uuid4(), "test_id": test_id},
        )


def downgrade() -> None:
    op.drop_index("ix_worklist_status_created", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_correlation_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_status", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_mapping_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_analyzer_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_test_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_order_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_specimen_id", table_name="analyzer_worklist_items")
    op.drop_index("ix_analyzer_worklist_items_branch_id", table_name="analyzer_worklist_items")
    op.drop_index(
        "ix_analyzer_worklist_items_organization_id", table_name="analyzer_worklist_items"
    )
    op.drop_table("analyzer_worklist_items")
    op.drop_column("test_catalog_parameters", "reference_text")
    op.drop_column("test_catalog_parameters", "reference_high")
    op.drop_column("test_catalog_parameters", "reference_low")
    op.drop_column("test_catalog_parameters", "unit")

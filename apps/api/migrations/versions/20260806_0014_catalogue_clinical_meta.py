"""Add clinical limit metadata and seed BIO0231 ANDRO ranges.

Revision ID: 20260806_0014
Revises: 20260805_0012
Create Date: 2026-08-06
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260806_0014"
down_revision = "20260805_0012"
branch_labels = None
depends_on = None

ANDRO_SOURCE = "UAT provisional limits — confirm with laboratory before clinical use"


def upgrade() -> None:
    op.add_column(
        "test_catalog_parameters",
        sa.Column("critical_low", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "test_catalog_parameters",
        sa.Column("critical_high", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "test_catalog_parameters",
        sa.Column("reference_source", sa.String(length=200), nullable=True),
    )

    connection = op.get_bind()
    tests = (
        connection.execute(
            sa.text("SELECT id, organization_id FROM test_catalog_items WHERE code = 'BIO0231'")
        )
        .mappings()
        .all()
    )
    for test in tests:
        connection.execute(
            sa.text(
                """
                UPDATE test_catalog_items
                SET specimen_type = CASE
                        WHEN lower(coalesce(specimen_type, '')) IN ('', 'specimen', 'unspecified')
                        THEN 'Serum' ELSE specimen_type END,
                    container_type = CASE
                        WHEN lower(coalesce(container_type, '')) IN ('', 'unspecified')
                        THEN 'SST clot activator' ELSE container_type END,
                    price = CASE WHEN coalesce(price, 0) <= 0 THEN 900.00 ELSE price END,
                    is_panel = true,
                    validation_status = 'validated',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :test_id
                """
            ),
            {"test_id": test["id"]},
        )
        existing = connection.execute(
            sa.text(
                """
                SELECT id FROM test_catalog_parameters
                WHERE test_id = :test_id AND upper(external_code) = 'ANDRO'
                """
            ),
            {"test_id": test["id"]},
        ).first()
        if existing:
            connection.execute(
                sa.text(
                    """
                    UPDATE test_catalog_parameters
                    SET name = coalesce(nullif(name, ''), 'Androstenedione'),
                        unit = coalesce(nullif(unit, ''), 'ng/mL'),
                        reference_low = coalesce(nullif(reference_low, ''), '0.3'),
                        reference_high = coalesce(nullif(reference_high, ''), '3.5'),
                        reference_text = coalesce(
                            nullif(reference_text, ''),
                            'Adult reference interval (provisional UAT)'
                        ),
                        reference_source = coalesce(nullif(reference_source, ''), :source),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :parameter_id
                    """
                ),
                {"parameter_id": existing[0], "source": ANDRO_SOURCE},
            )
        else:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO test_catalog_parameters (
                        id, test_id, name, external_code, display_order, unit,
                        reference_low, reference_high, reference_text,
                        critical_low, critical_high, reference_source,
                        created_at, updated_at
                    ) VALUES (
                        :id, :test_id, 'Androstenedione', 'ANDRO', 1, 'ng/mL',
                        '0.3', '3.5', 'Adult reference interval (provisional UAT)',
                        NULL, NULL, :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "test_id": test["id"],
                    "source": ANDRO_SOURCE,
                },
            )


def downgrade() -> None:
    op.drop_column("test_catalog_parameters", "reference_source")
    op.drop_column("test_catalog_parameters", "critical_high")
    op.drop_column("test_catalog_parameters", "critical_low")

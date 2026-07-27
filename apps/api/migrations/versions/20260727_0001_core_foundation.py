"""LAB-19 LAB-20 LAB-21 core foundation schema.

Revision ID: 20260727_0001
Revises:
"""

from alembic import op
from app import models  # noqa: F401
from app.database import Base

revision = "20260727_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'audit_events are append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation")
    Base.metadata.drop_all(bind=bind)

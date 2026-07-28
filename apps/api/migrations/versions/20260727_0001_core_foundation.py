"""LAB-19 LAB-20 LAB-21 core foundation schema.

Revision ID: 20260727_0001
Revises:
"""

from alembic import op
from app.models import (
    AuditEvent,
    Branch,
    Department,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)

revision = "20260727_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in [
        Organization.__table__,
        Branch.__table__,
        Department.__table__,
        User.__table__,
        Role.__table__,
        Permission.__table__,
        RolePermission.__table__,
        UserRoleAssignment.__table__,
        AuditEvent.__table__,
    ]:
        table.create(bind=bind, checkfirst=True)
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
    for table in [
        AuditEvent.__table__,
        UserRoleAssignment.__table__,
        RolePermission.__table__,
        Permission.__table__,
        Role.__table__,
        User.__table__,
        Department.__table__,
        Branch.__table__,
        Organization.__table__,
    ]:
        table.drop(bind=bind, checkfirst=True)

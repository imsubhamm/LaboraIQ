import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.auth import AuthContext
from app.models import AuditEvent

MASKED_KEYS = {"password", "token", "access_token", "refresh_token", "secret", "authorization"}


def mask_sensitive(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        key: "***MASKED***" if key.lower() in MASKED_KEYS else item for key, item in value.items()
    }


def record_event(
    db: Session,
    request: Request,
    context: AuthContext,
    *,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None,
    action: str,
    branch_id: uuid.UUID | None = None,
    previous: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event_record = AuditEvent(
        organization_id=context.organization_id,
        branch_id=branch_id,
        actor_user_id=context.user_id,
        actor_type="user",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        action=action,
        previous_value=mask_sensitive(previous),
        new_value=mask_sensitive(new),
        correlation_id=request.state.correlation_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        additional_metadata=mask_sensitive(metadata),
    )
    db.add(event_record)
    return event_record


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_audit_mutation(*_: object) -> None:
    raise ValueError("Audit events are immutable")

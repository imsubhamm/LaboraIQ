import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import router
from app.config import get_settings
from app.database import SessionLocal
from app.models import AuditEvent, User

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="LaboraIQ Core Platform API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-User-Email", "X-Correlation-ID"],
)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    if int(request.headers.get("content-length", "0") or 0) > 1_048_576:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
    response = await call_next(request)
    authenticated_user = getattr(request.state, "auth", None)
    if response.status_code == 403 and isinstance(authenticated_user, User):
        with SessionLocal() as audit_db:
            audit_db.add(
                AuditEvent(
                    organization_id=authenticated_user.organization_id,
                    actor_user_id=authenticated_user.id,
                    actor_type="user",
                    event_type="access.denied",
                    entity_type="route",
                    entity_id=request.url.path,
                    action=request.method,
                    correlation_id=correlation_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    additional_metadata={"reason": "insufficient_permission_or_scope"},
                )
            )
            try:
                audit_db.commit()
            except Exception:  # pragma: no cover - denial response must remain available
                logging.getLogger(__name__).exception("Unable to persist denied-access audit event")
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(router, prefix="/api/v1")

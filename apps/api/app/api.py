import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record_event
from app.auth import AuthContext, require_permission
from app.database import get_db
from app.models import (
    AuditEvent,
    Branch,
    Department,
    Organization,
    Permission,
    Role,
    User,
    UserRoleAssignment,
)
from app.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AuditEventRead,
    BranchCreate,
    BranchRead,
    BranchUpdate,
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    Page,
    PermissionRead,
    RoleCreate,
    RoleRead,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
ModelT = TypeVar("ModelT")


def page(db: Session, statement: Any, model: type[ModelT], limit: int, offset: int) -> Page[ModelT]:
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(db.scalars(statement.limit(limit).offset(offset)).all())
    return Page[model](items=items, total=total, limit=limit, offset=offset)  # type: ignore[valid-type]


def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A record with this code already exists"
        ) from error


def flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A record with this code already exists"
        ) from error


def get_tenant_record(
    db: Session, model: type[ModelT], record_id: uuid.UUID, context: AuthContext
) -> ModelT:
    record = db.scalar(
        select(model).where(
            model.id == record_id,  # type: ignore[attr-defined]
            model.organization_id == context.organization_id,  # type: ignore[attr-defined]
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


def snapshot(record: Any, keys: list[str]) -> dict[str, Any]:
    return {key: getattr(record, key) for key in keys}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Db) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ready"}


@router.get("/organizations", response_model=Page[OrganizationRead])
def list_organizations(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("organization.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[OrganizationRead]:
    statement = (
        select(Organization)
        .where(Organization.id == context.organization_id)
        .order_by(Organization.code, Organization.id)
    )
    return page(db, statement, OrganizationRead, limit, offset)


@router.post("/organizations", response_model=OrganizationRead, status_code=201)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("organization.manage"))],
) -> Organization:
    if db.scalar(select(Organization).where(Organization.id == context.organization_id)):
        raise HTTPException(
            status_code=403, detail="Tenant users cannot create another organization"
        )
    organization = Organization(
        **payload.model_dump(), created_by=context.user_id, updated_by=context.user_id
    )
    db.add(organization)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="organization.created",
        entity_type="organization",
        entity_id=organization.id,
        action="create",
        new=payload.model_dump(),
    )
    commit(db)
    return organization


@router.get("/organizations/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("organization.read"))],
) -> Organization:
    if organization_id != context.organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.patch("/organizations/{organization_id}", response_model=OrganizationRead)
def update_organization(
    organization_id: uuid.UUID,
    payload: OrganizationUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("organization.manage"))],
) -> Organization:
    organization = get_organization(organization_id, db, context)
    previous = snapshot(organization, ["name", "status"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(organization, key, value)
    organization.updated_by = context.user_id
    record_event(
        db,
        request,
        context,
        event_type="organization.updated",
        entity_type="organization",
        entity_id=organization.id,
        action="update",
        previous=previous,
        new=snapshot(organization, ["name", "status"]),
    )
    commit(db)
    return organization


@router.get("/branches", response_model=Page[BranchRead])
def list_branches(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BranchRead]:
    statement = select(Branch).where(Branch.organization_id == context.organization_id)
    if not context.is_organization_scoped:
        statement = statement.where(Branch.id.in_(context.branch_ids))
    return page(db, statement.order_by(Branch.code, Branch.id), BranchRead, limit, offset)


@router.post("/branches", response_model=BranchRead, status_code=201)
def create_branch(
    payload: BranchCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.manage"))],
) -> Branch:
    if not context.is_organization_scoped:
        raise HTTPException(status_code=403, detail="Organization-scoped role required")
    branch = Branch(
        **payload.model_dump(),
        organization_id=context.organization_id,
        created_by=context.user_id,
        updated_by=context.user_id,
    )
    db.add(branch)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="branch.created",
        entity_type="branch",
        entity_id=branch.id,
        branch_id=branch.id,
        action="create",
        new=payload.model_dump(),
    )
    commit(db)
    return branch


@router.get("/branches/{branch_id}", response_model=BranchRead)
def get_branch(
    branch_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.read"))],
) -> Branch:
    branch = get_tenant_record(db, Branch, branch_id, context)
    if not context.can_access_branch(branch.id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    return branch


@router.patch("/branches/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.manage"))],
) -> Branch:
    branch = get_branch(branch_id, db, context)
    previous = snapshot(branch, ["name", "address", "time_zone", "status"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, key, value)
    branch.updated_by = context.user_id
    record_event(
        db,
        request,
        context,
        event_type="branch.updated",
        entity_type="branch",
        entity_id=branch.id,
        branch_id=branch.id,
        action="update",
        previous=previous,
        new=snapshot(branch, ["name", "address", "time_zone", "status"]),
    )
    commit(db)
    return branch


@router.get("/departments", response_model=Page[DepartmentRead])
def list_departments(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DepartmentRead]:
    statement = select(Department).where(Department.organization_id == context.organization_id)
    if not context.is_organization_scoped:
        statement = statement.where(Department.branch_id.in_(context.branch_ids))
    return page(
        db, statement.order_by(Department.code, Department.id), DepartmentRead, limit, offset
    )


@router.post("/departments", response_model=DepartmentRead, status_code=201)
def create_department(
    payload: DepartmentCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.manage"))],
) -> Department:
    if payload.branch_id:
        get_branch(payload.branch_id, db, context)
    elif not context.is_organization_scoped:
        raise HTTPException(status_code=403, detail="Organization-scoped role required")
    department = Department(**payload.model_dump(), organization_id=context.organization_id)
    db.add(department)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="department.created",
        entity_type="department",
        entity_id=department.id,
        branch_id=department.branch_id,
        action="create",
        new=payload.model_dump(mode="json"),
    )
    commit(db)
    return department


@router.get("/departments/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.read"))],
) -> Department:
    department = get_tenant_record(db, Department, department_id, context)
    if not context.can_access_branch(department.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    return department


@router.patch("/departments/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("branch.manage"))],
) -> Department:
    department = get_department(department_id, db, context)
    previous = snapshot(department, ["name", "status"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(department, key, value)
    record_event(
        db,
        request,
        context,
        event_type="department.updated",
        entity_type="department",
        entity_id=department.id,
        branch_id=department.branch_id,
        action="update",
        previous=previous,
        new=snapshot(department, ["name", "status"]),
    )
    commit(db)
    return department


@router.get("/users", response_model=Page[UserRead])
def list_users(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("user.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserRead]:
    statement = (
        select(User)
        .where(User.organization_id == context.organization_id)
        .order_by(User.email, User.id)
    )
    return page(db, statement, UserRead, limit, offset)


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("user.manage"))],
) -> User:
    user = User(**payload.model_dump(), organization_id=context.organization_id)
    db.add(user)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="user.created",
        entity_type="user",
        entity_id=user.id,
        action="create",
        new=payload.model_dump(),
    )
    commit(db)
    return user


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("user.read"))],
) -> User:
    return get_tenant_record(db, User, user_id, context)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("user.manage"))],
) -> User:
    user = get_user(user_id, db, context)
    previous = snapshot(user, ["display_name", "status"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    event_type = "user.status_changed" if payload.status is not None else "user.updated"
    record_event(
        db,
        request,
        context,
        event_type=event_type,
        entity_type="user",
        entity_id=user.id,
        action="update",
        previous=previous,
        new=snapshot(user, ["display_name", "status"]),
    )
    commit(db)
    return user


@router.get("/roles", response_model=Page[RoleRead])
def list_roles(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("role.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RoleRead]:
    statement = (
        select(Role)
        .where((Role.organization_id == context.organization_id) | (Role.organization_id.is_(None)))
        .order_by(Role.name, Role.id)
    )
    return page(db, statement, RoleRead, limit, offset)


@router.post("/roles", response_model=RoleRead, status_code=201)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("role.manage"))],
) -> Role:
    permissions = list(
        db.scalars(select(Permission).where(Permission.code.in_(payload.permission_codes))).all()
    )
    if len(permissions) != len(set(payload.permission_codes)):
        raise HTTPException(status_code=422, detail="One or more permissions are unknown")
    role = Role(
        organization_id=context.organization_id,
        name=payload.name,
        description=payload.description,
        permissions=permissions,
    )
    db.add(role)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="role.created",
        entity_type="role",
        entity_id=role.id,
        action="create",
        new=payload.model_dump(),
    )
    commit(db)
    return role


@router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(
    db: Db, _: Annotated[AuthContext, Depends(require_permission("role.read"))]
) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.code)).all())


@router.post("/user-role-assignments", response_model=AssignmentRead, status_code=201)
def assign_role(
    payload: AssignmentCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("role.manage"))],
) -> UserRoleAssignment:
    get_user(payload.user_id, db, context)
    role = db.scalar(
        select(Role).where(
            Role.id == payload.role_id,
            (Role.organization_id == context.organization_id) | (Role.organization_id.is_(None)),
        )
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if payload.branch_id:
        get_branch(payload.branch_id, db, context)
    assignment_data = payload.model_dump(exclude={"effective_at"})
    assignment = UserRoleAssignment(
        **assignment_data,
        organization_id=context.organization_id,
        assigned_by=context.user_id,
        effective_at=payload.effective_at or datetime.now(UTC),
    )
    db.add(assignment)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="role.assigned",
        entity_type="user_role_assignment",
        entity_id=assignment.id,
        branch_id=assignment.branch_id,
        action="assign",
        new=payload.model_dump(mode="json"),
    )
    commit(db)
    return assignment


@router.delete("/user-role-assignments/{assignment_id}", status_code=204)
def revoke_role(
    assignment_id: uuid.UUID,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("role.manage"))],
) -> Response:
    assignment = get_tenant_record(db, UserRoleAssignment, assignment_id, context)
    if not context.can_access_branch(assignment.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    assignment.active = False
    record_event(
        db,
        request,
        context,
        event_type="role.revoked",
        entity_type="user_role_assignment",
        entity_id=assignment.id,
        branch_id=assignment.branch_id,
        action="deactivate",
        previous={"active": True},
        new={"active": False},
    )
    commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audit-events", response_model=Page[AuditEventRead])
def list_audit_events(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("audit.read"))],
    event_type: str | None = None,
    entity_type: str | None = None,
    branch_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEventRead]:
    statement = select(AuditEvent).where(AuditEvent.organization_id == context.organization_id)
    if not context.is_organization_scoped:
        statement = statement.where(AuditEvent.branch_id.in_(context.branch_ids))
    if branch_id:
        if not context.can_access_branch(branch_id):
            raise HTTPException(status_code=403, detail="Branch access denied")
        statement = statement.where(AuditEvent.branch_id == branch_id)
    if event_type:
        statement = statement.where(AuditEvent.event_type == event_type)
    if entity_type:
        statement = statement.where(AuditEvent.entity_type == entity_type)
    statement = statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    return page(db, statement, AuditEventRead, limit, offset)


@router.get("/audit-events/{event_id}", response_model=AuditEventRead)
def get_audit_event(
    event_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("audit.read"))],
) -> AuditEvent:
    event_record = get_tenant_record(db, AuditEvent, event_id, context)
    if not context.can_access_branch(event_record.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    return event_record

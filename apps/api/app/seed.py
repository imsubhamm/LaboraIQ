from datetime import UTC, datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Branch,
    Department,
    Organization,
    Permission,
    Role,
    User,
    UserRoleAssignment,
)

PERMISSIONS = {
    "organization.read": "View organization configuration",
    "organization.manage": "Manage organization configuration",
    "branch.read": "View branches and departments",
    "branch.manage": "Manage branches and departments",
    "user.read": "View users",
    "user.manage": "Manage users",
    "role.read": "View roles and permissions",
    "role.manage": "Manage roles and assignments",
    "audit.read": "View audit events",
    "validation.read": "View validation evidence",
    "validation.manage": "Manage validation evidence",
}

ROLE_TEMPLATES = {
    "Platform Administrator": list(PERMISSIONS),
    "Laboratory Administrator": list(PERMISSIONS),
    "Technician": ["branch.read"],
    "Pathologist": ["branch.read"],
    "Quality Manager": [
        "organization.read",
        "branch.read",
        "user.read",
        "role.read",
        "audit.read",
        "validation.read",
        "validation.manage",
    ],
    "Billing User": ["branch.read"],
    "Collection User": ["branch.read"],
    "Auditor": [
        "organization.read",
        "branch.read",
        "user.read",
        "role.read",
        "audit.read",
        "validation.read",
    ],
}


def seed() -> None:
    with SessionLocal() as db:
        permissions = {}
        for code, description in PERMISSIONS.items():
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if not permission:
                permission = Permission(code=code, description=description)
                db.add(permission)
            permissions[code] = permission
        db.flush()

        roles = {}
        for name, codes in ROLE_TEMPLATES.items():
            role = db.scalar(select(Role).where(Role.organization_id.is_(None), Role.name == name))
            if not role:
                role = Role(
                    name=name,
                    description=f"Configurable {name} starter template",
                    is_template=True,
                    permissions=[permissions[code] for code in codes],
                )
                db.add(role)
            roles[name] = role
        db.flush()

        organization = db.scalar(select(Organization).where(Organization.code == "DEVLAB"))
        if not organization:
            organization = Organization(name="LaboraIQ Development Laboratory", code="DEVLAB")
            db.add(organization)
            db.flush()

        branch = db.scalar(
            select(Branch).where(Branch.organization_id == organization.id, Branch.code == "KOL")
        )
        if not branch:
            branch = Branch(
                organization_id=organization.id,
                name="Kolkata Development Branch",
                code="KOL",
                time_zone="Asia/Kolkata",
            )
            db.add(branch)
            db.flush()

        for name, code in [("Chemistry", "CHEM"), ("Haematology", "HAEM")]:
            existing = db.scalar(
                select(Department).where(
                    Department.organization_id == organization.id,
                    Department.branch_id == branch.id,
                    Department.code == code,
                )
            )
            if not existing:
                db.add(
                    Department(
                        organization_id=organization.id,
                        branch_id=branch.id,
                        name=name,
                        code=code,
                    )
                )

        user = db.scalar(select(User).where(User.email == "admin@dev.labora.local"))
        if not user:
            user = User(
                organization_id=organization.id,
                email="admin@dev.labora.local",
                display_name="Development Administrator",
                auth_provider_id="dev:admin@dev.labora.local",
            )
            db.add(user)
            db.flush()
        assignment = db.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.role_id == roles["Laboratory Administrator"].id,
                UserRoleAssignment.active.is_(True),
            )
        )
        if not assignment:
            db.add(
                UserRoleAssignment(
                    organization_id=organization.id,
                    user_id=user.id,
                    role_id=roles["Laboratory Administrator"].id,
                    effective_at=datetime.now(UTC),
                    assigned_by=user.id,
                    assignment_reason="Development environment bootstrap",
                )
            )
        db.commit()


if __name__ == "__main__":
    seed()

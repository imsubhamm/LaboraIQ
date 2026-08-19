from datetime import UTC, datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Branch,
    Department,
    Organization,
    Permission,
    Role,
    TestCatalogItem,
    TestCatalogParameter,
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
    "test_master.read": "View the LIS/HIS test master",
    "test_master.manage": "Manage and import the LIS/HIS test master",
    "analyzer.read": "View analyzer configurations",
    "analyzer.manage": "Manage analyzer configurations",
    "result.read": "View laboratory results and reports",
    "result.review": "Perform technical review of results",
    "result.validate": "Pathologist validation of results",
    "result.release": "Release validated laboratory reports",
}

ROLE_TEMPLATES = {
    "Platform Administrator": list(PERMISSIONS),
    "Laboratory Administrator": list(PERMISSIONS),
    "Technician": [
        "branch.read",
        "analyzer.read",
        "result.read",
        "result.review",
    ],
    "Pathologist": [
        "branch.read",
        "analyzer.read",
        "result.read",
        "result.validate",
        "result.release",
    ],
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
            else:
                assigned_codes = {permission.code for permission in role.permissions}
                role.permissions.extend(
                    permissions[code] for code in codes if code not in assigned_codes
                )
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

        test_catalog = [
            ("CBC", "Complete Blood Count (CBC)", "Whole blood", "EDTA lavender tube", "450.00"),
            ("LIPID", "Lipid Profile", "Serum", "Clot activator red tube", "900.00"),
            ("LFT", "Liver Function Test", "Serum", "Clot activator red tube", "850.00"),
            ("KFT", "Kidney Function Test", "Serum", "Clot activator red tube", "800.00"),
            ("THYROID", "Thyroid Profile", "Serum", "Clot activator red tube", "950.00"),
            ("HBA1C", "HbA1c", "Whole blood", "EDTA lavender tube", "650.00"),
            ("VITD", "Vitamin D", "Serum", "Clot activator red tube", "1400.00"),
            ("URINE", "Urine Routine", "Urine", "Sterile urine container", "300.00"),
            (
                "BIO0231",
                "A4 - Androstenedione Test",
                "Serum",
                "SST clot activator",
                "900.00",
            ),
        ]
        for test_code, test_name, specimen, container, price in test_catalog:
            existing_test = db.scalar(
                select(TestCatalogItem).where(
                    TestCatalogItem.organization_id == organization.id,
                    TestCatalogItem.code == test_code,
                )
            )
            if not existing_test:
                existing_test = TestCatalogItem(
                    organization_id=organization.id,
                    code=test_code,
                    name=test_name,
                    specimen_type=specimen,
                    container_type=container,
                    price=price,
                    validation_status="validated",
                )
                db.add(existing_test)
                db.flush()
            if test_code == "BIO0231":
                existing_test.specimen_type = specimen
                existing_test.container_type = container
                existing_test.price = price
                existing_test.is_panel = True
                andro = next(
                    (
                        parameter
                        for parameter in existing_test.parameters
                        if parameter.external_code.upper() == "ANDRO"
                    ),
                    None,
                )
                if andro is None:
                    existing_test.parameters.append(
                        TestCatalogParameter(
                            name="Androstenedione",
                            external_code="ANDRO",
                            display_order=1,
                            unit="ng/mL",
                            reference_low="0.3",
                            reference_high="3.5",
                            reference_text="Adult reference interval (provisional UAT)",
                            reference_source=(
                                "UAT provisional limits — confirm with laboratory "
                                "before clinical use"
                            ),
                        )
                    )
                else:
                    andro.unit = andro.unit or "ng/mL"
                    andro.reference_low = andro.reference_low or "0.3"
                    andro.reference_high = andro.reference_high or "3.5"
                    andro.reference_text = (
                        andro.reference_text or "Adult reference interval (provisional UAT)"
                    )
                    andro.reference_source = andro.reference_source or (
                        "UAT provisional limits — confirm with laboratory before clinical use"
                    )
                existing_test.validation_status = "validated"

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

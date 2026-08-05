import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from app.auth import AuthContext, get_auth_context
from app.database import Base, get_db
from app.main import app
from app.models import Organization, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db() -> Session:
    Base.metadata.create_all(engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def context(db: Session) -> AuthContext:
    org = Organization(name="Alpha Labs", code="ALPHA")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email="admin@alpha.test",
        display_name="Alpha Admin",
        auth_provider_id="test:alpha",
    )
    db.add(user)
    db.commit()
    return AuthContext(
        user_id=user.id,
        organization_id=org.id,
        email=user.email,
        branch_ids=frozenset(),
        permissions=frozenset(
            {
                "organization.read",
                "organization.manage",
                "branch.read",
                "branch.manage",
                "user.read",
                "user.manage",
                "role.read",
                "role.manage",
                "audit.read",
                "test_master.read",
                "test_master.manage",
                "analyzer.read",
                "analyzer.manage",
                "result.read",
                "result.review",
                "result.validate",
                "result.release",
            }
        ),
        is_organization_scoped=True,
    )


@pytest.fixture
def client(db: Session, context: AuthContext) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_auth_context] = lambda: context
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

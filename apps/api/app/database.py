from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
pool_options = (
    {}
    if settings.database_url.startswith("sqlite")
    else {
        # Analyzer TCP exchange can hold a request for several seconds; keep enough
        # spare connections so list endpoints (patients, etc.) do not time out.
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "pool_use_lifo": True,
    }
)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    **pool_options,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

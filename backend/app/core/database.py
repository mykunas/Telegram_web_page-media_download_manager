from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


# SQLite needs check_same_thread=False for usage across different threads.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: provide a database session and close it after request."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables declared by SQLAlchemy models."""

    # Import models so SQLAlchemy metadata can discover all table definitions.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def initialize_database() -> None:
    """Application-level database initialization entrypoint."""

    init_db()

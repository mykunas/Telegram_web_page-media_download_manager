from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


# SQLite needs check_same_thread=False for usage across different threads.
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        """Apply low-risk concurrency and integrity settings to every SQLite connection."""

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: provide a database session and close it after request."""

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
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
    from app.core.migrations import run_migrations

    run_migrations(engine)

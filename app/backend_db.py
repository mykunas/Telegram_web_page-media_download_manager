import sys
from contextlib import contextmanager
from pathlib import Path


_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.database import SessionLocal, initialize_database  # noqa: E402
from app.models import DownloadRecord, DownloadStatus, ErrorLog, SyncStatus, SystemLog  # noqa: E402


@contextmanager
def db_session_scope():
    """Provide a transactional database session scope."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "DownloadRecord",
    "DownloadStatus",
    "ErrorLog",
    "SyncStatus",
    "SystemLog",
    "db_session_scope",
    "initialize_database",
]

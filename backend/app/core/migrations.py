from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Engine, text


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        payload = "\n-- statement --\n".join(statement.strip() for statement in self.statements)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="operational_indexes",
        statements=(
            "CREATE INDEX IF NOT EXISTS ix_download_records_chat_status ON download_records(chat_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_download_records_status_created ON download_records(status, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_sync_statuses_status ON sync_statuses(sync_status)",
            "CREATE INDEX IF NOT EXISTS ix_system_logs_created_at ON system_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_error_logs_created_at ON error_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_user_actions_user_created ON user_actions(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_collection_items_collection_sort ON user_collection_items(collection_id, sort_order)",
        ),
    ),
    Migration(
        version=2,
        name="relationship_guards",
        statements=(
            """
            CREATE TRIGGER IF NOT EXISTS trg_play_progress_record_insert
            BEFORE INSERT ON play_progress
            WHEN NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'play_progress record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_play_progress_record_update
            BEFORE UPDATE OF record_id ON play_progress
            WHEN NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'play_progress record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_recommendation_record_insert
            BEFORE INSERT ON daily_recommendations
            WHEN NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'recommendation record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_recommendation_record_update
            BEFORE UPDATE OF record_id ON daily_recommendations
            WHEN NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'recommendation record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_collection_item_insert
            BEFORE INSERT ON user_collection_items
            WHEN NOT EXISTS (SELECT 1 FROM user_collections WHERE id = NEW.collection_id)
              OR NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'collection or download record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_collection_item_update
            BEFORE UPDATE OF collection_id, record_id ON user_collection_items
            WHEN NOT EXISTS (SELECT 1 FROM user_collections WHERE id = NEW.collection_id)
              OR NOT EXISTS (SELECT 1 FROM download_records WHERE id = NEW.record_id)
            BEGIN SELECT RAISE(ABORT, 'collection or download record does not exist'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_collection_delete_cascade
            AFTER DELETE ON user_collections
            BEGIN DELETE FROM user_collection_items WHERE collection_id = OLD.id; END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_download_record_delete_cascade
            AFTER DELETE ON download_records
            BEGIN
                DELETE FROM play_progress WHERE record_id = OLD.id;
                DELETE FROM daily_recommendations WHERE record_id = OLD.id;
                DELETE FROM user_collection_items WHERE record_id = OLD.id;
                UPDATE user_actions SET record_id = NULL WHERE record_id = OLD.id;
            END
            """,
        ),
    ),
    Migration(
        version=3,
        name="numeric_guards",
        statements=(
            """
            CREATE TRIGGER IF NOT EXISTS trg_download_record_numeric_insert
            BEFORE INSERT ON download_records
            WHEN NEW.retry_count < 0 OR (NEW.file_size IS NOT NULL AND NEW.file_size < 0)
            BEGIN SELECT RAISE(ABORT, 'download numeric values must be non-negative'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_download_record_numeric_update
            BEFORE UPDATE OF retry_count, file_size ON download_records
            WHEN NEW.retry_count < 0 OR (NEW.file_size IS NOT NULL AND NEW.file_size < 0)
            BEGIN SELECT RAISE(ABORT, 'download numeric values must be non-negative'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_play_progress_numeric_insert
            BEFORE INSERT ON play_progress
            WHEN NEW.last_position_sec < 0 OR NEW.duration_sec < 0
            BEGIN SELECT RAISE(ABORT, 'play progress values must be non-negative'); END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_play_progress_numeric_update
            BEFORE UPDATE OF last_position_sec, duration_sec ON play_progress
            WHEN NEW.last_position_sec < 0 OR NEW.duration_sec < 0
            BEGIN SELECT RAISE(ABORT, 'play progress values must be non-negative'); END
            """,
        ),
    ),
)


CREATE_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


def run_migrations(engine: Engine) -> list[int]:
    """Apply pending migrations transactionally and verify applied checksums."""

    if engine.dialect.name != "sqlite":
        return []

    with engine.begin() as connection:
        connection.exec_driver_sql(CREATE_MIGRATION_TABLE)
        applied = {
            int(row.version): (str(row.name), str(row.checksum))
            for row in connection.execute(text("SELECT version, name, checksum FROM schema_migrations"))
        }

    applied_now: list[int] = []
    for migration in MIGRATIONS:
        existing = applied.get(migration.version)
        if existing:
            if existing != (migration.name, migration.checksum):
                raise RuntimeError(f"database migration checksum mismatch at version {migration.version}")
            continue

        with engine.begin() as connection:
            for statement in migration.statements:
                connection.exec_driver_sql(statement)
            connection.execute(
                text(
                    "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                    "VALUES (:version, :name, :checksum, :applied_at)"
                ),
                {
                    "version": migration.version,
                    "name": migration.name,
                    "checksum": migration.checksum,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        applied_now.append(migration.version)
    return applied_now


def current_schema_version(engine: Engine) -> int:
    if engine.dialect.name != "sqlite":
        return 0
    with engine.connect() as connection:
        exists = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).scalar()
        if not exists:
            return 0
        return int(connection.exec_driver_sql("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").scalar_one())

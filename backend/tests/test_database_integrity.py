from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import models  # noqa: E402,F401
from app.core.database import Base  # noqa: E402
from app.core.database_health import inspect_database  # noqa: E402
from app.core.migrations import MIGRATIONS, current_schema_version, run_migrations  # noqa: E402
from app.core.sqlite_backup import create_backup, restore_backup, verify_backup  # noqa: E402


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "app.db"
        self.engine = create_engine(f"sqlite:///{self.database.as_posix()}")
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.tempdir.cleanup()

    def test_migrations_are_idempotent_and_recorded(self) -> None:
        self.assertEqual(run_migrations(self.engine), [migration.version for migration in MIGRATIONS])
        self.assertEqual(run_migrations(self.engine), [])
        self.assertEqual(current_schema_version(self.engine), MIGRATIONS[-1].version)

    def test_relationship_trigger_rejects_orphan_and_rolls_back_transaction(self) -> None:
        run_migrations(self.engine)
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO download_records(chat_id,message_id,status,retry_count) VALUES (1,1,'WAITING',0)"
            )
            connection.exec_driver_sql(
                "INSERT INTO play_progress(user_id,record_id,last_position_sec,duration_sec,is_completed) "
                "VALUES (1,999,0,0,0)"
            )
        with self.engine.connect() as connection:
            count = connection.exec_driver_sql("SELECT COUNT(1) FROM download_records").scalar_one()
        self.assertEqual(count, 0)

    def test_database_health_reports_valid_database(self) -> None:
        run_migrations(self.engine)
        health = inspect_database(self.engine, full=True)
        self.assertTrue(health["valid"])
        self.assertEqual(health["schema_version"], MIGRATIONS[-1].version)


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = self.root / "source.db"
        with sqlite3.connect(self.source) as connection:
            connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO sample(value) VALUES ('before')")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_backup_verify_and_restore_round_trip(self) -> None:
        backup = self.root / "backup.db"
        manifest = create_backup(self.source, backup)
        self.assertEqual(manifest["integrity_check"], "ok")
        self.assertEqual(verify_backup(backup)["sha256"], manifest["sha256"])

        restored = self.root / "restored.db"
        restore_backup(backup, restored, confirmation="RESTORE_DATABASE")
        with sqlite3.connect(restored) as connection:
            value = connection.execute("SELECT value FROM sample").fetchone()[0]
        self.assertEqual(value, "before")

    def test_restore_requires_explicit_confirmation(self) -> None:
        backup = self.root / "backup.db"
        create_backup(self.source, backup)
        with self.assertRaises(ValueError):
            restore_backup(backup, self.root / "restored.db", confirmation="yes")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_sqlite(path: Path, *, full: bool = False) -> list[str]:
    resolved = path.resolve(strict=True)
    with sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True) as connection:
        pragma = "PRAGMA integrity_check" if full else "PRAGMA quick_check"
        return [str(row[0]) for row in connection.execute(pragma)]


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def create_backup(source: Path, destination: Path) -> dict:
    """Create a consistent online SQLite backup and a SHA-256 manifest."""

    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if source == destination:
        raise ValueError("backup destination must differ from the source database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    temporary_size = 0
    temporary_checksum = ""

    try:
        with (
            sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as source_connection,
            sqlite3.connect(temporary) as backup_connection,
        ):
            source_connection.backup(backup_connection)
            # A backup copies the source journal mode. Publish a standalone
            # database so the artifact never depends on temporary WAL files.
            backup_connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            backup_connection.commit()
        if check_sqlite(temporary, full=True) != ["ok"]:
            raise RuntimeError("backup integrity check failed")
        temporary_size = temporary.stat().st_size
        temporary_checksum = sha256_file(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
        Path(f"{temporary}-wal").unlink(missing_ok=True)
        Path(f"{temporary}-shm").unlink(missing_ok=True)

    manifest = {
        "format": "telegram-media-center-sqlite-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_name": source.name,
        "backup_name": destination.name,
        "size_bytes": temporary_size,
        "sha256": temporary_checksum,
        "integrity_check": "ok",
    }
    _atomic_json(destination.with_suffix(destination.suffix + ".manifest.json"), manifest)
    return manifest


def verify_backup(backup: Path) -> dict:
    backup = backup.resolve(strict=True)
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    if not manifest_path.is_file():
        raise RuntimeError("backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "telegram-media-center-sqlite-backup-v1":
        raise RuntimeError("backup manifest format is unsupported")
    if manifest.get("sha256") != sha256_file(backup):
        raise RuntimeError("backup checksum mismatch")
    if check_sqlite(backup, full=True) != ["ok"]:
        raise RuntimeError("backup integrity check failed")
    return manifest


def restore_backup(backup: Path, target: Path, *, confirmation: str) -> Path | None:
    """Restore an offline database, retaining a verified pre-restore snapshot."""

    if confirmation != "RESTORE_DATABASE":
        raise ValueError("confirmation must equal RESTORE_DATABASE")
    backup = backup.resolve(strict=True)
    target = target.resolve(strict=False)
    verify_backup(backup)
    target.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    previous = target.with_name(f"{target.name}.pre-restore-{timestamp}") if target.exists() else None
    if previous:
        create_backup(target, previous)

    temporary = target.with_suffix(target.suffix + ".restore.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with (
            sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True) as source_connection,
            sqlite3.connect(temporary) as target_connection,
        ):
            source_connection.backup(target_connection)
        if check_sqlite(temporary, full=True) != ["ok"]:
            raise RuntimeError("restored database integrity check failed")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return previous

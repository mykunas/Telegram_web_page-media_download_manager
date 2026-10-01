# SQLite Backup and Disaster Recovery

## What must be protected

- `data/app.db`: records, settings, user state, and potentially Telegram secrets.
- `session/`: high-value Telegram authorization credentials.
- `.env`: bootstrap configuration and credentials.
- Downloads, when the original Telegram source cannot be relied upon.

These are separate recovery assets. The database backup tool intentionally does
not package `.env`, Session files, logs, or downloads.

## Create an online database backup

From the repository root:

```powershell
docker compose run --rm backend python /app/scripts/sqlite_backup.py
```

The script uses SQLite's online backup API, not a raw file copy. It writes the
backup atomically, runs a full integrity check, sets restrictive permissions when
supported, and writes a SHA-256 manifest beside the backup.

Backups are written under ignored `backups/` by default. Encrypt and copy them to
a different device. A backup on the same NAS is not disaster recovery.

## Verify a backup

```powershell
docker compose run --rm backend python /app/scripts/sqlite_restore.py `
  /app/backups/app-TIMESTAMP.db --verify-only
```

Verification checks both the manifest checksum and SQLite integrity.

## Restore drill

Perform drills against a temporary target while services continue running:

```powershell
docker compose run --rm backend python /app/scripts/sqlite_restore.py `
  /app/backups/app-TIMESTAMP.db `
  --database /app/data/restore-drill.db `
  --confirm RESTORE_DATABASE
docker compose run --rm backend python /app/scripts/sqlite_health.py `
  --database /app/data/restore-drill.db --full
```

Delete the drill database only after recording the result.

## Production restore

1. Stop backend and worker. Keep the frontend stopped or in maintenance mode.
2. Verify the selected backup.
3. Preserve `.env`, Session, and downloads separately.
4. Run the restore command with exact `RESTORE_DATABASE` confirmation.
5. The tool creates a verified `app.db.pre-restore-*` snapshot first.
6. Remove stale `app.db-wal` and `app.db-shm` only while all writers are stopped.
7. Start backend first and confirm migrations and `/health`.
8. Start worker and verify Telegram authorization and record counts.

Never combine a restored main database with WAL/SHM files from a different point
in time. Never upload database, Session, or `.env` backups to GitHub.

## Recommended schedule

- Daily online database backup.
- Backup immediately before each application upgrade or migration.
- Keep multiple generations and at least one encrypted offline copy.
- Run a restore drill monthly and after changing backup tooling.

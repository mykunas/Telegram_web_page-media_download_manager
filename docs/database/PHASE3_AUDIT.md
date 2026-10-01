# Phase 3 Database Audit

Date: 2026-10-01

## Scope

The audit covered SQLAlchemy models, SQLite connection configuration, backend and
worker transaction boundaries, startup initialization, data relationships,
backup documentation, and the live NAS database using read-only checks.

## Baseline

- SQLite used WAL, a 10 second busy timeout, and foreign key enforcement.
- Startup used `Base.metadata.create_all()`. This creates missing tables but does
  not upgrade existing tables, indexes, constraints, or data.
- The worker used a commit/rollback context manager. Backend routes used explicit
  commits, while failed request dependencies did not explicitly roll back.
- Logical relationships such as play progress to download records and collection
  items to collections were integer columns without database foreign keys.
- Backup guidance existed, but there was no consistent SQLite online-backup,
  checksum, restore confirmation, or restore drill tooling.

## Live Database Findings

The pre-migration read-only baseline returned:

- `PRAGMA quick_check`: ok
- foreign key violations: 0
- duplicate `(chat_id, message_id)` download identities: 0
- orphan play progress: 0
- orphan collection items: 0
- orphan daily recommendations: 0

No application settings or secret values were read by the audit queries.

## Risks

### High

- `create_all()` alone cannot provide controlled schema evolution or detect
  migration drift.
- A copied `app.db` can be inconsistent when WAL writers are active.
- Restoring by overwriting the live database can lose the current state and mix
  an old database with current `-wal`/`-shm` files.

### Medium

- Missing relationship constraints allowed future orphan rows.
- Frequently used compound filters lacked matching indexes.
- Negative counters, file sizes, or playback positions were not rejected by
  SQLite itself.
- No repeatable disaster-recovery verification existed.

### Low

- Connection timeout and WAL checkpoint behavior were only partially explicit.
- Health responses did not expose the non-sensitive schema version.

## Phase 3 Decision

Use an in-process, append-only migration registry because the project is a small
single-database NAS application and introducing Alembic only for three initial
migrations would add deployment surface without improving current safety. Every
migration is checksummed, transactional, idempotent, and recorded in
`schema_migrations`. Moving to Alembic remains possible if the schema begins to
branch or requires complex table rebuilds.

Existing tables are not rebuilt in this phase. Relationship and numeric triggers
protect future writes while integrity checks continue to report any legacy rows.

# Transactions and Data Integrity

## Transaction boundaries

- Worker jobs use `db_session_scope()`: success commits; exceptions roll back.
- Configuration batches validate every item before a single commit.
- FastAPI database dependencies now explicitly roll back when a request raises.
- Each schema migration is independently transactional.
- Backup and restore publish files using atomic replacement.

Do not commit inside low-level helper functions unless the helper owns the entire
business operation. New multi-row operations should use one request/job-level
transaction so partial state cannot become visible.

## SQLite policy

Every SQLAlchemy connection enables:

- WAL journal mode
- foreign keys
- 30 second connection timeout
- 10 second SQLite busy timeout
- NORMAL synchronous mode
- 1000 page WAL auto-checkpoint

## Integrity layers

- Existing unique constraints protect settings, channel/message identity, and
  user-specific logical records.
- Migration triggers reject future orphan relationship writes.
- Delete triggers remove dependent playback, recommendation, and collection rows.
- Numeric triggers reject negative sizes, retries, positions, and durations.
- Startup checks detect corruption, duplicate download identities, foreign-key
  violations, and legacy orphan rows.

Integrity failures are fatal at startup. Operators should restore a verified
backup or repair a copy; they should not disable the check on the live database.

# Database Migrations

## Startup order

1. SQLAlchemy creates genuinely missing tables.
2. The migration runner creates `schema_migrations`.
3. Pending migrations run one version at a time in a transaction.
4. Previously applied migration checksums are verified.
5. Startup runs SQLite and logical integrity checks.

A checksum mismatch or failed integrity check stops backend startup rather than
allowing the application to run silently against an unknown schema.

## Current versions

- Version 1: operational compound indexes.
- Version 2: relationship guards and delete cascades for collections,
  recommendations, playback progress, actions, and download records.
- Version 3: non-negative guards for download and playback numeric values.

## Rules for new migrations

- Never edit an applied migration. Add the next integer version.
- Validate existing data before adding a new constraint.
- Keep migrations deterministic and safe to retry.
- Do not put secrets or deployment-specific paths in migration SQL.
- Test upgrade from a copy of the oldest supported database.
- Back up and verify the database before deploying schema changes.

## Rollback policy

The migration runner is forward-only. Database rollback means restoring a
verified pre-deployment backup with the matching application version. This is
safer for SQLite than attempting partial down migrations after application writes
have used a newer schema.

# Backup Security

## Sensitive backup contents

- `.env`: credentials and security policy.
- `data/app.db`: Telegram credentials, configuration, logs and media metadata.
- `session/`: active Telegram account credential.
- logs: may contain operational metadata even after sanitization.
- downloads: private media content.

Never upload these to GitHub, attach them to issues, or include them in a code
deployment archive. Encrypt backups at rest and restrict them to the deployment
account.

## What to back up

Stop the stack cleanly, then back up `.env`, `data/`, `session/`, downloads and
needed logs as separate sensitive data. Preserve file ownership/modes where the
backup system supports it.

## Restore order

1. Restore code/Compose from a trusted release.
2. Restore `.env` with restrictive permissions.
3. Restore `data/` and `session/`; on Linux/NAS use directory mode `700` and
   session file mode `600`.
4. Restore downloads to the configured bind mount.
5. Apply the Phase 1 UID/GID permission helper.
6. Run `docker compose config`, start backend, then frontend/worker.
7. Verify masked config status, existing database counts and session reuse.

Keep at least one known-good offline backup. A backup containing a leaked
session must not be used after that session has been revoked.

# Phase 2 Migration and Rollback

## Before upgrade

1. Follow `BACKUP_SECURITY.md` and stop containers before copying SQLite/session.
2. Do not delete or reinitialize `data/app.db` or `session/`.
3. Deploy backend and frontend together because Telegram API response schemas
   change from raw strings to masked metadata.

## Upgrade

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

Existing non-empty database values remain authoritative. No credential or
session migration is required. The first GET returns configured/masked state;
it never returns the original value.

Verify:

```bash
curl -fsS http://127.0.0.1:${FRONTEND_PORT:-3000}/healthz
curl -fsS http://127.0.0.1:${FRONTEND_PORT:-3000}/api/telegram-config
docker compose logs --tail 100 backend worker
```

Inspect the JSON only for `configured`/`masked`; it must not contain the known
API hash or full phone number.

## Enable optional admin write protection

1. Generate a long random token and its SHA-256 digest offline.
2. Put only the digest in `.env` as `ADMIN_API_TOKEN_HASH`.
3. Set `ADMIN_AUTH_ENABLED=true` and restart backend.
4. Enter the raw token in the Settings security panel after each page reload.

All `/api` POST/PUT/PATCH/DELETE requests will return 401 without the token.
GET media remains unchanged.

## Rollback

Stop the stack, restore the complete pre-Phase-2 code and matching frontend,
then restore the verified `.env`, database and session backup only if Phase 2
changed values you do not want. Phase 2 does not perform a schema migration, so
the existing SQLite file remains structurally compatible.

Do not use the old tracked `deploy_ai_tg.tar.gz`: audit found real `.env` and
session files inside it. Treat it as compromised sensitive backup material.

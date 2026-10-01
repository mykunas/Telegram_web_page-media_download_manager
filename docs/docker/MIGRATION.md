# Phase 1 Migration and Rollback

Phase 1 does not delete or rebuild the database, Telegram session, downloads,
or logs.

## Pre-migration backup

Stop containers cleanly before copying SQLite and Telegram session files:

```bash
docker compose down
mkdir -p backup-phase1
cp .env backup-phase1/.env
cp -a data backup-phase1/data
cp -a session backup-phase1/session
cp -a downloads backup-phase1/downloads
```

If `DOWNLOADS_VOLUME` points elsewhere, back up that exact directory instead of
`./downloads`.

Do not use `kill -9`; allow the worker grace period to finish or preserve its
`.part` file for retry.

## Linux/NAS volume ownership

Choose the deployment UID/GID in `.env`, then initialize only the known volume
directories:

```bash
sudo env PUID=1000 PGID=1000 sh ./scripts/init-volume-permissions.sh "$(pwd)"
```

Do not use recursive `chmod 777`.

## Deploy Phase 1

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

The backend no longer publishes port 8000 by default. Use the frontend `/api`
proxy, or add `docker-compose.api.yml` for loopback-only diagnostics.

## Compatibility behavior

- Existing `data/app.db` is mounted unchanged at `/app/data/app.db`.
- Existing Telegram session files remain under `/app/session`.
- Existing downloads use the same host directory.
- Old database paths beginning with `/downloads/` continue to work through the
  image compatibility symlink.
- If `app/hash_index.json` contains runtime state and `data/hash_index.json`
  does not exist, copy it before first Phase 1 startup:

  ```bash
  cp app/hash_index.json data/hash_index.json
  ```

## Smoke test

```bash
docker compose ps
curl -fsS http://127.0.0.1:${FRONTEND_PORT:-3000}/healthz
curl -fsS http://127.0.0.1:${FRONTEND_PORT:-3000}/api/dashboard/summary
docker compose logs --tail 100 worker
```

Verify in the UI that existing records and media remain readable and that the
worker logs show a successful Telegram client startup.

## Rollback

```bash
docker compose down
git restore docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf
cp backup-phase1/.env .env
test -f backup-phase1/data/app.db
rollback_stamp="$(date +%Y%m%d-%H%M%S)"
mv data "data.phase1-failed-$rollback_stamp"
mv session "session.phase1-failed-$rollback_stamp"
mv downloads "downloads.phase1-failed-$rollback_stamp"
cp -a backup-phase1/data data
cp -a backup-phase1/session session
cp -a backup-phase1/downloads downloads
docker compose up -d --build
```

Only run the replacement steps against the verified project directory and a
verified backup. On systems where downloads are external, restore the external
directory rather than `./downloads`. The `*.phase1-failed-*` directories retain
the failed state until rollback has been verified; remove them only after that.

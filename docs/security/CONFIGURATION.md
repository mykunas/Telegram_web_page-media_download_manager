# Configuration Model

## Classes

### Bootstrap configuration

Loaded from process environment and optional `.env`. Changes require container
restart. Examples: `DATABASE_URL`, `DEBUG`, `LOG_LEVEL`, `ALLOWED_HOSTS`,
`SESSION_DIR`, `DOWNLOAD_ROOT`, admin protection and Docker ports/resources.

### Runtime configuration

Download behavior such as `TARGET_CHATS`, `ALLOW_EXTS`, history, retry and file
size limits. Non-empty database values override environment fallback, which
overrides the registry default. Changes currently report
`worker_reload_required=true`; restart the worker to apply them reliably.

### Secrets

Telegram credentials use the same explicit priority as runtime-editable values:

1. existing non-empty SQLite value;
2. process environment / `.env` fallback;
3. registry default (normally empty).

This order preserves credentials previously saved through the UI. Secret
updates are accepted only by the dedicated Telegram API. Empty or omitted
fields keep the existing value.

## Registry

`backend/app/core/config_registry.py` is the canonical source for key, type,
classification, default, required/secret/editable flags, restart/reload effect,
description and validator. Backend APIs and the worker both import it.

Important normalization:

- chat targets: trim empty items and remove duplicates;
- extensions: lowercase, add the leading dot and remove duplicates;
- numeric settings: bounded ranges;
- phone: E.164-like international format;
- API hash: 32 hexadecimal characters;
- download/session paths: absolute, no `..`, and confined to mounted roots.

## Change effects

Responses include `restart_required` and `worker_reload_required`. Bootstrap
values are not editable through Settings APIs. Phase 2 does not introduce a
worker control plane, so a reported worker reload means:

```bash
docker compose restart worker
```

## Host and debug settings

`ALLOWED_HOSTS=*` preserves LAN/NAS access. For a known domain/IP list, use a
comma-separated value. `DEBUG=false` is the production default. Debug mode is
development-only and must not be exposed publicly.

## Optional write protection

Set `ADMIN_AUTH_ENABLED=true` and put only a SHA-256 hex digest in
`ADMIN_API_TOKEN_HASH`. Generate a digest outside the repository, for example:

```bash
printf %s 'choose-a-long-random-token' | sha256sum
```

The browser token input is memory-only. Page reload intentionally forgets it.

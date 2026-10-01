# Phase 2 Security Audit

Audit date: 2026-10-01

Scope: local working tree after Phase 1. The local tree is authoritative and
the Phase 1 non-root containers, health checks, volume boundaries, resource
limits and network isolation remain the baseline.

## Secret inventory and data flow

| Item | Sources | Storage | Consumers | Exposure before Phase 2 |
| --- | --- | --- | --- | --- |
| Telegram API ID | `.env`, `app_settings` | SQLite/plain environment | backend auth, worker | returned by both configuration APIs |
| Telegram API hash | `.env`, `app_settings` | SQLite/plain environment | backend auth, worker | returned verbatim by GET APIs and filled into the browser form |
| Phone number | `.env`, `app_settings` | SQLite/plain environment and auth runtime state | backend auth, worker | returned verbatim by config/status APIs and browser form |
| Verification code | request body | function argument | Pyrogram sign-in | not persisted, but raw exception text could disclose context |
| 2FA password | request body | function argument | Pyrogram password check | not persisted, but raw exception text could disclose context |
| Telegram session | bind-mounted files | `session/*.session*` | backend auth and worker | ignored by the current tree, but present in Git history; disconnect deleted it |
| Optional admin token | not implemented before Phase 2 | none | none | all management writes were unauthenticated |

## Findings

### Critical

1. `GET /api/telegram-config` returned the raw `API_HASH` and phone number.
2. `GET /api/settings` serialized every `AppSetting`, including secrets.
3. `PUT /api/settings` could create or overwrite arbitrary keys, including
   Telegram secrets, bypassing any dedicated secret policy.
4. `.env` and Telegram session files exist in historical public Git commits.
   Removing them from the current index does not revoke or erase those values.
5. Tracked `deploy_ai_tg.tar.gz` contained root and component `.env` files plus
   Telegram session files. Phase 2 removes generated archives from the index,
   but historical archive copies remain compromised.

### High

1. The frontend loaded the raw API hash and phone number into reactive form
   state and submitted them again on unrelated saves.
2. `disconnect` removed the session database and sidecar files by default,
   turning a normal disconnect action into destructive credential deletion.
3. Telegram authorization errors included raw exception messages in API
   responses. Worker logs and database error rows also stored raw exception
   messages and tracebacks.
4. No authentication protected settings, authorization, delete or other
   state-changing management APIs if the NAS port was exposed publicly.
5. `SESSION_NAME` and `DOWNLOAD_DIR` accepted arbitrary paths. Values such as
   `/`, `../../...`, or paths outside the mounted boundaries were possible.

### Medium

1. Defaults, supported keys and parsing logic were duplicated in
   `telegram_config_service.py` and `app/runtime_config.py`.
2. Configuration precedence was implicit: non-empty database values overrode
   environment values, while bootstrap settings were environment-only.
3. Integer ranges, phone format, API hash format, chat lists and extension
   lists lacked consistent validation and normalization.
4. Telegram batch updates committed values directly and could leave unclear
   behavior when validation failed midway.
5. Sensitive configuration and auth responses lacked `Cache-Control: no-store`.
6. Auth endpoints had no focused rate limiting.
7. Error-log APIs returned stored tracebacks and paths without a sanitization
   pass, including legacy rows.
8. No startup security/configuration check reported fatal, warning and info
   conditions.

### Low

1. Global CORS was not enabled, which is correct for the same-origin Nginx
   proxy. Host validation was absent.
2. Nginx already set basic clickjacking, MIME and referrer headers; a compatible
   CSP and explicit cache policy for sensitive API responses were still absent.
3. The repository had no security regression test suite or automated secret
   scan. Enabling a history-aware scanner before rotating historical secrets
   would immediately fail on known historical leaks.

## Existing protections retained

- Phase 1 excludes `.env`, session files, databases, logs, downloads, backups
  and runtime hash indexes from Docker build contexts.
- Current Git index no longer tracks `.env`, session files or runtime state.
- Frontend containers do not receive backend/Telegram environment variables.
- Backend and worker run as a non-root user with explicit mounts only.
- Unhandled backend exceptions already returned a generic 500 response, but
  business exceptions still needed sanitization and safe-message discipline.

## Configuration classification baseline

- **Bootstrap:** database URL, application/debug/host policy, storage roots,
  logging and container ports/resources. Environment/Docker only; restart is
  required.
- **Runtime:** download behavior and channel/extension lists. Database values
  override environment fallback and application defaults; worker reload or
  restart may be required.
- **Secrets:** API hash, phone number, Telegram auth transients, session files
  and optional admin credential. They require dedicated write-only handling.

## Compatibility constraints

- Existing non-empty database credentials must remain usable and be exposed
  only as configured/masked metadata.
- Existing `/app/session/telegram_user.session` must not be deleted or renamed.
- Existing `/downloads/...` database paths remain compatible through the Phase
  1 image symlink.
- No history rewrite, force push, credential rotation or session revocation is
  performed automatically.

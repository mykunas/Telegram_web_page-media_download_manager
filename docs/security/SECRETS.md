# Secret Policy

## Storage policy

| Secret | Storage | Returned by GET |
| --- | --- | --- |
| Telegram API hash | SQLite when saved in UI, otherwise environment | configured + masked metadata only |
| Telegram phone number | SQLite when saved in UI, otherwise environment | configured + masked metadata only |
| Telegram API ID | SQLite/environment | configured + masked metadata only |
| Verification code | request/function memory | never |
| 2FA password | request/function memory | never |
| Phone-code hash | short-lived backend auth state | never |
| Telegram session | host-mounted session database | existence boolean only |
| Admin token | operator/browser memory | never; only its SHA-256 digest is configured |

SQLite credentials are plaintext. This is deliberate and honest: there is no
independent key-management source in this NAS deployment. Encrypting with a key
stored beside the database would be obfuscation, not a meaningful boundary.
Protect `.env`, `data/app.db`, `session/` and their backups with host access
controls and encrypted backup storage.

## API rules

- GET never returns raw secrets.
- Empty/omitted secret update fields mean “keep existing”.
- Clearing a credential requires the dedicated DELETE endpoint and matching
  confirmation phrase.
- Credential and auth responses use `Cache-Control: no-store`.
- Generic Settings endpoints reject secret, bootstrap, unknown and duplicate
  keys.
- API errors are browser-safe; internal logs are sanitized before writing.

## Session rules

- Session directory should be mode `700`; files should be `600` on Linux/NAS.
- Docker UID/GID must match the host deployment account where bind mounts
  enforce ownership. Use the Phase 1 permission helper; never use `chmod 777`.
- Disconnect retains the session. Permanent deletion requires
  `DELETE /api/telegram-config/session` with `{"confirm":"DELETE_SESSION"}`.
- Stop the worker before permanent deletion to avoid an active session handle.

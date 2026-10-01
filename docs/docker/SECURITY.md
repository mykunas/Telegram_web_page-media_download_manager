# Docker Security

## Applied controls

- Non-root runtime users for Python and Nginx.
- `no-new-privileges:true` and all Linux capabilities dropped.
- No host Docker socket and no complete-project bind mount.
- Frontend does not receive Telegram secrets.
- Backend is not published by default; frontend is the single ingress.
- `.dockerignore` excludes Git metadata, secrets, sessions, databases, logs,
  downloads, archives, editor state, and build output.
- `.env.example` contains only empty/sample values.
- Docker stdout/stderr uses bounded `json-file` rotation.

These controls do not replace application authentication. Keep the frontend on
a trusted network or behind an authenticated TLS reverse proxy until login and
authorization are implemented.

## Public repository incident response

The repository previously tracked `.env` and Telegram session files. Adding
ignore rules does not remove them from Git history.

Required operator actions:

1. In Telegram, terminate leaked/old sessions and change the two-step password.
2. Rotate any exposed credentials where the provider supports rotation.
3. Keep a local backup of required runtime data.
4. Remove sensitive paths from tracking without deleting local files:

   ```bash
   git rm --cached .env
   git rm --cached -r session
   git rm --cached app/hash_index.json
   ```

5. Rewrite public Git history with `git filter-repo` or BFG in a separately
   reviewed maintenance operation, then force-push and notify all clone owners.

History rewriting is intentionally not automated by Phase 1.

## Secret handling

- Never commit `.env`, database files, session files, logs, or downloaded media.
- Restrict filesystem access to the deployment account and configured PUID/PGID.
- Do not paste API hashes, OTP codes, or two-step passwords into issue trackers.
- Backups containing session or database files must be encrypted and access
  controlled.

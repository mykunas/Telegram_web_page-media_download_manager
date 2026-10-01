# Phase 1 Docker Audit

## Scope

This audit covers Docker architecture, runtime boundaries, persistence, logging,
resource controls, secret handling, and deployment configuration. Business
logic, the recommendation system, UI behavior, and major database redesign are
out of scope.

## Baseline architecture

- `backend`: FastAPI/Uvicorn built from `backend/Dockerfile`.
- `worker`: built from the backend image but executed source from a host bind
  mount of the complete repository (`./:/workspace`).
- `frontend`: Vue build served by Nginx on container port 80.
- All services shared one bridge network.
- Backend and frontend published host ports.
- Backend used `/app/data`; worker used `/workspace/data` for the same SQLite
  file.
- Backend/worker shared the download and Telegram session bind mounts.
- No healthchecks, resource limits, PID limits, init process, log rotation, or
  explicit graceful-stop periods were configured.

## Runtime details before Phase 1

1. Backend command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
2. Worker command: `python app/downloader.py` with `/workspace` as working dir.
3. Frontend command: default Nginx entrypoint.
4. Volumes: database, session, downloads, and logs, plus the entire repository
   for the worker.
5. Network: one Docker bridge; backend and frontend ports were published.
6. Environment: all three services loaded the root `.env`, including frontend.
7. SQLite: backend and worker accessed the same host DB through different
   container paths; no explicit WAL or busy timeout.
8. Session: shared host `session/`, but concurrent auth/worker access could lock
   the Pyrogram SQLite session.
9. Downloads: shared host path mounted at `/downloads`.
10. Logging: application logs plus unbounded Docker `json-file` logs.
11. Resources: no memory, CPU, or PID controls.
12. Security: root containers, broad repository bind mount, secrets in frontend
    environment, backend exposed by default, and sensitive files tracked in Git.

## Findings

### Critical

- `.env` and Telegram `.session` files were tracked by Git in a public
  repository. `.gitignore` does not remove already committed secrets.
- Worker mounted the entire repository read/write, exposing `.git`, frontend,
  docs, source code, and local files to the runtime container.
- Backend configuration and Telegram authorization endpoints had no application
  authentication while the backend port was published by default.

### High

- Backend and worker ran as root.
- Mixed `/workspace/*`, `/app/*`, and `/downloads` paths complicated persistence
  and migration.
- Frontend received Telegram secrets through `env_file` without using them.
- No healthchecks, startup readiness dependency, resource limits, PID limits,
  Docker log rotation, or explicit stop grace periods.
- Telegram authorization and worker processes could contend for the same
  SQLite-backed session file.

### Medium

- SQLite did not explicitly use WAL, foreign keys, or a busy timeout.
- Docker build contexts could contain archives and runtime state.
- Backend was directly exposed even though Nginx already proxied `/api/`.
- Runtime hash state was kept in the source tree.

### Low

- Generated archives and obsolete deployment artifacts remain in repository
  history.
- Sync-control task functions are placeholders and do not control the worker.
  This is recorded for a later business/runtime-control phase.

## Phase 1 remediation

- Backend and worker now share one immutable Python image containing only the
  required backend and worker source.
- Runtime mounts are limited to data, session, downloads, and logs.
- Canonical container paths are `/app/data`, `/app/session`, `/app/downloads`,
  and `/app/logs`.
- `/downloads` remains a compatibility symlink for paths already stored in the
  existing database; it is not an additional mount.
- Frontend no longer receives `.env` or Telegram credentials.
- All images run non-root, drop Linux capabilities, and enable
  `no-new-privileges`.
- Healthchecks, startup dependencies, tmpfs, resource limits, PID limits,
  init, graceful-stop periods, and bounded Docker logs are configured.
- Backend is internal-only by default. An opt-in Compose override publishes it
  on loopback.
- SQLite receives WAL, busy timeout, and foreign-key pragmas per connection.

## Deferred issues

- Add application authentication/authorization before public exposure.
- Replace placeholder sync-control tasks with a real worker control plane.
- Add a worker heartbeat instead of process-only health.
- Separate Telegram authorization from the long-running worker session lifecycle.
- Introduce migrations and automated tests in a later phase.

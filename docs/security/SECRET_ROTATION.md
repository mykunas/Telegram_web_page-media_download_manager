# Secret Rotation and Git History

Deleting `.env`, session files or deployment archives from the latest commit is
not enough. Copies remain in Git history, forks, caches and clones.

## Immediate response for a public leak

1. In Telegram, terminate old active sessions and create a fresh session.
2. Change the Telegram two-step password if it was exposed.
3. Replace credentials that the provider allows to be replaced.
4. Remove leaked deployment archives from every release/download location.
5. Treat old `.env`, `data/app.db`, session files and backups as compromised.

Do rotation before history cleanup because cleanup does not revoke credentials.

## Optional history cleanup

Coordinate with every contributor, make a mirror backup, and install
`git-filter-repo`. Review the exact paths first. A possible cleanup is:

```bash
git filter-repo \
  --path .env \
  --path session \
  --path deploy_ai_tg.tar.gz \
  --path frontend-dist.tar \
  --path frontend/dist_upload.tar.gz \
  --path frontend/dist_upload.zip \
  --invert-paths
```

Then inspect all refs and coordinate the required force push. Every existing
clone must be replaced or carefully rebased. This project does **not** run these
commands automatically.

After cleanup, a history-aware secret scan such as gitleaks can be enabled.
Until known history is cleaned, such a CI job will correctly report historical
findings.

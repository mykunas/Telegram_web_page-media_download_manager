# Resource Limits

Defaults are conservative rather than minimal, so normal Pyrogram downloads and
FFmpeg probes do not fail under routine NAS workloads.

| Service | Memory | CPU | PIDs | tmpfs `/tmp` |
| --- | ---: | ---: | ---: | ---: |
| Frontend | 128 MiB | 0.5 | 128 | 32 MiB |
| Backend | 512 MiB | 1.0 | 256 | 128 MiB |
| Worker | 1 GiB | 2.0 | 512 | 512 MiB |

All values are adjustable through `.env`; see `.env.example`.

## Tuning guidance

- Increase `WORKER_MEMORY_LIMIT` and `WORKER_TMPFS_SIZE` for large videos or
  memory-intensive FFmpeg operations.
- Raise CPU limits if thumbnail/preview generation competes with downloads.
- Do not reduce backend below 256 MiB or worker below 512 MiB without load tests.
- A container killed with exit code 137 usually needs more memory.
- Keep host disk space monitoring separate from container memory limits because
  downloaded media and SQLite live on bind mounts.

Inspect live usage with:

```bash
docker stats --no-stream
docker compose ps
docker compose logs --tail 200
```

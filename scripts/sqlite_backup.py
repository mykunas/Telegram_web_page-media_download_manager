from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.sqlite_backup import create_backup  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a verified online SQLite backup")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "app.db")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (
        ROOT / "backups" / f"app-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
    )
    manifest = create_backup(args.database, output)
    print(json.dumps({"backup": str(output.resolve()), **manifest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

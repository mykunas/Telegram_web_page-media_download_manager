from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.sqlite_backup import restore_backup, verify_backup  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or restore a SQLite backup")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "app.db")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    manifest = verify_backup(args.backup)
    if args.verify_only:
        print(json.dumps({"verified": True, **manifest}, ensure_ascii=False))
        return 0
    previous = restore_backup(args.backup, args.database, confirmation=args.confirm)
    print(json.dumps({"restored": True, "pre_restore_backup": str(previous) if previous else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

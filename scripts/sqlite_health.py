from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine  # noqa: E402

from app.core.database_health import inspect_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect SQLite integrity and logical relationships")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "app.db")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    result = inspect_database(engine, full=args.full)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

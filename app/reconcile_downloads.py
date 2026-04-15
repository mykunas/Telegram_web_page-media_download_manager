import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from runtime_config import load_runtime_config


FILE_NAME_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(?P<chat_id>-?\d+)_(?P<message_id>\d+)_(?P<orig>.+)$"
)


def parse_database_path() -> str:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError(f"DATABASE_URL is not sqlite: {database_url}")
    db_path = database_url.replace("sqlite:///", "", 1)
    if not db_path:
        raise RuntimeError("DATABASE_URL sqlite path is empty")
    return db_path


def detect_media_type(file_path: Path) -> str:
    parts = {part.lower() for part in file_path.parts}
    if "videos" in parts:
        return "video"
    if "photos" in parts:
        return "photo"
    if "files" in parts:
        return "document"

    ext = file_path.suffix.lower()
    if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
        return "video"
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "photo"
    return "document"


def calc_file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def upsert_record(conn: sqlite3.Connection, payload: dict, update_existing: bool) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status, saved_path
        FROM download_records
        WHERE chat_id = ? AND message_id = ?
        """,
        (payload["chat_id"], payload["message_id"]),
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO download_records (
              chat_id, chat_name, message_id, message_date, media_type,
              original_file_name, saved_file_name, saved_path, file_size, sha256,
              status, source_type, retry_count, error_message,
              created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["chat_id"],
                payload["chat_name"],
                payload["message_id"],
                payload["message_date"],
                payload["media_type"],
                payload["original_file_name"],
                payload["saved_file_name"],
                payload["saved_path"],
                payload["file_size"],
                payload["sha256"],
                "SUCCESS",
                "legacy_import",
                0,
                None,
                payload["timestamp"],
                payload["timestamp"],
                payload["timestamp"],
            ),
        )
        return "inserted"

    if not update_existing:
        return "skipped_existing"

    cur.execute(
        """
        UPDATE download_records
        SET chat_name = ?,
            message_date = COALESCE(message_date, ?),
            media_type = COALESCE(media_type, ?),
            original_file_name = COALESCE(original_file_name, ?),
            saved_file_name = ?,
            saved_path = ?,
            file_size = ?,
            sha256 = COALESCE(sha256, ?),
            status = CASE WHEN status IN ('SUCCESS', 'DUPLICATE') THEN status ELSE 'SUCCESS' END,
            source_type = COALESCE(source_type, 'legacy_import'),
            error_message = CASE WHEN status IN ('SUCCESS', 'DUPLICATE') THEN error_message ELSE NULL END,
            updated_at = ?,
            completed_at = CASE WHEN status IN ('SUCCESS', 'DUPLICATE') THEN completed_at ELSE ? END
        WHERE id = ?
        """,
        (
            payload["chat_name"],
            payload["message_date"],
            payload["media_type"],
            payload["original_file_name"],
            payload["saved_file_name"],
            payload["saved_path"],
            payload["file_size"],
            payload["sha256"],
            payload["timestamp"],
            payload["timestamp"],
            row[0],
        ),
    )
    return "updated"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile existing downloaded files into download_records.")
    parser.add_argument("--with-hash", action="store_true", help="Calculate sha256 and update hash_index.json")
    parser.add_argument("--update-existing", action="store_true", help="Update existing records metadata")
    parser.add_argument("--dry-run", action="store_true", help="Only scan and print stats, do not write DB")
    parser.add_argument("--root", default="", help="Custom scan root directory. Default uses DOWNLOAD_DIR")
    args = parser.parse_args()

    cfg = load_runtime_config()
    download_root = Path(args.root.strip() or cfg.download_dir)
    if not download_root.exists():
        raise RuntimeError(f"download directory not found: {download_root}")

    db_path = parse_database_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")

    hash_index_path = Path(cfg.hash_index_file)
    hash_index: dict[str, str] = {}
    if args.with_hash and hash_index_path.exists():
        try:
            loaded = json.loads(hash_index_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                hash_index = {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            hash_index = {}

    stats = {
        "scanned_files": 0,
        "matched_files": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_existing": 0,
        "skipped_name_unmatched": 0,
        "errors": 0,
        "hash_written": 0,
    }
    sample_errors: list[str] = []

    for file_path in download_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.endswith(".part"):
            continue

        stats["scanned_files"] += 1
        match = FILE_NAME_PATTERN.match(file_path.name)
        if not match:
            stats["skipped_name_unmatched"] += 1
            continue

        stats["matched_files"] += 1
        rel = file_path.relative_to(download_root)
        chat_name = rel.parts[0] if rel.parts else ""

        try:
            ts = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
            parsed_ts = datetime.strptime(match.group("ts"), "%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc).isoformat()
            sha256 = calc_file_sha256(file_path) if args.with_hash else None
            payload = {
                "chat_id": int(match.group("chat_id")),
                "message_id": int(match.group("message_id")),
                "chat_name": chat_name,
                "message_date": parsed_ts,
                "media_type": detect_media_type(file_path),
                "original_file_name": match.group("orig"),
                "saved_file_name": file_path.name,
                "saved_path": str(file_path.resolve()),
                "file_size": int(file_path.stat().st_size),
                "sha256": sha256,
                "timestamp": ts,
            }

            if not args.dry_run:
                result = upsert_record(conn, payload, update_existing=args.update_existing)
                stats[result] += 1
                if args.with_hash and sha256:
                    hash_index[sha256] = str(file_path.resolve())
                    stats["hash_written"] += 1
            else:
                stats["skipped_existing"] += 1
        except Exception:
            stats["errors"] += 1
            if len(sample_errors) < 5:
                sample_errors.append(str(file_path))

    if not args.dry_run:
        conn.commit()
        if args.with_hash:
            hash_index_path.parent.mkdir(parents=True, exist_ok=True)
            hash_index_path.write_text(json.dumps(hash_index, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if sample_errors:
        print(json.dumps({"error_samples": sample_errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

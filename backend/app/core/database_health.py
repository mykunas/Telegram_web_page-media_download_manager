from __future__ import annotations

from typing import Any

from sqlalchemy import Engine

from app.core.migrations import current_schema_version


ORPHAN_QUERIES: dict[str, str] = {
    "play_progress": (
        "SELECT COUNT(1) FROM play_progress p "
        "LEFT JOIN download_records d ON d.id=p.record_id WHERE d.id IS NULL"
    ),
    "daily_recommendations": (
        "SELECT COUNT(1) FROM daily_recommendations r "
        "LEFT JOIN download_records d ON d.id=r.record_id WHERE d.id IS NULL"
    ),
    "collection_items": (
        "SELECT COUNT(1) FROM user_collection_items i "
        "LEFT JOIN user_collections c ON c.id=i.collection_id "
        "LEFT JOIN download_records d ON d.id=i.record_id "
        "WHERE c.id IS NULL OR d.id IS NULL"
    ),
}


def inspect_database(engine: Engine, *, full: bool = False) -> dict[str, Any]:
    if engine.dialect.name != "sqlite":
        return {"engine": engine.dialect.name, "status": "unsupported", "valid": True}

    check_pragma = "PRAGMA integrity_check" if full else "PRAGMA quick_check"
    with engine.connect() as connection:
        check_rows = [str(row[0]) for row in connection.exec_driver_sql(check_pragma)]
        foreign_key_violations = len(connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall())
        orphan_counts = {
            name: int(connection.exec_driver_sql(query).scalar_one())
            for name, query in ORPHAN_QUERIES.items()
        }
        duplicate_download_keys = int(
            connection.exec_driver_sql(
                "SELECT COUNT(1) FROM ("
                "SELECT chat_id, message_id FROM download_records "
                "GROUP BY chat_id, message_id HAVING COUNT(1) > 1)"
            ).scalar_one()
        )

    check_ok = check_rows == ["ok"]
    valid = (
        check_ok
        and foreign_key_violations == 0
        and duplicate_download_keys == 0
        and not any(orphan_counts.values())
    )
    return {
        "engine": "sqlite",
        "status": "ok" if valid else "error",
        "valid": valid,
        "check": "ok" if check_ok else "failed",
        "foreign_key_violations": foreign_key_violations,
        "duplicate_download_keys": duplicate_download_keys,
        "orphan_counts": orphan_counts,
        "schema_version": current_schema_version(engine),
    }

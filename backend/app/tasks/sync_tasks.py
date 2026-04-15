from __future__ import annotations


def start_sync_worker() -> dict:
    """Task entrypoint placeholder for starting the sync worker."""

    return {"accepted": True, "detail": "sync worker start task submitted"}


def stop_sync_worker() -> dict:
    """Task entrypoint placeholder for stopping the sync worker."""

    return {"accepted": True, "detail": "sync worker stop task submitted"}


def enqueue_history_backfill() -> dict:
    """Task entrypoint placeholder for triggering history backfill."""

    return {"accepted": True, "detail": "history backfill task submitted"}


def enqueue_consistency_recheck() -> dict:
    """Task entrypoint placeholder for triggering consistency recheck."""

    return {"accepted": True, "detail": "consistency recheck task submitted"}

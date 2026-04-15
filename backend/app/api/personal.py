from __future__ import annotations

import json
import os
import random
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import success_response
from app.models import (
    AppSetting,
    DailyRecommendation,
    DownloadRecord,
    DownloadStatus,
    PlayProgress,
    UserAction,
    UserCollection,
    UserCollectionItem,
    UserPreferenceProfile,
)
from app.schemas.personal import (
    CollectionAddItemRequest,
    CollectionCreateRequest,
    CollectionUpdateRequest,
    PlaybackInitRequest,
    PlaybackStateUpdateRequest,
    PreferenceManualUpdateRequest,
    PlayProgressUpdateRequest,
    RandomPickRequest,
)

router = APIRouter(prefix="/personal", tags=["Personal"])

RECOMMEND_LIMIT = 20
RECENT_ACTION_TYPES = {"preview_open", "play_start", "play_pause", "play_seek", "play_complete", "recommend_click"}
ACTION_WEIGHT = {
    "recommend_click": 4.0,
    "play_complete": 5.0,
    "play_start": 3.0,
    "preview_open": 2.0,
    "random_pick": 1.0,
    "favorite_add": 5.0,
}
PREFERENCE_REFRESH_INTERVAL_SECONDS = 3600


def _normalize_media_type(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"video", "photo", "document"}:
        return v
    return None


def _build_record_payload(row: DownloadRecord, *, reason: str | None = None, score: float | None = None) -> dict:
    file_name = row.saved_file_name or row.original_file_name or f"record_{row.id}"
    payload = {
        "id": int(row.id),
        "chat_id": int(row.chat_id or 0),
        "chat_name": row.chat_name,
        "media_type": row.media_type,
        "file_name": file_name,
        "file_size": int(row.file_size or 0),
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "message_date": row.message_date.isoformat() if row.message_date else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "preview_url": f"/api/downloads/{row.id}/file?mode=inline",
        "download_url": f"/api/downloads/{row.id}/file?mode=download",
        "thumbnail_url": f"/api/downloads/{row.id}/thumbnail",
    }
    if reason is not None:
        payload["reason"] = reason
    if score is not None:
        payload["score"] = round(float(score), 4)
    return payload


def _build_collection_item_payload(item: UserCollectionItem, record_map: dict[int, DownloadRecord]) -> dict:
    row = record_map.get(int(item.record_id))
    payload = {
        "record_id": int(item.record_id),
        "sort_order": int(item.sort_order or 0),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "record": None,
    }
    if row is not None:
        payload["record"] = _build_record_payload(row)
    return payload


def _load_user_collections(db: Session, *, user_id: int) -> list[dict]:
    collections = (
        db.query(UserCollection)
        .filter(UserCollection.user_id == user_id)
        .order_by(UserCollection.sort_order.asc(), UserCollection.id.asc())
        .all()
    )
    if not collections:
        return []

    collection_ids = [int(row.id) for row in collections]
    items = (
        db.query(UserCollectionItem)
        .filter(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.collection_id.in_(collection_ids),
        )
        .order_by(
            UserCollectionItem.collection_id.asc(),
            UserCollectionItem.sort_order.asc(),
            UserCollectionItem.id.asc(),
        )
        .all()
    )
    record_ids = sorted({int(item.record_id) for item in items})
    record_rows = db.query(DownloadRecord).filter(DownloadRecord.id.in_(record_ids)).all() if record_ids else []
    record_map = {int(row.id): row for row in record_rows}

    items_map: dict[int, list[dict]] = {}
    for item in items:
        cid = int(item.collection_id)
        items_map.setdefault(cid, []).append(_build_collection_item_payload(item, record_map))

    payload_list: list[dict] = []
    for collection in collections:
        cid = int(collection.id)
        payload_list.append(
            {
                "id": cid,
                "name": collection.name,
                "description": collection.description,
                "sort_order": int(collection.sort_order or 0),
                "created_at": collection.created_at.isoformat() if collection.created_at else None,
                "updated_at": collection.updated_at.isoformat() if collection.updated_at else None,
                "item_count": len(items_map.get(cid, [])),
                "items": items_map.get(cid, []),
            }
        )
    return payload_list


def _record_user_action(
    db: Session,
    *,
    user_id: int,
    action_type: str,
    record_id: int | None = None,
    action_value: dict | None = None,
) -> None:
    db.add(
        UserAction(
            user_id=user_id,
            record_id=record_id,
            action_type=action_type,
            action_value=json.dumps(action_value or {}, ensure_ascii=False),
        )
    )


def _extract_tags(file_name: str | None) -> list[str]:
    text = (file_name or "").lower()
    if not text:
        return []
    text = re.sub(r"\.[a-z0-9]{1,6}$", "", text)
    candidates = re.findall(r"[a-z0-9]{2,20}|[\u4e00-\u9fff]{2,8}", text)
    stop_words = {
        "mp4",
        "mkv",
        "mov",
        "avi",
        "jpg",
        "jpeg",
        "png",
        "webp",
        "part",
        "temp",
    }
    tags: list[str] = []
    for token in candidates:
        token = token.strip().lower()
        if not token or token in stop_words:
            continue
        if token not in tags:
            tags.append(token)
        if len(tags) >= 6:
            break
    return tags


def _safe_load_action_value(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _upsert_preference_row(
    db: Session,
    *,
    user_id: int,
    channel: str | None = None,
    media_type: str | None = None,
    tag: str | None = None,
    weight: float,
    source: str,
) -> None:
    row = (
        db.query(UserPreferenceProfile)
        .filter(
            UserPreferenceProfile.user_id == user_id,
            UserPreferenceProfile.channel == channel,
            UserPreferenceProfile.media_type == media_type,
            UserPreferenceProfile.tag == tag,
        )
        .first()
    )
    now = datetime.now(UTC)
    if row is None:
        row = UserPreferenceProfile(
            user_id=user_id,
            channel=channel,
            media_type=media_type,
            tag=tag,
            weight=weight,
            source=source,
            updated_at=now,
        )
        db.add(row)
        return
    row.weight = weight
    row.source = source
    row.updated_at = now


def _compute_user_preference_profile(db: Session, *, user_id: int) -> dict:
    since = datetime.now(UTC) - timedelta(days=30)

    record_rows = (
        db.query(DownloadRecord.id, DownloadRecord.chat_name, DownloadRecord.media_type, DownloadRecord.saved_file_name)
        .all()
    )
    record_map = {
        int(row.id): {
            "chat_name": (row.chat_name or "").strip(),
            "media_type": (row.media_type or "").strip().lower(),
            "tags": _extract_tags(row.saved_file_name),
        }
        for row in record_rows
    }

    channel_score: dict[str, float] = {}
    media_score: dict[str, float] = {}
    tag_score: dict[str, float] = {}

    progress_rows = (
        db.query(PlayProgress.record_id, PlayProgress.last_position_sec, PlayProgress.duration_sec, PlayProgress.is_completed)
        .filter(PlayProgress.user_id == user_id)
        .all()
    )
    for row in progress_rows:
        rid = int(row.record_id or 0)
        if rid <= 0 or rid not in record_map:
            continue
        duration = max(float(row.duration_sec or 0.0), 1.0)
        ratio = min(1.0, max(0.0, float(row.last_position_sec or 0.0) / duration))
        signal = ratio * 1.2 + (0.8 if row.is_completed else 0.0)
        info = record_map[rid]
        ch = info["chat_name"]
        mt = info["media_type"]
        if ch:
            channel_score[ch] = channel_score.get(ch, 0.0) + signal
        if mt:
            media_score[mt] = media_score.get(mt, 0.0) + signal
        for tag in info["tags"]:
            tag_score[tag] = tag_score.get(tag, 0.0) + signal * 0.5

    favorite_rows = (
        db.query(UserCollectionItem.record_id)
        .filter(UserCollectionItem.user_id == user_id)
        .all()
    )
    for row in favorite_rows:
        rid = int(row.record_id or 0)
        if rid <= 0 or rid not in record_map:
            continue
        info = record_map[rid]
        ch = info["chat_name"]
        mt = info["media_type"]
        if ch:
            channel_score[ch] = channel_score.get(ch, 0.0) + 3.0
        if mt:
            media_score[mt] = media_score.get(mt, 0.0) + 2.2
        for tag in info["tags"]:
            tag_score[tag] = tag_score.get(tag, 0.0) + 1.4

    action_rows = (
        db.query(UserAction.record_id, UserAction.action_type, UserAction.action_value)
        .filter(UserAction.user_id == user_id, UserAction.created_at >= since)
        .all()
    )
    for row in action_rows:
        rid = int(row.record_id or 0)
        if rid <= 0 or rid not in record_map:
            continue
        info = record_map[rid]
        ch = info["chat_name"]
        mt = info["media_type"]
        tags = info["tags"]
        action_type = str(row.action_type or "")
        if action_type in {"play_complete", "favorite_add"}:
            bonus = 1.0 if action_type == "play_complete" else 1.4
            if ch:
                channel_score[ch] = channel_score.get(ch, 0.0) + bonus
            if mt:
                media_score[mt] = media_score.get(mt, 0.0) + bonus * 0.9
            for tag in tags:
                tag_score[tag] = tag_score.get(tag, 0.0) + bonus * 0.6
            continue

        if action_type == "play_seek":
            payload = _safe_load_action_value(row.action_value)
            pos = float(payload.get("position_sec", 0.0) or 0.0)
            duration = float(payload.get("duration_sec", 0.0) or 0.0)
            if duration >= 120 and pos <= min(30.0, duration * 0.08):
                if ch:
                    channel_score[ch] = channel_score.get(ch, 0.0) - 1.2
                if mt:
                    media_score[mt] = media_score.get(mt, 0.0) - 1.0
                for tag in tags:
                    tag_score[tag] = tag_score.get(tag, 0.0) - 0.6

    def normalize(score_map: dict[str, float], *, scale: float) -> dict[str, float]:
        if not score_map:
            return {}
        values = list(score_map.values())
        max_abs = max(max(values), abs(min(values)), 1.0)
        out: dict[str, float] = {}
        for k, v in score_map.items():
            w = max(-5.0, min(5.0, v / max_abs * scale))
            out[k] = round(float(w), 4)
        return out

    channel_w = normalize(channel_score, scale=4.0)
    media_w = normalize(media_score, scale=3.5)
    tag_w = normalize(tag_score, scale=2.8)

    manual_rows = (
        db.query(UserPreferenceProfile)
        .filter(UserPreferenceProfile.user_id == user_id, UserPreferenceProfile.source == "manual")
        .all()
    )
    for row in manual_rows:
        if row.channel:
            channel_w[row.channel] = round(float(channel_w.get(row.channel, 0.0) + float(row.weight or 0.0)), 4)
        elif row.media_type:
            media_w[row.media_type] = round(float(media_w.get(row.media_type, 0.0) + float(row.weight or 0.0)), 4)
        elif row.tag:
            tag_w[row.tag] = round(float(tag_w.get(row.tag, 0.0) + float(row.weight or 0.0)), 4)

    db.query(UserPreferenceProfile).filter(
        UserPreferenceProfile.user_id == user_id,
        func.coalesce(UserPreferenceProfile.source, "auto") != "manual",
    ).delete()
    for key, weight in channel_w.items():
        _upsert_preference_row(db, user_id=user_id, channel=key, weight=weight, source="auto")
    for key, weight in media_w.items():
        _upsert_preference_row(db, user_id=user_id, media_type=key, weight=weight, source="auto")
    # keep top tags only to control table size
    for key, weight in sorted(tag_w.items(), key=lambda x: abs(float(x[1])), reverse=True)[:120]:
        _upsert_preference_row(db, user_id=user_id, tag=key, weight=weight, source="auto")
    db.commit()

    return {
        "channel": channel_w,
        "media_type": media_w,
        "tag": tag_w,
        "updated_at": datetime.now(UTC),
    }


def _load_preference_maps(db: Session, *, user_id: int) -> dict:
    rows = db.query(UserPreferenceProfile).filter(UserPreferenceProfile.user_id == user_id).all()
    channel_map: dict[str, float] = {}
    media_map: dict[str, float] = {}
    tag_map: dict[str, float] = {}
    updated_at = None
    for row in rows:
        if row.channel:
            key = str(row.channel)
            channel_map[key] = channel_map.get(key, 0.0) + float(row.weight or 0.0)
        elif row.media_type:
            key = str(row.media_type)
            media_map[key] = media_map.get(key, 0.0) + float(row.weight or 0.0)
        elif row.tag:
            key = str(row.tag)
            tag_map[key] = tag_map.get(key, 0.0) + float(row.weight or 0.0)
        if row.updated_at and (updated_at is None or row.updated_at > updated_at):
            updated_at = row.updated_at
    return {
        "channel": channel_map,
        "media_type": media_map,
        "tag": tag_map,
        "updated_at": updated_at,
    }


def _ensure_preference_profile(db: Session, *, user_id: int, force: bool = False) -> dict:
    pref = _load_preference_maps(db, user_id=user_id)
    updated_at = pref.get("updated_at")
    stale = True
    if updated_at is not None:
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        stale = (datetime.now(UTC) - updated_at).total_seconds() >= PREFERENCE_REFRESH_INTERVAL_SECONDS
    if force or stale or (not pref["channel"] and not pref["media_type"] and not pref["tag"]):
        return _compute_user_preference_profile(db, user_id=user_id)
    return pref


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _today_viewed_record_ids(db: Session, *, user_id: int) -> set[int]:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    rows = (
        db.query(UserAction.record_id)
        .filter(
            UserAction.user_id == user_id,
            UserAction.record_id.isnot(None),
            UserAction.created_at >= start,
            UserAction.action_type.in_(RECENT_ACTION_TYPES),
        )
        .all()
    )
    return {int(item[0]) for item in rows if item[0] is not None}


def _build_recommendation_candidates(
    db: Session,
    *,
    user_id: int,
    exclude_ids: set[int],
    pref: dict | None = None,
) -> list[tuple[DownloadRecord, float, str]]:
    since = datetime.now(UTC) - timedelta(days=7)
    action_rows = (
        db.query(UserAction.record_id, UserAction.action_type)
        .filter(
            UserAction.user_id == user_id,
            UserAction.record_id.isnot(None),
            UserAction.created_at >= since,
        )
        .all()
    )
    record_score: dict[int, float] = {}
    for record_id, action_type in action_rows:
        rid = int(record_id or 0)
        if rid <= 0:
            continue
        record_score[rid] = record_score.get(rid, 0.0) + ACTION_WEIGHT.get(str(action_type), 1.0)

    track_ids = list(record_score.keys())
    tracked_rows = (
        db.query(DownloadRecord.id, DownloadRecord.chat_id).filter(DownloadRecord.id.in_(track_ids)).all()
        if track_ids
        else []
    )
    channel_score: dict[int, float] = {}
    for row in tracked_rows:
        rid = int(row.id)
        chat_id = int(row.chat_id or 0)
        channel_score[chat_id] = channel_score.get(chat_id, 0.0) + record_score.get(rid, 0.0)

    candidates = (
        db.query(DownloadRecord)
        .filter(
            DownloadRecord.status.in_([DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE]),
            DownloadRecord.saved_path.isnot(None),
        )
        .order_by(DownloadRecord.id.desc())
        .limit(2000)
        .all()
    )

    result: list[tuple[DownloadRecord, float, str]] = []
    pref = pref or {}
    pref_channel = pref.get("channel", {}) if isinstance(pref, dict) else {}
    pref_media = pref.get("media_type", {}) if isinstance(pref, dict) else {}
    pref_tag = pref.get("tag", {}) if isinstance(pref, dict) else {}
    for row in candidates:
        row_id = int(row.id)
        if row_id in exclude_ids:
            continue

        path = (row.saved_path or "").strip()
        if not path or not os.path.isfile(path):
            continue

        ch_score = channel_score.get(int(row.chat_id or 0), 0.0)
        r_score = record_score.get(row_id, 0.0)
        size_bonus = min(1.5, float(row.file_size or 0) / (1024 * 1024 * 1024))
        media_bonus = 1.2 if (row.media_type or "") == "video" else 0.4
        ch_pref = float(pref_channel.get(str(row.chat_name or ""), 0.0))
        media_pref = float(pref_media.get(str(row.media_type or ""), 0.0))
        tags = _extract_tags(row.saved_file_name or row.original_file_name or "")
        tag_pref = sum(float(pref_tag.get(tag, 0.0)) for tag in tags[:4])
        total = 1.0 + ch_score * 0.3 + r_score * 0.6 + size_bonus + media_bonus
        total += ch_pref * 0.8 + media_pref * 0.65 + tag_pref * 0.2

        if r_score >= 4.0:
            reason = "你最近看过相似内容"
        elif ch_pref >= 1.2:
            reason = "匹配你的频道偏好"
        elif media_pref >= 1.0:
            reason = "匹配你的媒体类型偏好"
        elif ch_score >= 6.0:
            reason = "你最近常看该频道"
        elif (row.media_type or "") == "video":
            reason = "优先推荐视频内容"
        else:
            reason = "根据最近行为推荐"

        result.append((row, total, reason))

    result.sort(key=lambda x: (x[1], int(x[0].id)), reverse=True)
    return result


def _refresh_today_recommendations(
    db: Session,
    *,
    user_id: int,
    rec_date: date,
) -> list[DailyRecommendation]:
    exclude_ids = _today_viewed_record_ids(db, user_id=user_id)
    pref = _ensure_preference_profile(db, user_id=user_id)
    ranked = _build_recommendation_candidates(db, user_id=user_id, exclude_ids=exclude_ids, pref=pref)
    picked = ranked[:RECOMMEND_LIMIT]

    db.query(DailyRecommendation).filter(
        DailyRecommendation.user_id == user_id,
        DailyRecommendation.rec_date == rec_date,
    ).delete()

    for row, score, reason in picked:
        db.add(
            DailyRecommendation(
                rec_date=rec_date,
                user_id=user_id,
                record_id=int(row.id),
                score=float(score),
                reason=reason,
            )
        )
    db.commit()

    return (
        db.query(DailyRecommendation)
        .filter(DailyRecommendation.user_id == user_id, DailyRecommendation.rec_date == rec_date)
        .order_by(DailyRecommendation.score.desc(), DailyRecommendation.id.desc())
        .all()
    )


def _load_today_recommendations(db: Session, *, user_id: int, rec_date: date) -> list[DailyRecommendation]:
    rows = (
        db.query(DailyRecommendation)
        .filter(DailyRecommendation.user_id == user_id, DailyRecommendation.rec_date == rec_date)
        .order_by(DailyRecommendation.score.desc(), DailyRecommendation.id.desc())
        .all()
    )
    if not rows:
        rows = _refresh_today_recommendations(db, user_id=user_id, rec_date=rec_date)
    return rows


@router.post("/random/pick")
def personal_random_pick(
    payload: RandomPickRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    pref = _ensure_preference_profile(db, user_id=user_id)
    media_type = _normalize_media_type(payload.media_type)
    recent_minutes = int(payload.exclude_recent_minutes or 0)

    query = db.query(DownloadRecord).filter(
        DownloadRecord.status.in_([DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE]),
        DownloadRecord.saved_path.isnot(None),
    )

    if media_type:
        query = query.filter(DownloadRecord.media_type == media_type)
    if payload.min_size is not None and payload.min_size > 0:
        query = query.filter(DownloadRecord.file_size.isnot(None), DownloadRecord.file_size >= int(payload.min_size))
    if payload.max_size is not None and payload.max_size > 0:
        query = query.filter(DownloadRecord.file_size.isnot(None), DownloadRecord.file_size <= int(payload.max_size))

    rows = query.order_by(DownloadRecord.id.desc()).limit(1200).all()
    if not rows:
        return success_response(data=None, message="当前筛选条件下没有可随机内容")

    excluded_ids: set[int] = set()
    if recent_minutes > 0:
        since = datetime.now(UTC) - timedelta(minutes=recent_minutes)
        recent_rows = (
            db.query(UserAction.record_id)
            .filter(
                UserAction.user_id == user_id,
                UserAction.action_type == "random_pick",
                UserAction.record_id.isnot(None),
                UserAction.created_at >= since,
            )
            .all()
        )
        excluded_ids = {int(item[0]) for item in recent_rows if item[0] is not None}

    candidates = []
    for row in rows:
        if int(row.id) in excluded_ids:
            continue
        path = (row.saved_path or "").strip()
        if not path or not os.path.isfile(path):
            continue
        candidates.append(row)

    if not candidates:
        return success_response(data=None, message="没有可用候选，请缩短排除时间或放宽筛选条件")

    pref_channel = pref.get("channel", {}) if isinstance(pref, dict) else {}
    pref_media = pref.get("media_type", {}) if isinstance(pref, dict) else {}
    pref_tag = pref.get("tag", {}) if isinstance(pref, dict) else {}
    weighted: list[float] = []
    for row in candidates:
        ch_pref = float(pref_channel.get(str(row.chat_name or ""), 0.0))
        media_pref = float(pref_media.get(str(row.media_type or ""), 0.0))
        tags = _extract_tags(row.saved_file_name or row.original_file_name or "")
        tag_pref = sum(float(pref_tag.get(tag, 0.0)) for tag in tags[:4])
        weight = max(0.1, 1.0 + ch_pref * 0.7 + media_pref * 0.8 + tag_pref * 0.2)
        weighted.append(weight)
    picked = random.choices(candidates, weights=weighted, k=1)[0]
    _record_user_action(
        db,
        user_id=user_id,
        record_id=int(picked.id),
        action_type="random_pick",
        action_value={
            "source": "random_pick_api",
            "filters": {
                "media_type": media_type,
                "min_size": payload.min_size,
                "max_size": payload.max_size,
                "duration_range": payload.duration_range,
            },
            "exclude_recent_minutes": recent_minutes,
            "candidate_count": len(candidates),
        },
    )
    db.commit()

    return success_response(data={"record": _build_record_payload(picked)})


@router.get("/recommendations/today")
def personal_today_recommendations(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    rec_date = datetime.now(UTC).date()

    rows = _load_today_recommendations(db, user_id=user_id, rec_date=rec_date)
    viewed_today = _today_viewed_record_ids(db, user_id=user_id)
    keep_rows = [row for row in rows if int(row.record_id) not in viewed_today]

    if len(keep_rows) < min(8, RECOMMEND_LIMIT):
        rows = _refresh_today_recommendations(db, user_id=user_id, rec_date=rec_date)
        viewed_today = _today_viewed_record_ids(db, user_id=user_id)
        keep_rows = [row for row in rows if int(row.record_id) not in viewed_today]

    record_ids = [int(row.record_id) for row in keep_rows]
    if not record_ids:
        return success_response(data={"date": str(rec_date), "list": []})

    rec_map = {int(row.record_id): row for row in keep_rows}
    record_rows = db.query(DownloadRecord).filter(DownloadRecord.id.in_(record_ids)).all()
    payload_list = []
    for row in record_rows:
        rec = rec_map.get(int(row.id))
        if rec is None:
            continue
        payload_list.append(_build_record_payload(row, reason=rec.reason, score=float(rec.score or 0.0)))

    payload_list.sort(key=lambda x: (float(x.get("score") or 0.0), int(x["id"])), reverse=True)
    return success_response(data={"date": str(rec_date), "list": payload_list})


@router.post("/recommendations/refresh")
def personal_refresh_recommendations(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    rec_date = datetime.now(UTC).date()
    rows = _refresh_today_recommendations(db, user_id=user_id, rec_date=rec_date)
    return success_response(data={"date": str(rec_date), "count": len(rows)}, message="recommendations refreshed")


@router.post("/recommendations/click/{record_id}")
def personal_recommend_click(
    record_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    _record_user_action(
        db,
        user_id=user_id,
        record_id=int(record_id),
        action_type="recommend_click",
        action_value={"source": "recommendations_today"},
    )
    db.commit()
    return success_response(data={"record_id": record_id}, message="click recorded")


@router.get("/progress/{record_id}")
def personal_get_play_progress(
    record_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    row = (
        db.query(PlayProgress)
        .filter(PlayProgress.user_id == user_id, PlayProgress.record_id == int(record_id))
        .first()
    )
    if not row:
        return success_response(
            data={
                "record_id": int(record_id),
                "last_position_sec": 0.0,
                "duration_sec": 0.0,
                "is_completed": False,
                "updated_at": None,
            }
        )

    return success_response(
        data={
            "record_id": int(record_id),
            "last_position_sec": float(row.last_position_sec or 0.0),
            "duration_sec": float(row.duration_sec or 0.0),
            "is_completed": bool(row.is_completed),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )


@router.put("/progress/{record_id}")
def personal_update_play_progress(
    record_id: int,
    payload: PlayProgressUpdateRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    rid = int(record_id)

    row = db.query(PlayProgress).filter(PlayProgress.user_id == user_id, PlayProgress.record_id == rid).first()
    if not row:
        row = PlayProgress(user_id=user_id, record_id=rid)
        db.add(row)

    last_pos = max(0.0, float(payload.last_position_sec or 0.0))
    duration = max(0.0, float(payload.duration_sec or 0.0))
    completed = bool(payload.is_completed) if payload.is_completed is not None else False

    if duration > 0 and last_pos > duration:
        last_pos = duration
    if duration > 0 and last_pos >= max(0.0, duration - 2.0):
        completed = True

    row.last_position_sec = last_pos
    row.duration_sec = duration
    row.is_completed = completed
    row.updated_at = datetime.now(UTC)

    action_type = "play_complete" if completed else "play_seek"
    _record_user_action(
        db,
        user_id=user_id,
        record_id=rid,
        action_type=action_type,
        action_value={"position_sec": last_pos, "duration_sec": duration},
    )
    db.commit()

    return success_response(
        data={
            "record_id": rid,
            "last_position_sec": last_pos,
            "duration_sec": duration,
            "is_completed": completed,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        },
        message="progress updated",
    )


@router.get("/recap")
def personal_recap(
    period: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    now = datetime.now(UTC)
    today = datetime(now.year, now.month, now.day, tzinfo=UTC)
    if period == "weekly":
        start = today - timedelta(days=6)
    else:
        start = today - timedelta(days=29)
    end = now

    new_rows = (
        db.query(DownloadRecord.id, DownloadRecord.file_size)
        .filter(
            DownloadRecord.status.in_([DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE]),
            or_(
                and_(DownloadRecord.completed_at.isnot(None), DownloadRecord.completed_at >= start, DownloadRecord.completed_at <= end),
                and_(DownloadRecord.completed_at.is_(None), DownloadRecord.created_at >= start, DownloadRecord.created_at <= end),
            ),
        )
        .all()
    )
    new_files_count = len(new_rows)
    new_files_size_bytes = int(sum(int(row.file_size or 0) for row in new_rows))

    action_rows = (
        db.query(UserAction.record_id, UserAction.action_type, UserAction.action_value, UserAction.created_at)
        .filter(
            UserAction.user_id == user_id,
            UserAction.created_at >= start,
            UserAction.created_at <= end,
            UserAction.record_id.isnot(None),
            UserAction.action_type.in_(["play_seek", "play_complete", "recommend_click", "favorite_add", "preview_open"]),
        )
        .order_by(UserAction.record_id.asc(), UserAction.created_at.asc())
        .all()
    )

    record_ids = sorted({int(row.record_id or 0) for row in action_rows if int(row.record_id or 0) > 0})
    record_rows = db.query(DownloadRecord.id, DownloadRecord.chat_name).filter(DownloadRecord.id.in_(record_ids)).all() if record_ids else []
    record_chat_map = {int(row.id): str(row.chat_name or "-") for row in record_rows}

    record_max_position: dict[int, float] = {}
    viewed_ids: set[int] = set()
    completed_ids: set[int] = set()
    channel_scores: dict[str, float] = defaultdict(float)

    if period == "weekly":
        bucket_starts = [start + timedelta(days=i) for i in range(7)]
        bucket_ends = [s + timedelta(days=1) for s in bucket_starts]
        bucket_labels = [s.strftime("%m-%d") for s in bucket_starts]
    else:
        bucket_starts = []
        s = start
        while s <= today:
            bucket_starts.append(s)
            s = s + timedelta(days=7)
        bucket_ends = [min(s + timedelta(days=7), today + timedelta(days=1)) for s in bucket_starts]
        bucket_labels = [f"{s.strftime('%m-%d')}~{(e - timedelta(days=1)).strftime('%m-%d')}" for s, e in zip(bucket_starts, bucket_ends)]

    bucket_viewed: list[set[int]] = [set() for _ in bucket_labels]
    bucket_completed: list[set[int]] = [set() for _ in bucket_labels]

    def locate_bucket(ts: datetime) -> int | None:
        for i, (b_start, b_end) in enumerate(zip(bucket_starts, bucket_ends)):
            if b_start <= ts < b_end:
                return i
        return None

    action_weight = {
        "play_complete": 3.0,
        "play_seek": 1.0,
        "favorite_add": 2.2,
        "recommend_click": 0.6,
        "preview_open": 0.3,
    }

    for row in action_rows:
        rid = int(row.record_id or 0)
        if rid <= 0:
            continue
        created_at = _as_aware_utc(row.created_at) or start
        action_type = str(row.action_type or "")

        chat_name = record_chat_map.get(rid, "-")
        channel_scores[chat_name] += float(action_weight.get(action_type, 0.2))

        payload = _safe_load_action_value(row.action_value)
        if action_type in {"play_seek", "play_complete"}:
            viewed_ids.add(rid)
            pos = max(0.0, float(payload.get("position_sec", 0.0) or 0.0))
            if pos > record_max_position.get(rid, 0.0):
                record_max_position[rid] = pos
            idx = locate_bucket(created_at)
            if idx is not None:
                bucket_viewed[idx].add(rid)

        if action_type == "play_complete":
            completed_ids.add(rid)
            idx = locate_bucket(created_at)
            if idx is not None:
                bucket_completed[idx].add(rid)

    total_play_seconds = int(sum(record_max_position.values()))
    most_watched_channel = "-"
    if channel_scores:
        most_watched_channel = max(channel_scores.items(), key=lambda x: x[1])[0]

    completion_rate = round((len(completed_ids) * 100.0 / len(viewed_ids)), 2) if viewed_ids else 0.0
    completion_trend = []
    for label, viewed_set, completed_set in zip(bucket_labels, bucket_viewed, bucket_completed):
        rate = round((len(completed_set) * 100.0 / len(viewed_set)), 2) if viewed_set else 0.0
        completion_trend.append(
            {
                "label": label,
                "completion_rate": rate,
                "viewed_count": len(viewed_set),
                "completed_count": len(completed_set),
            }
        )

    return success_response(
        data={
            "period": period,
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "new_files_count": new_files_count,
            "new_files_size_bytes": new_files_size_bytes,
            "total_play_seconds": total_play_seconds,
            "most_watched_channel": most_watched_channel,
            "completion_rate": completion_rate,
            "completion_trend": completion_trend,
        }
    )


@router.get("/preferences")
def personal_get_preferences(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    pref = _ensure_preference_profile(db, user_id=user_id)
    updated_at = pref.get("updated_at")
    stale_seconds = None
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        stale_seconds = int((datetime.now(UTC) - updated_at).total_seconds())

    def _to_ranked(data: dict[str, float], limit: int) -> list[dict]:
        return [{"key": k, "weight": round(float(v), 4)} for k, v in sorted(data.items(), key=lambda x: x[1], reverse=True)[:limit]]

    return success_response(
        data={
            "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else pref.get("updated_at"),
            "stale_seconds": stale_seconds,
            "channel_weights": _to_ranked(pref.get("channel", {}), 30),
            "media_type_weights": _to_ranked(pref.get("media_type", {}), 10),
            "tag_weights": _to_ranked(pref.get("tag", {}), 60),
        }
    )


@router.post("/preferences/refresh")
def personal_refresh_preferences(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    pref = _ensure_preference_profile(db, user_id=user_id, force=True)
    channel_count = len(pref.get("channel", {}))
    media_count = len(pref.get("media_type", {}))
    tag_count = len(pref.get("tag", {}))
    return success_response(
        data={
            "updated_at": pref.get("updated_at"),
            "channel_count": channel_count,
            "media_type_count": media_count,
            "tag_count": tag_count,
        },
        message="preferences refreshed",
    )


@router.put("/preferences/manual")
def personal_manual_preferences(
    payload: PreferenceManualUpdateRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    updated = 0
    for item in payload.items:
        key = str(item.key or "").strip()
        if not key:
            continue
        kwargs = {"channel": None, "media_type": None, "tag": None}
        if item.kind == "channel":
            kwargs["channel"] = key
        elif item.kind == "media_type":
            kwargs["media_type"] = key.lower()
        else:
            kwargs["tag"] = key.lower()
        _upsert_preference_row(
            db,
            user_id=user_id,
            channel=kwargs["channel"],
            media_type=kwargs["media_type"],
            tag=kwargs["tag"],
            weight=float(item.weight),
            source="manual",
        )
        updated += 1
    db.commit()
    return success_response(data={"updated": updated}, message="preferences updated")


def _playback_state_key(user_id: int, collection_id: int) -> str:
    return f"personal.playback.state.u{int(user_id)}.c{int(collection_id)}"


def _load_collection_video_rows(db: Session, *, user_id: int, collection_id: int) -> list[dict]:
    exists = (
        db.query(UserCollection.id)
        .filter(UserCollection.id == int(collection_id), UserCollection.user_id == int(user_id))
        .first()
    )
    if exists is None:
        raise AppException("collection not found", status_code=404)

    item_rows = (
        db.query(UserCollectionItem.record_id, UserCollectionItem.sort_order, UserCollectionItem.created_at)
        .filter(
            UserCollectionItem.user_id == int(user_id),
            UserCollectionItem.collection_id == int(collection_id),
        )
        .order_by(UserCollectionItem.sort_order.asc(), UserCollectionItem.id.asc())
        .all()
    )
    if not item_rows:
        return []

    record_ids = [int(row.record_id) for row in item_rows]
    rec_rows = (
        db.query(DownloadRecord)
        .filter(
            DownloadRecord.id.in_(record_ids),
            DownloadRecord.media_type == "video",
            DownloadRecord.status.in_([DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE]),
        )
        .all()
    )
    rec_map = {int(r.id): r for r in rec_rows}

    progress_rows = (
        db.query(PlayProgress.record_id, PlayProgress.duration_sec)
        .filter(
            PlayProgress.user_id == int(user_id),
            PlayProgress.record_id.in_(record_ids),
        )
        .all()
    )
    duration_map = {int(row.record_id): float(row.duration_sec or 0.0) for row in progress_rows}

    out: list[dict] = []
    for item in item_rows:
        rid = int(item.record_id)
        rec = rec_map.get(rid)
        if rec is None:
            continue
        out.append(
            {
                "id": rid,
                "title": rec.saved_file_name or rec.original_file_name or f"record_{rid}",
                "file_path": rec.saved_path or "",
                "play_url": f"/api/downloads/{rid}/file?mode=inline",
                "duration": round(float(duration_map.get(rid, 0.0)), 2),
                "cover": f"/api/downloads/{rid}/thumbnail",
                "size": int(rec.file_size or 0),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "sort_order": int(item.sort_order or 0),
            }
        )
    return out


def _load_playback_state(db: Session, *, user_id: int, collection_id: int) -> dict | None:
    key = _playback_state_key(user_id, collection_id)
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None or not row.value:
        return None
    try:
        data = json.loads(row.value)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _save_playback_state(db: Session, *, user_id: int, collection_id: int, payload: dict) -> None:
    key = _playback_state_key(user_id, collection_id)
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(
            key=key,
            value_type="json",
            description="personal playlist playback state",
        )
        db.add(row)
    row.value = json.dumps(payload, ensure_ascii=False)
    row.updated_at = datetime.now(UTC)


@router.get("/collections/{collection_id}/videos")
def personal_collection_videos(
    collection_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    videos = _load_collection_video_rows(db, user_id=user_id, collection_id=int(collection_id))
    return success_response(
        data={
            "collection_id": int(collection_id),
            "total": len(videos),
            "list": videos,
        }
    )


@router.post("/collections/{collection_id}/playback/init")
def personal_collection_playback_init(
    collection_id: int,
    payload: PlaybackInitRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    videos = _load_collection_video_rows(db, user_id=user_id, collection_id=int(collection_id))
    mode = payload.mode
    slot_count = int(payload.slot_count or 8)

    if mode == "random":
        shuffled = videos[:]
        random.shuffle(shuffled)
        queue = shuffled
    else:
        queue = videos

    saved_state = _load_playback_state(db, user_id=user_id, collection_id=int(collection_id)) if payload.use_saved_state else None
    if saved_state and isinstance(saved_state, dict):
        queue_ids = saved_state.get("queue_ids", [])
        slots = saved_state.get("slots", [])
        if isinstance(queue_ids, list) and isinstance(slots, list):
            id_map = {int(item["id"]): item for item in queue}
            restored_queue = [id_map[i] for i in queue_ids if int(i) in id_map]
            restored_slots = []
            for i in range(slot_count):
                slot = slots[i] if i < len(slots) and isinstance(slots[i], dict) else {}
                cur_id = int(slot.get("current_id", 0) or 0)
                restored_slots.append(
                    {
                        "slot_index": i,
                        "status": str(slot.get("status") or "waiting"),
                        "video": id_map.get(cur_id),
                    }
                )
            return success_response(
                data={
                    "collection_id": int(collection_id),
                    "mode": mode,
                    "slot_count": slot_count,
                    "total": len(queue),
                    "queue": restored_queue,
                    "initial_slots": restored_slots,
                    "restored": True,
                }
            )

    initial_slots = []
    for idx in range(slot_count):
        if idx < len(queue):
            initial_slots.append({"slot_index": idx, "status": "playing", "video": queue[idx]})
        else:
            initial_slots.append({"slot_index": idx, "status": "waiting", "video": None})

    return success_response(
        data={
            "collection_id": int(collection_id),
            "mode": mode,
            "slot_count": slot_count,
            "total": len(queue),
            "queue": queue[slot_count:],
            "initial_slots": initial_slots,
            "restored": False,
        }
    )


@router.get("/collections/{collection_id}/playback/state")
def personal_collection_playback_state_get(
    collection_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    state = _load_playback_state(db, user_id=user_id, collection_id=int(collection_id))
    return success_response(data={"collection_id": int(collection_id), "state": state})


@router.put("/collections/{collection_id}/playback/state")
def personal_collection_playback_state_put(
    collection_id: int,
    payload: PlaybackStateUpdateRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    _save_playback_state(
        db,
        user_id=user_id,
        collection_id=int(collection_id),
        payload={
            "mode": payload.mode,
            "queue_ids": [int(i) for i in (payload.queue_ids or [])],
            "slots": payload.slots or [],
            "stats": payload.stats or {},
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    db.commit()
    return success_response(data={"collection_id": int(collection_id)}, message="playback state updated")


@router.post("/collections")
def personal_create_collection(
    payload: CollectionCreateRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    name = payload.name.strip()
    if not name:
        raise AppException("collection name is required", status_code=400)

    exists = (
        db.query(UserCollection)
        .filter(UserCollection.user_id == user_id, func.lower(UserCollection.name) == name.lower())
        .first()
    )
    if exists is not None:
        raise AppException("collection name already exists", status_code=400)

    if payload.sort_order is None:
        max_sort = db.query(func.max(UserCollection.sort_order)).filter(UserCollection.user_id == user_id).scalar()
        sort_order = int(max_sort or 0) + 10
    else:
        sort_order = int(payload.sort_order)

    row = UserCollection(
        user_id=user_id,
        name=name,
        description=(payload.description or "").strip() or None,
        sort_order=sort_order,
    )
    db.add(row)
    db.commit()

    return success_response(data={"id": int(row.id)}, message="collection created")


@router.get("/collections")
def personal_list_collections(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    return success_response(data={"list": _load_user_collections(db, user_id=user_id)})


@router.put("/collections/{collection_id}")
def personal_update_collection(
    collection_id: int,
    payload: CollectionUpdateRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    row = (
        db.query(UserCollection)
        .filter(UserCollection.id == int(collection_id), UserCollection.user_id == user_id)
        .first()
    )
    if row is None:
        raise AppException("collection not found", status_code=404)

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise AppException("collection name is required", status_code=400)
        exists = (
            db.query(UserCollection)
            .filter(
                UserCollection.user_id == user_id,
                func.lower(UserCollection.name) == new_name.lower(),
                UserCollection.id != int(collection_id),
            )
            .first()
        )
        if exists is not None:
            raise AppException("collection name already exists", status_code=400)
        row.name = new_name

    if payload.description is not None:
        row.description = (payload.description or "").strip() or None
    if payload.sort_order is not None:
        row.sort_order = int(payload.sort_order)

    row.updated_at = datetime.now(UTC)
    db.commit()
    return success_response(data={"id": int(collection_id)}, message="collection updated")


@router.delete("/collections/{collection_id}")
def personal_delete_collection(
    collection_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    row = (
        db.query(UserCollection)
        .filter(UserCollection.id == int(collection_id), UserCollection.user_id == user_id)
        .first()
    )
    if row is None:
        raise AppException("collection not found", status_code=404)

    db.query(UserCollectionItem).filter(
        UserCollectionItem.user_id == user_id,
        UserCollectionItem.collection_id == int(collection_id),
    ).delete()
    db.delete(row)
    db.commit()
    return success_response(data={"id": int(collection_id)}, message="collection deleted")


@router.post("/collections/{collection_id}/items")
def personal_add_collection_item(
    collection_id: int,
    payload: CollectionAddItemRequest,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    cid = int(collection_id)
    rid = int(payload.record_id)

    collection = db.query(UserCollection).filter(UserCollection.id == cid, UserCollection.user_id == user_id).first()
    if collection is None:
        raise AppException("collection not found", status_code=404)

    record = db.query(DownloadRecord).filter(DownloadRecord.id == rid).first()
    if record is None:
        raise AppException("record not found", status_code=404)

    exists = (
        db.query(UserCollectionItem)
        .filter(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.collection_id == cid,
            UserCollectionItem.record_id == rid,
        )
        .first()
    )
    if exists is not None:
        raise AppException("record already exists in this collection", status_code=400)

    if payload.sort_order is None:
        max_sort = (
            db.query(func.max(UserCollectionItem.sort_order))
            .filter(UserCollectionItem.user_id == user_id, UserCollectionItem.collection_id == cid)
            .scalar()
        )
        sort_order = int(max_sort or 0) + 10
    else:
        sort_order = int(payload.sort_order)

    item = UserCollectionItem(
        user_id=user_id,
        collection_id=cid,
        record_id=rid,
        sort_order=sort_order,
    )
    db.add(item)
    _record_user_action(
        db,
        user_id=user_id,
        record_id=rid,
        action_type="favorite_add",
        action_value={"collection_id": cid},
    )
    db.commit()
    return success_response(data={"collection_id": cid, "record_id": rid}, message="item added")


@router.delete("/collections/{collection_id}/items/{record_id}")
def personal_delete_collection_item(
    collection_id: int,
    record_id: int,
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> dict:
    user_id = int(x_user_id or 1)
    cid = int(collection_id)
    rid = int(record_id)

    row = (
        db.query(UserCollectionItem)
        .filter(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.collection_id == cid,
            UserCollectionItem.record_id == rid,
        )
        .first()
    )
    if row is None:
        raise AppException("collection item not found", status_code=404)

    db.delete(row)
    _record_user_action(
        db,
        user_id=user_id,
        record_id=rid,
        action_type="favorite_remove",
        action_value={"collection_id": cid},
    )
    db.commit()
    return success_response(data={"collection_id": cid, "record_id": rid}, message="item deleted")

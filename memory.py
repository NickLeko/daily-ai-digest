from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import (
    DIGEST_MEMORY_FILE_PATH,
    HISTORY_CONTEXT_WINDOW_DAYS,
    HISTORY_MAX_EVENTS,
    HISTORY_REPEAT_WINDOW_DAYS,
    LOCAL_TIMEZONE,
    PRIORITY_THEME_RULES,
)


DigestMemory = Dict[str, Any]
MEMORY_PATH = Path(DIGEST_MEMORY_FILE_PATH)


def _default_memory() -> DigestMemory:
    return {
        "version": 1,
        "events": [],
    }


def _today_key() -> str:
    return datetime.now(ZoneInfo(LOCAL_TIMEZONE)).date().isoformat()


def _parse_event_date(value: str) -> datetime | None:
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    for candidate in (raw_value, f"{raw_value}T00:00:00+00:00"):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=ZoneInfo("UTC"))
            return parsed
        except ValueError:
            continue
    return None


def load_digest_memory() -> DigestMemory:
    if not MEMORY_PATH.exists():
        return _default_memory()

    try:
        with MEMORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _default_memory()

    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    cleaned_events: List[Dict[str, Any]] = []
    for event in events[-HISTORY_MAX_EVENTS:]:
        if not isinstance(event, dict):
            continue
        cleaned_events.append(
            {
                "date": str(event.get("date", "") or ""),
                "item_key": str(event.get("item_key", "") or ""),
                "category": str(event.get("category", "") or ""),
                "title": str(event.get("title", "") or ""),
                "url": str(event.get("url", "") or ""),
                "source": str(event.get("source", "") or ""),
                "topic_key": str(event.get("topic_key", "") or ""),
                "themes": [
                    str(theme).strip()
                    for theme in event.get("themes", [])
                    if str(theme).strip()
                ],
                "entities": [
                    str(entity).strip()
                    for entity in event.get("entities", [])
                    if str(entity).strip()
                ],
                "priority_score": float(event.get("priority_score", 0.0) or 0.0),
                "objective_scores": {
                    str(key): float(value or 0.0)
                    for key, value in (event.get("objective_scores", {}) or {}).items()
                    if str(key).strip()
                },
                "signal": str(event.get("signal", "") or ""),
            }
        )

    return {
        "version": int(data.get("version", 1) or 1),
        "events": cleaned_events,
    }


def save_digest_memory(memory: DigestMemory) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def build_history_context(
    item: Dict[str, Any],
    memory: DigestMemory,
    *,
    themes: List[str],
    entities: List[str],
    now: datetime,
) -> Dict[str, Any]:
    repeat_cutoff = now - timedelta(days=HISTORY_REPEAT_WINDOW_DAYS)
    item_key = str(item.get("item_key", "") or "")

    item_seen_count = 0
    last_seen_at: datetime | None = None
    recent_theme_counts: Counter[str] = Counter()
    recent_entity_counts: Counter[str] = Counter()

    for event in memory.get("events", []):
        event_dt = _parse_event_date(str(event.get("date", "")))
        if not event_dt:
            continue

        if str(event.get("item_key", "")) == item_key:
            item_seen_count += 1
            if last_seen_at is None or event_dt > last_seen_at:
                last_seen_at = event_dt

        if event_dt < repeat_cutoff:
            continue

        for theme in themes:
            if theme in set(event.get("themes", [])):
                recent_theme_counts[theme] += 1
        for entity in entities:
            if entity in set(event.get("entities", [])):
                recent_entity_counts[entity] += 1

    days_since_last_seen: int | None = None
    if last_seen_at is not None:
        days_since_last_seen = max((now - last_seen_at).days, 0)

    return {
        "item_seen_count": item_seen_count,
        "days_since_last_seen": days_since_last_seen,
        "recent_theme_counts": dict(recent_theme_counts),
        "recent_entity_counts": dict(recent_entity_counts),
        "recent_theme_hits": sum(recent_theme_counts.values()),
        "recent_entity_hits": sum(recent_entity_counts.values()),
    }


def build_memory_snapshot(
    memory: DigestMemory,
    *,
    now: datetime | None = None,
) -> Dict[str, Any]:
    now = now or datetime.now(ZoneInfo("UTC"))
    cutoff = now - timedelta(days=HISTORY_CONTEXT_WINDOW_DAYS)
    theme_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()

    for event in memory.get("events", []):
        event_dt = _parse_event_date(str(event.get("date", "")))
        if not event_dt or event_dt < cutoff:
            continue
        theme_counts.update(event.get("themes", []))
        entity_counts.update(event.get("entities", []))

    top_themes = [
        {
            "theme": theme,
            "label": PRIORITY_THEME_RULES.get(theme, {}).get("label", theme),
            "count": count,
        }
        for theme, count in theme_counts.most_common(5)
    ]
    top_entities = [
        {"entity": entity, "count": count}
        for entity, count in entity_counts.most_common(5)
    ]

    return {
        "lookback_days": HISTORY_CONTEXT_WINDOW_DAYS,
        "top_themes": top_themes,
        "top_entities": top_entities,
        "event_count": len(memory.get("events", [])),
    }


def record_digest_items(items: List[Dict[str, Any]]) -> None:
    memory = load_digest_memory()
    events = list(memory.get("events", []))
    digest_date = _today_key()

    for item in items:
        events.append(
            {
                "date": digest_date,
                "item_key": str(item.get("item_key", "") or ""),
                "category": str(item.get("category", "") or ""),
                "title": str(item.get("title", "") or ""),
                "url": str(item.get("url", "") or ""),
                "source": str(item.get("source", "") or ""),
                "topic_key": str(item.get("topic_key", "") or ""),
                "themes": [
                    str(theme).strip()
                    for theme in item.get("matched_themes", [])
                    if str(theme).strip()
                ],
                "entities": [
                    str(entity).strip()
                    for entity in item.get("entity_keys", [])
                    if str(entity).strip()
                ],
                "priority_score": round(float(item.get("priority_score", 0.0) or 0.0), 2),
                "objective_scores": {
                    str(key): round(float(value or 0.0), 2)
                    for key, value in (item.get("objective_scores", {}) or {}).items()
                },
                "signal": str(item.get("signal", "") or ""),
            }
        )

    memory["events"] = events[-HISTORY_MAX_EVENTS:]
    save_digest_memory(memory)

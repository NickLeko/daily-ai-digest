from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import LOCAL_TIMEZONE, STATE_FILE_PATH


STATE_PATH = Path(STATE_FILE_PATH)


def local_now() -> datetime:
    return datetime.now(ZoneInfo(LOCAL_TIMEZONE))


def today_key() -> str:
    return local_now().date().isoformat()


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "last_sent_date": "",
            "sent_items": [],
        }

    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {
            "last_sent_date": "",
            "sent_items": [],
        }

    sent_items = data.get("sent_items", [])
    if not isinstance(sent_items, list):
        sent_items = []

    return {
        "last_sent_date": str(data.get("last_sent_date", "") or ""),
        "sent_items": sent_items,
    }


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def already_sent_today() -> bool:
    return load_state().get("last_sent_date") == today_key()


def mark_sent(item_keys: List[str]) -> None:
    state = load_state()
    existing_keys = [str(key) for key in state.get("sent_items", []) if str(key).strip()]
    combined = existing_keys + [key for key in item_keys if key]

    seen = set()
    deduped: List[str] = []
    for key in reversed(combined):
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    state["last_sent_date"] = today_key()
    state["sent_items"] = list(reversed(deduped))[-250:]
    save_state(state)


def get_sent_item_keys() -> set[str]:
    return {
        str(key).strip()
        for key in load_state().get("sent_items", [])
        if str(key).strip()
    }

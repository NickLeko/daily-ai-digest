from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import AppConfig, current_config
from storage import read_json_file, write_json_file


def _resolved_config(config: AppConfig | None = None) -> AppConfig:
    return config or current_config()


def _state_path(*, config: AppConfig | None = None) -> Path:
    return Path(_resolved_config(config).state_file_path)


def local_now(*, config: AppConfig | None = None) -> datetime:
    return datetime.now(ZoneInfo(_resolved_config(config).local_timezone))


def today_key(*, config: AppConfig | None = None) -> str:
    return local_now(config=config).date().isoformat()


def load_state(*, config: AppConfig | None = None) -> Dict[str, Any]:
    data = read_json_file(
        _state_path(config=config),
        {"last_sent_date": "", "sent_items": []},
        expected_type=dict,
    )
    sent_items = data.get("sent_items", [])
    if not isinstance(sent_items, list):
        sent_items = []

    return {
        "last_sent_date": str(data.get("last_sent_date", "") or ""),
        "sent_items": sent_items,
    }


def save_state(state: Dict[str, Any], *, config: AppConfig | None = None) -> None:
    write_json_file(_state_path(config=config), state)


def already_sent_today(*, config: AppConfig | None = None) -> bool:
    return load_state(config=config).get("last_sent_date") == today_key(config=config)


def mark_sent(item_keys: List[str], *, config: AppConfig | None = None) -> None:
    state = load_state(config=config)
    existing_keys = [str(key) for key in state.get("sent_items", []) if str(key).strip()]
    combined = existing_keys + [key for key in item_keys if key]

    seen = set()
    deduped: List[str] = []
    for key in reversed(combined):
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    state["last_sent_date"] = today_key(config=config)
    state["sent_items"] = list(reversed(deduped))[-250:]
    save_state(state, config=config)


def get_sent_item_keys(*, config: AppConfig | None = None) -> set[str]:
    return {
        str(key).strip()
        for key in load_state(config=config).get("sent_items", [])
        if str(key).strip()
    }

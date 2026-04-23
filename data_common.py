from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List

from app_logging import info
from memory import DigestMemory
from scoring import attach_priority_scores


DigestItem = Dict[str, Any]


def iso_days_ago(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")

def truncate(text: str, max_len: int = 1200) -> str:
    text = " ".join((text or "").split())
    return text[:max_len]

def item_key(category: str, title: str, url: str) -> str:
    normalized_title = (title or "").strip().lower()
    normalized_url = (url or "").strip().lower()
    return f"{category.lower()}::{normalized_title}::{normalized_url}"

def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))

def strip_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(value or "")).split())

def parse_feed_datetime(entry: Dict[str, Any]) -> datetime | None:
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        return datetime(*parsed_struct[:6], tzinfo=timezone.utc)

    for field in ("published", "updated"):
        raw_value = entry.get(field)
        if not raw_value:
            continue
        try:
            parsed = parsedate_to_datetime(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None

def parse_fda_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def parse_iso_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def title_tokens(title: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (title or "").lower())
        if len(token) > 2
    }

def titles_are_similar(left: str, right: str) -> bool:
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    threshold = max(len(left_tokens), len(right_tokens))
    return overlap / threshold >= 0.8

def format_excluded_reasons(reasons: Counter[str]) -> str:
    if not reasons:
        return "none"
    return ", ".join(
        f"{reason}={count}" for reason, count in sorted(reasons.items())
    )

def format_score_breakdown(item: DigestItem) -> str:
    breakdown = item.get("score_breakdown", {})
    if not breakdown:
        return "no-score"
    parts = [
        f"{name}={value}"
        for name, value in breakdown.items()
        if name != "total"
    ]
    parts.append(f"total={item.get('selection_score', breakdown.get('total', 0))}")
    return ", ".join(parts)

def format_selected_items(items: List[DigestItem]) -> str:
    if not items:
        return "none"

    formatted = []
    for item in items:
        reference = item.get("id") or item.get("unique_id") or item.get("item_key") or item.get("title", "")
        priority_score = item.get("priority_score")
        priority_suffix = ""
        if priority_score is not None:
            priority_suffix = f" | priority={priority_score}"
        if item.get("category") == "Regulatory" and item.get("selection_score") is not None:
            formatted.append(
                f"{reference} | {item.get('title', 'Untitled')} | {format_score_breakdown(item)}{priority_suffix}"
            )
        else:
            formatted.append(f"{reference} | {item.get('title', 'Untitled')}{priority_suffix}")
    return "; ".join(formatted)

def log_section_debug(
    label: str,
    raw_count: int,
    filtered_count: int,
    excluded_reasons: Counter[str],
    selected_items: List[DigestItem],
) -> None:
    info(
        f"{label} selection",
        raw_count=raw_count,
        filtered_count=filtered_count,
        excluded_reasons=format_excluded_reasons(excluded_reasons),
        selected_items=format_selected_items(selected_items),
        fallback_triggered=(len(selected_items) == 0),
    )

def log_regulatory_source_debug(
    source_name: str,
    raw_count: int,
    normalized_count: int,
    excluded_reasons: Counter[str],
) -> None:
    info(
        f"Regulatory source {source_name}",
        raw_count=raw_count,
        normalized_count=normalized_count,
        excluded_reasons=format_excluded_reasons(excluded_reasons),
    )

def empty_source_stats(
    source_name: str,
    excluded_reasons: Counter[str],
) -> Dict[str, Any]:
    return {
        "source": source_name,
        "raw_count": 0,
        "normalized_count": 0,
        "excluded_reasons": excluded_reasons,
    }

def select_scored_items(
    items: List[DigestItem],
    *,
    sent_item_keys: set[str],
    limit: int,
    memory: DigestMemory | None = None,
    enforce_repo_generic_cap: bool = False,
    excluded_reasons: Counter[str] | None = None,
) -> List[DigestItem]:
    scored = attach_priority_scores(items, memory, sort_items=False)
    ranked = sorted(
        scored,
        key=lambda item: (
            item.get("item_key", "") not in sent_item_keys,
            float(item.get("priority_score", 0.0) or 0.0),
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )

    if not enforce_repo_generic_cap:
        return ranked[:limit]

    selected: List[DigestItem] = []
    generic_repo_count = 0

    for item in ranked:
        counts_toward_cap = bool(item.get("is_generic_devtool")) and not bool(
            item.get("generic_repo_cap_exempt")
        )
        if counts_toward_cap and generic_repo_count >= 1:
            if excluded_reasons is not None:
                excluded_reasons["generic_repo_cap"] += 1
            continue

        selected.append(item)
        if counts_toward_cap:
            generic_repo_count += 1
        if len(selected) >= limit:
            break

    return selected


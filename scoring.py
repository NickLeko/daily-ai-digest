from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from config import (
    OBJECTIVE_SCORE_WEIGHTS,
    PRIORITY_THEME_RULES,
    SCORING_WEIGHTS,
    TRACKED_ENTITY_RULES,
)
from memory import DigestMemory, build_history_context


DigestItem = Dict[str, Any]

DIMENSION_KEYS = [
    "career_relevance",
    "build_relevance",
    "content_potential",
    "regulatory_significance",
    "side_hustle_relevance",
    "timeliness",
    "novelty",
    "theme_momentum",
]

OBJECTIVE_LABELS = {
    "career": "Top item for career",
    "build": "Top item for build",
    "content": "Top item for content",
    "regulatory": "Top item for regulatory",
}

CATEGORY_BASELINES = {
    "Repo": {
        "build_relevance": 1.2,
        "content_potential": 0.4,
        "side_hustle_relevance": 0.4,
    },
    "News": {
        "career_relevance": 0.7,
        "content_potential": 0.9,
    },
    "Regulatory": {
        "career_relevance": 1.1,
        "content_potential": 0.6,
        "regulatory_significance": 2.2,
    },
}

REGULATORY_KEYWORDS = [
    "rule",
    "guidance",
    "fda",
    "cms",
    "onc",
    "hipaa",
    "privacy",
    "security",
    "compliance",
    "audit",
    "interoperability",
    "prior authorization",
]

CONTENT_SIGNAL_KEYWORDS = [
    "framework",
    "launch",
    "policy",
    "benchmark",
    "trend",
    "roadmap",
    "agent",
    "rag",
    "workflow",
    "fhir",
]


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def keyword_matches_text(keyword: str, text: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    normalized_text = normalize_text(text)
    if not normalized_keyword or not normalized_text:
        return False

    if " " in normalized_keyword:
        return f" {normalized_keyword} " in f" {normalized_text} "

    return normalized_keyword in set(normalized_text.split())


def matched_keywords(keywords: List[str], text: str) -> List[str]:
    return [keyword for keyword in keywords if keyword_matches_text(keyword, text)]


def item_text_blob(item: DigestItem) -> str:
    return " ".join(
        str(part).strip()
        for part in [
            item.get("title", ""),
            item.get("raw_text", ""),
            item.get("summary", ""),
            item.get("why_it_matters", ""),
            item.get("source", ""),
            item.get("organization", ""),
            item.get("subcategory", ""),
            item.get("topic_key", ""),
        ]
        if str(part).strip()
    )


def extract_theme_hits(item: DigestItem) -> Dict[str, List[str]]:
    text = item_text_blob(item)
    hits: Dict[str, List[str]] = {}
    for theme_key, config in PRIORITY_THEME_RULES.items():
        theme_hits = matched_keywords(config.get("keywords", []), text)
        if theme_hits:
            hits[theme_key] = theme_hits
    return hits


def extract_entity_keys(item: DigestItem) -> List[str]:
    text = item_text_blob(item)
    entity_keys = set()

    for entity_key, keywords in TRACKED_ENTITY_RULES.items():
        if matched_keywords(keywords, text):
            entity_keys.add(entity_key)

    organization = normalize_text(str(item.get("organization", "") or ""))
    if organization:
        entity_keys.add(f"org:{organization}")

    source = normalize_text(str(item.get("source", "") or ""))
    if source:
        entity_keys.add(f"source:{source}")

    if item.get("category") == "Repo":
        title = str(item.get("title", "") or "")
        if "/" in title:
            owner = normalize_text(title.split("/", 1)[0])
            if owner:
                entity_keys.add(f"owner:{owner}")

    firm_key = normalize_text(str(item.get("firm_key", "") or ""))
    if firm_key:
        entity_keys.add(f"firm:{firm_key}")

    return sorted(entity_keys)


def clamp_score(value: float) -> float:
    return max(0.0, min(5.0, round(value, 2)))


def timeliness_score(item: DigestItem, *, now: datetime) -> float:
    published_at = item.get("published_at")
    if not isinstance(published_at, datetime):
        return 2.5

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age = now - published_at.astimezone(timezone.utc)
    if age <= timedelta(hours=24):
        return 5.0
    if age <= timedelta(days=3):
        return 4.2
    if age <= timedelta(days=7):
        return 3.4
    if age <= timedelta(days=14):
        return 2.5
    if age <= timedelta(days=30):
        return 1.7
    return 0.8


def novelty_score(history_context: Dict[str, Any]) -> float:
    seen_count = int(history_context.get("item_seen_count", 0) or 0)
    days_since_last_seen = history_context.get("days_since_last_seen")

    if seen_count == 0:
        return 5.0
    if days_since_last_seen is None:
        return 3.5
    if days_since_last_seen >= 30:
        return 3.4
    if days_since_last_seen >= 14:
        return 2.4
    if days_since_last_seen >= 7:
        return 1.4
    return 0.4


def theme_momentum_score(history_context: Dict[str, Any]) -> float:
    recent_theme_hits = int(history_context.get("recent_theme_hits", 0) or 0)
    recent_entity_hits = int(history_context.get("recent_entity_hits", 0) or 0)
    combined = recent_theme_hits + recent_entity_hits
    if combined <= 0:
        return 0.4
    if combined == 1:
        return 1.5
    if combined <= 3:
        return 2.6
    if combined <= 5:
        return 3.6
    return 4.6


def compute_dimension_scores(
    item: DigestItem,
    *,
    theme_hits: Dict[str, List[str]],
    history_context: Dict[str, Any],
    now: datetime,
) -> Dict[str, float]:
    scores = {dimension: 0.0 for dimension in DIMENSION_KEYS}

    for dimension, baseline in CATEGORY_BASELINES.get(item.get("category", ""), {}).items():
        scores[dimension] += baseline

    for theme_key, hits in theme_hits.items():
        theme_config = PRIORITY_THEME_RULES.get(theme_key, {})
        scale = min(1.35, 0.85 + (0.1 * len(hits)))
        for dimension, boost in theme_config.get("dimension_boosts", {}).items():
            scores[dimension] += boost * scale

    text = item_text_blob(item)
    if matched_keywords(REGULATORY_KEYWORDS, text):
        scores["regulatory_significance"] += 0.9
        scores["career_relevance"] += 0.3

    if matched_keywords(CONTENT_SIGNAL_KEYWORDS, text):
        scores["content_potential"] += 0.5

    if item.get("category") == "Repo":
        scores["build_relevance"] += 0.4

    scores["timeliness"] = timeliness_score(item, now=now)
    scores["novelty"] = novelty_score(history_context)
    scores["theme_momentum"] = theme_momentum_score(history_context)

    return {
        dimension: clamp_score(value)
        for dimension, value in scores.items()
    }


def compute_objective_scores(dimension_scores: Dict[str, float]) -> Dict[str, float]:
    return {
        objective: round(
            sum(
                dimension_scores.get(dimension, 0.0) * weight
                for dimension, weight in weights.items()
            ),
            2,
        )
        for objective, weights in OBJECTIVE_SCORE_WEIGHTS.items()
    }


def strongest_dimensions(dimension_scores: Dict[str, float]) -> List[str]:
    ranked = sorted(
        dimension_scores.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    return [name for name, _value in ranked[:3]]


def priority_score(dimension_scores: Dict[str, float]) -> float:
    total = sum(
        dimension_scores.get(dimension, 0.0) * weight
        for dimension, weight in SCORING_WEIGHTS.items()
    )
    return round(total, 2)


def score_item(
    item: DigestItem,
    *,
    memory: DigestMemory,
    now: datetime,
) -> DigestItem:
    theme_hits = extract_theme_hits(item)
    matched_themes = sorted(theme_hits.keys())
    entity_keys = extract_entity_keys(item)
    history_context = build_history_context(
        item,
        memory,
        themes=matched_themes,
        entities=entity_keys,
        now=now,
    )
    dimension_scores = compute_dimension_scores(
        item,
        theme_hits=theme_hits,
        history_context=history_context,
        now=now,
    )
    objective_scores = compute_objective_scores(dimension_scores)

    return {
        **item,
        "matched_themes": matched_themes,
        "entity_keys": entity_keys,
        "score_dimensions": dimension_scores,
        "objective_scores": objective_scores,
        "priority_score": priority_score(dimension_scores),
        "score_focus": strongest_dimensions(dimension_scores),
        "history_context": history_context,
    }


def attach_priority_scores(
    items: List[DigestItem],
    memory: DigestMemory | None,
    *,
    now: datetime | None = None,
    sort_items: bool = True,
) -> List[DigestItem]:
    now = now or datetime.now(timezone.utc)
    memory = memory or {"version": 1, "events": []}
    scored = [score_item(item, memory=memory, now=now) for item in items]
    if not sort_items:
        return scored
    return sort_items_by_priority(scored)


def sort_items_by_priority(items: List[DigestItem]) -> List[DigestItem]:
    return sorted(
        items,
        key=lambda item: (
            float(item.get("priority_score", 0.0) or 0.0),
            float(max((item.get("objective_scores", {}) or {}).values(), default=0.0)),
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )


def build_top_picks(items: List[DigestItem]) -> List[Dict[str, Any]]:
    picks: List[Dict[str, Any]] = []

    for objective, label in OBJECTIVE_LABELS.items():
        ranked = sorted(
            items,
            key=lambda item: (
                float((item.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
                float(item.get("priority_score", 0.0) or 0.0),
            ),
            reverse=True,
        )

        choice = ranked[0] if ranked else None
        if not choice:
            continue

        picks.append(
            {
                "objective": objective,
                "label": label,
                "item": choice,
                "score": float((choice.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
            }
        )

    return picks

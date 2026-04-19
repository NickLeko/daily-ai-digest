from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from agent_brief import build_operator_brief as build_strategy_brief
from config import (
    GITHUB_WATCHLIST_FILE_PATH,
    MARKET_MAP_FILE_PATH,
    OPERATOR_STORY_LIMIT,
    SOURCE_POLICY_FILE_PATH,
    THESES_FILE_PATH,
    WATCHLIST_STORY_LIMIT,
)
from memory import DigestMemory, latest_previous_brief
from scoring import OBJECTIVE_DISPLAY_ORDER
from selection_policy import (
    NEAR_MISS_LIMIT,
    NEAR_MISS_MIN_OBJECTIVE_SCORE,
    NEAR_MISS_MIN_REGULATORY_OBJECTIVE_SCORE,
    NEAR_MISS_MIN_STORY_SCORE,
    STORY_OBJECTIVE_MIN_SCORES,
    STORY_STRONG_OBJECTIVE_SCORE,
    STORY_STRONG_SCORE,
    TARGET_THEME_KEYS,
    confidence_display_for_story,
)
from signal_quality import classify_mapping_materiality
from state import local_now
from summarize import (
    sentence_start,
    why_it_matters_is_specific,
    workflow_actions_for_item,
    workflow_guidance_for_item,
)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "signal",
    "story",
    "cluster",
    "guidance",
    "news",
    "repo",
    "regulatory",
    "update",
    "with",
    "via",
    "new",
    "today",
}

ACTION_WORDS = {
    "audit",
    "build",
    "check",
    "decide",
    "deprioritize",
    "inventory",
    "map",
    "pilot",
    "prioritize",
    "rank",
    "review",
    "test",
    "track",
    "validate",
}

NEGATIVE_SIGNAL_WORDS = {
    "backlash",
    "breach",
    "delay",
    "lawsuit",
    "low adoption",
    "manual exception",
    "rollback",
    "skepticism",
}

DEFAULT_MARKET_BUCKET = {
    "Repo": "infra_devtools",
    "News": "buyer_adoption",
    "Regulatory": "regulation_policy",
}

OBJECTIVE_LABELS = {
    "career": "Top item for career",
    "build": "Top item for build",
    "content": "Top item for content",
    "regulatory": "Top item for regulatory",
}

OBJECTIVE_EMPTY_MESSAGES = {
    "career": "No high-signal career fit today.",
    "build": "No high-signal build fit today.",
    "content": "No strong content hook today.",
    "regulatory": "No high-signal regulatory item today.",
}

QUALITY_WARNING_LIMIT = 5
OBJECTIVE_MIN_SCORES = STORY_OBJECTIVE_MIN_SCORES

NEAR_MISS_BLOCKED_SUMMARY_PHRASES = {
    "integration leads should",
    "health it owners should",
    "backlog review",
    "fhir/api dependencies",
    "fhir api dependencies",
    "operator implication",
    "operator planning",
    "roadmap time",
    "why it matters",
}

RECALL_ENFORCEMENT_TOPIC_KEY = "recall_enforcement"

NO_STRONG_SIGNAL_OPERATOR_MOVES = {
    "top_insight": "No strong operator signal cleared today's quality bar.",
    "content_angle": "",
    "build_idea": "",
    "interview_talking_point": "",
    "watch_item": "Watch for concrete deployment, policy, reimbursement, or measurable workflow evidence before assigning roadmap time.",
}


def load_json_config(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return default

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default

    return data if isinstance(data, dict) else default


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def slugify(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", (value or "").lower()))[:80]


def unique(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def isoformat_or_empty(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value or "").strip()


def domain_from_value(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""

    if not candidate.startswith(("http://", "https://")):
        if "." not in candidate:
            return ""
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def label_for_reliability_score(score: int) -> str:
    if score >= 85:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def source_display_name(item: Dict[str, Any]) -> str:
    source_name = str(item.get("source", "") or "").strip()
    if source_name.startswith(("http://", "https://")):
        return domain_from_value(source_name) or source_name
    return source_name or (domain_from_value(str(item.get("url", "") or "")) or "Unknown source")


def reliability_for_item(
    item: Dict[str, Any],
    policies: Dict[str, Any],
) -> Dict[str, Any]:
    source_name = source_display_name(item)
    source_domain = domain_from_value(str(item.get("url", "") or "")) or domain_from_value(source_name)
    source_name_rules = policies.get("source_name_rules", {}) if isinstance(policies.get("source_name_rules", {}), dict) else {}
    domain_rules = policies.get("domain_rules", {}) if isinstance(policies.get("domain_rules", {}), dict) else {}
    suffix_rules = policies.get("suffix_rules", {}) if isinstance(policies.get("suffix_rules", {}), dict) else {}
    default_rule = policies.get("default", {"score": 60, "label": "Medium", "reason": "Unclassified source."})

    rule = None
    if source_name in source_name_rules:
        rule = source_name_rules[source_name]
    elif source_domain in domain_rules:
        rule = domain_rules[source_domain]
    else:
        for suffix, suffix_rule in suffix_rules.items():
            if source_domain.endswith(str(suffix).lower()):
                rule = suffix_rule
                break

    if rule is None and "press release" in normalize_text(source_name):
        rule = {
            "score": 42,
            "label": "Low",
            "reason": "Press release or vendor claim, not independent reporting.",
        }

    if rule is None and item.get("category") == "Regulatory":
        rule = {
            "score": 92,
            "label": "High",
            "reason": "Regulatory item sourced from a primary or official channel.",
        }

    applied = rule or default_rule
    score = int(applied.get("score", 60) or 60)
    label = str(applied.get("label", "") or label_for_reliability_score(score))
    return {
        "score": score,
        "label": label,
        "reason": str(applied.get("reason", "") or "Unclassified source."),
        "source_name": source_name,
        "source_domain": source_domain,
    }


def confidence_for_item(
    *,
    reliability_score: int,
    signal: str,
    support_count: int = 1,
    signal_quality: str = "medium",
    material_operator_signal: bool = True,
    low_signal_announcement: bool = False,
) -> str:
    normalized_signal = str(signal or "medium").lower()
    normalized_quality = str(signal_quality or "medium").lower()
    if low_signal_announcement or normalized_quality == "weak" or not material_operator_signal:
        return "Low"
    if normalized_quality == "medium":
        if reliability_score >= 85 and support_count >= 2 and normalized_signal == "high":
            return "High"
        if reliability_score >= 60:
            return "Medium"
        return "Low"
    if reliability_score >= 85 and support_count >= 2:
        return "High"
    if reliability_score >= 85 and normalized_signal in {"high", "medium"}:
        return "High"
    if reliability_score >= 60:
        return "Medium"
    return "Low"


def item_text(item: Dict[str, Any]) -> str:
    return " ".join(
        str(part).strip()
        for part in [
            item.get("title", ""),
            item.get("raw_text", ""),
            item.get("summary", ""),
            item.get("why_it_matters", ""),
            item.get("topic_key", ""),
            " ".join(str(value) for value in item.get("workflow_wedges", []) or []),
            " ".join(str(value) for value in item.get("matched_themes", []) or []),
            " ".join(str(value) for value in item.get("repo_topics", []) or []),
        ]
        if str(part).strip()
    )


def signature_tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if token not in STOPWORDS and len(token) > 2
    ]


def market_buckets_for_item(
    item: Dict[str, Any],
    market_map: Dict[str, Any],
) -> List[str]:
    text = item_text(item)
    bucket_scores: Dict[str, int] = {}
    for bucket in market_map.get("buckets", []):
        if not isinstance(bucket, dict):
            continue
        bucket_id = str(bucket.get("id", "") or "").strip()
        keywords = [str(value).strip() for value in bucket.get("keywords", []) if str(value).strip()]
        score = sum(1 for keyword in keywords if normalize_text(keyword) and normalize_text(keyword) in normalize_text(text))
        if score > 0 and bucket_id:
            bucket_scores[bucket_id] = score

    if bucket_scores:
        return [
            bucket_id
            for bucket_id, _score in sorted(
                bucket_scores.items(),
                key=lambda entry: (-entry[1], entry[0]),
            )
        ]

    fallback_bucket = DEFAULT_MARKET_BUCKET.get(str(item.get("category", "") or ""), "buyer_adoption")
    return [fallback_bucket]


def thesis_links_for_item(
    item: Dict[str, Any],
    theses: Dict[str, Any],
) -> List[Dict[str, Any]]:
    normalized = normalize_text(item_text(item))
    links: List[Dict[str, Any]] = []

    for thesis in theses.get("theses", []):
        if not isinstance(thesis, dict):
            continue
        thesis_id = str(thesis.get("id", "") or "").strip()
        title = str(thesis.get("title", "") or "").strip()
        core_hits = [
            keyword for keyword in thesis.get("keywords", [])
            if normalize_text(str(keyword)) and normalize_text(str(keyword)) in normalized
        ]
        support_hits = [
            keyword for keyword in thesis.get("support_keywords", [])
            if normalize_text(str(keyword)) and normalize_text(str(keyword)) in normalized
        ]
        weaken_hits = [
            keyword for keyword in thesis.get("weaken_keywords", [])
            if normalize_text(str(keyword)) and normalize_text(str(keyword)) in normalized
        ]
        adjacent_hits = [
            keyword for keyword in thesis.get("adjacent_keywords", [])
            if normalize_text(str(keyword)) and normalize_text(str(keyword)) in normalized
        ]

        relation = ""
        if core_hits:
            if weaken_hits and not support_hits:
                relation = "weakens" if len(weaken_hits) >= 2 else "complicates"
            elif support_hits or len(core_hits) >= 2:
                relation = "supports"
            else:
                relation = "adjacent"
        elif adjacent_hits:
            relation = "adjacent"

        if not relation or not thesis_id:
            continue

        links.append(
            {
                "thesis_id": thesis_id,
                "title": title,
                "relation": relation,
                "matched_keywords": unique(
                    [str(value) for value in (*core_hits, *support_hits, *weaken_hits, *adjacent_hits)]
                )[:4],
            }
        )

    return links


def watchlist_matches_for_item(
    item: Dict[str, Any],
    watchlist: Dict[str, Any],
) -> List[Dict[str, str]]:
    if item.get("category") != "Repo":
        return []

    repo_full_name = str(item.get("repo_full_name", "") or item.get("title", "") or "").strip()
    repo_owner = str(item.get("repo_owner", "") or "").strip()
    repo_topics = {
        normalize_text(str(topic))
        for topic in item.get("repo_topics", []) or []
        if normalize_text(str(topic))
    }
    text = normalize_text(
        " ".join(
            [
                str(item.get("title", "") or ""),
                str(item.get("evidence", "") or ""),
                str(item.get("_item", {}).get("raw_text", "") or ""),
                " ".join(str(topic) for topic in item.get("repo_topics", []) or []),
            ]
        )
    )
    matches: List[Dict[str, str]] = []

    for repo_name in watchlist.get("repos", []):
        if normalize_text(str(repo_name)) == normalize_text(repo_full_name):
            matches.append({"type": "repo", "value": repo_full_name})
    for org_name in watchlist.get("orgs", []):
        if normalize_text(str(org_name)) == normalize_text(repo_owner):
            matches.append({"type": "org", "value": repo_owner})
    for topic in watchlist.get("topics", []):
        normalized_topic = normalize_text(str(topic))
        if not normalized_topic:
            continue
        if normalized_topic in repo_topics or normalized_topic in text:
            matches.append({"type": "topic", "value": str(topic)})

    return [
        match
        for match in matches
        if str(match.get("value", "")).strip()
    ]


def objective_scores_for_story(items: List[Dict[str, Any]], reliability_score: int) -> Dict[str, float]:
    result: Dict[str, float] = {}
    reliability_bonus = max(0.0, (reliability_score - 60) / 40)
    support_bonus = min(1.0, max(0, len(items) - 1) * 0.35)
    for objective in OBJECTIVE_DISPLAY_ORDER:
        best_value = max(
            float((item.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0)
            for item in items
        )
        result[objective] = round(best_value + reliability_bonus + support_bonus, 2)
    return result


def item_type_label(category: str) -> str:
    return {
        "Repo": "repo",
        "News": "news",
        "Regulatory": "regulatory",
    }.get(category, normalize_text(category) or "signal")


def human_label_for_bucket(bucket_id: str, market_map: Dict[str, Any]) -> str:
    for bucket in market_map.get("buckets", []):
        if not isinstance(bucket, dict):
            continue
        if str(bucket.get("id", "") or "") == bucket_id:
            return str(bucket.get("label", bucket_id) or bucket_id)
    return bucket_id.replace("_", " ").title()


def normalize_item(
    item: Dict[str, Any],
    *,
    policies: Dict[str, Any],
    theses: Dict[str, Any],
    market_map: Dict[str, Any],
    watchlist: Dict[str, Any],
) -> Dict[str, Any]:
    reliability = reliability_for_item(item, policies)
    market_bucket_ids = market_buckets_for_item(item, market_map)
    thesis_links = thesis_links_for_item(item, theses)
    watchlist_matches = watchlist_matches_for_item(item, watchlist)
    summary = str(item.get("summary", "") or "").strip()
    why_it_matters = str(item.get("why_it_matters", "") or "").strip()
    materiality = classify_mapping_materiality(item)
    signal_quality = str(item.get("signal_quality") or materiality["signal_quality"])
    low_signal_announcement = (
        bool(item.get("low_signal_announcement"))
        if "low_signal_announcement" in item
        else bool(materiality["low_signal_announcement"])
    )
    material_operator_signal = (
        bool(item.get("material_operator_signal"))
        if "material_operator_signal" in item
        else bool(materiality["material_operator_signal"])
    )
    raw_excerpt = str(item.get("raw_text", "") or "").strip()[:240]
    signature = signature_tokens(
        " ".join(
            [
                str(item.get("title", "") or ""),
                str(item.get("topic_key", "") or ""),
                " ".join(str(value) for value in item.get("workflow_wedges", []) or []),
            ]
        )
    )

    normalized_item = {
        "item_id": str(item.get("item_key", "") or item.get("id", "") or item.get("url", "") or item.get("title", "")),
        "item_type": item_type_label(str(item.get("category", "") or "")),
        "category": str(item.get("category", "") or ""),
        "title": str(item.get("title", "") or ""),
        "canonical_url": str(item.get("url", "") or ""),
        "source_name": reliability["source_name"],
        "source_domain": reliability["source_domain"],
        "published_at": isoformat_or_empty(item.get("published_at")),
        "fetched_at": local_now().astimezone(timezone.utc).isoformat(),
        "summary": summary,
        "evidence": raw_excerpt,
        "entities": unique(
            [
                str(value).split(":", 1)[-1]
                for value in item.get("entity_keys", []) or []
                if str(value).strip()
            ]
        )[:8],
        "tags": unique(
            [
                *[str(value) for value in item.get("matched_themes", []) or []],
                *[str(value) for value in item.get("workflow_wedges", []) or []],
                *[str(value) for value in item.get("repo_topics", []) or []],
            ]
        )[:10],
        "market_bucket_ids": market_bucket_ids,
        "market_buckets": [
            human_label_for_bucket(bucket_id, market_map)
            for bucket_id in market_bucket_ids
        ],
        "cluster_id": "",
        "cluster_title": "",
        "duplicate_group_id": "",
        "novelty_score": round(
            (float(((item.get("score_dimensions", {}) or {}).get("novelty", 0.0) or 0.0) / 5.0) * 100),
            1,
        ),
        "reliability_score": reliability["score"],
        "reliability_label": reliability["label"],
        "reliability_reason": reliability["reason"],
        "objective_scores": {
            str(key): round(float(value or 0.0), 2)
            for key, value in (item.get("objective_scores", {}) or {}).items()
        },
        "score_dimensions": {
            str(key): round(float(value or 0.0), 2)
            for key, value in (item.get("score_dimensions", {}) or {}).items()
        },
        "priority_score": round(float(item.get("priority_score", 0.0) or 0.0), 2),
        "thesis_links": thesis_links,
        "watchlist_matches": watchlist_matches,
        "change_status": "new",
        "confidence": confidence_for_item(
            reliability_score=reliability["score"],
            signal=str(item.get("signal", "medium") or "medium"),
            signal_quality=signal_quality,
            material_operator_signal=material_operator_signal,
            low_signal_announcement=low_signal_announcement,
        ),
        "uncertainty": "Low" if reliability["score"] >= 85 else ("Medium" if reliability["score"] >= 60 else "High"),
        "why_it_matters": why_it_matters,
        "action_suggestion": "",
        "signal": str(item.get("signal", "medium") or "medium"),
        "matched_themes": [str(value) for value in item.get("matched_themes", []) or []],
        "workflow_wedges": [str(value) for value in item.get("workflow_wedges", []) or []],
        "operator_relevance": str(item.get("operator_relevance", "low") or "low"),
        "near_term_actionability": str(item.get("near_term_actionability", "low") or "low"),
        "is_generic_devtool": bool(item.get("is_generic_devtool")),
        "generic_repo_cap_exempt": bool(item.get("generic_repo_cap_exempt")),
        "signal_quality": signal_quality,
        "low_signal_announcement": low_signal_announcement,
        "soft_funding_or_challenge": bool(item.get("soft_funding_or_challenge"))
        if "soft_funding_or_challenge" in item
        else bool(materiality["soft_funding_or_challenge"]),
        "material_operator_signal": material_operator_signal,
        "materiality_signals": [
            str(value) for value in (item.get("materiality_signals") or materiality["materiality_signals"])
        ],
        "materiality_reason": str(item.get("materiality_reason") or materiality["materiality_reason"]),
        "selection_penalties": [str(value) for value in item.get("selection_penalties", []) or []],
        "signature_tokens": unique(signature)[:10],
        "_item": item,
    }
    normalized_item.update(confidence_display_for_story(normalized_item))
    return normalized_item


def cleaned_entities(item: Dict[str, Any]) -> set[str]:
    values = set()
    for entity in item.get("entities", []) or []:
        normalized = normalize_text(str(entity))
        if normalized:
            values.add(normalized)
    return values


def overlap_score(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    if a["canonical_url"] and a["canonical_url"] == b["canonical_url"]:
        return 1.0
    if a["item_type"] == "repo" and normalize_text(a["title"]) == normalize_text(b["title"]):
        return 1.0

    tokens_a = set(a.get("signature_tokens", []) or signature_tokens(a["title"]))
    tokens_b = set(b.get("signature_tokens", []) or signature_tokens(b["title"]))
    token_overlap = 0.0
    if tokens_a and tokens_b:
        token_overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    market_overlap = bool(set(a.get("market_bucket_ids", [])) & set(b.get("market_bucket_ids", [])))
    workflow_overlap = bool(set(a.get("workflow_wedges", [])) & set(b.get("workflow_wedges", [])))
    thesis_overlap = bool(
        {link["thesis_id"] for link in a.get("thesis_links", [])}
        & {link["thesis_id"] for link in b.get("thesis_links", [])}
    )
    entity_overlap = bool(cleaned_entities(a) & cleaned_entities(b))
    topic_overlap = normalize_text(str(a.get("_item", {}).get("topic_key", "") or "")) and normalize_text(
        str(a.get("_item", {}).get("topic_key", "") or "")
    ) == normalize_text(str(b.get("_item", {}).get("topic_key", "") or ""))

    score = token_overlap * 0.6
    if market_overlap:
        score += 0.12
    if workflow_overlap:
        score += 0.14
    if thesis_overlap:
        score += 0.08
    if entity_overlap:
        score += 0.08
    if topic_overlap:
        score += 0.12
    if a["item_type"] == b["item_type"]:
        score += 0.05
    return min(score, 1.0)


def should_merge(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if a["item_type"] != b["item_type"] and ("repo" in {a["item_type"], b["item_type"]}):
        return False
    score = overlap_score(a, b)
    if score >= 0.64:
        return True
    if score >= 0.5 and (
        bool(set(a.get("workflow_wedges", [])) & set(b.get("workflow_wedges", [])))
        or bool(set(a.get("market_bucket_ids", [])) & set(b.get("market_bucket_ids", [])))
    ):
        return True
    return False


def choose_lead_item(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return sorted(
        items,
        key=lambda item: (
            float(item.get("priority_score", 0.0) or 0.0) + (int(item.get("reliability_score", 0) or 0) / 20.0),
            item.get("signal", "medium") == "high",
            item.get("published_at", ""),
            item.get("title", ""),
        ),
        reverse=True,
    )[0]


def derive_cluster_title(
    items: List[Dict[str, Any]],
    lead_item: Dict[str, Any],
    market_map: Dict[str, Any],
) -> str:
    if len(items) == 1:
        return str(lead_item.get("title", "") or "Untitled story")

    top_tokens = [
        token
        for token, count in Counter(
            token
            for item in items
            for token in item.get("signature_tokens", [])[:5]
            if token not in STOPWORDS
        ).most_common(3)
        if count >= 2
    ]
    workflow_counter = Counter(
        str(value)
        for item in items
        for value in item.get("workflow_wedges", []) or []
        if str(value).strip()
    )
    if workflow_counter:
        workflow_label = workflow_counter.most_common(1)[0][0]
        workflow_tokens = set(signature_tokens(workflow_label))
        specific_tokens = [token for token in top_tokens if token not in workflow_tokens]
        if specific_tokens:
            token_label = " ".join(token.title() for token in specific_tokens[:2])
            return f"{token_label} / {workflow_label.title()}"
        return str(lead_item.get("title", "") or f"{workflow_label.title()} cluster")

    bucket_counter = Counter(
        bucket_id
        for item in items
        for bucket_id in item.get("market_bucket_ids", []) or []
        if str(bucket_id).strip()
    )
    if bucket_counter:
        label = human_label_for_bucket(bucket_counter.most_common(1)[0][0], market_map)
        if top_tokens:
            return f"{' '.join(token.title() for token in top_tokens[:2])} / {label}"
        return label

    return str(lead_item.get("title", "") or "Untitled story")


def story_identifier(
    cluster_title: str,
    items: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    token_counter = Counter(
        token
        for item in items
        for token in item.get("signature_tokens", [])
        if token not in STOPWORDS
    )
    signature = [
        token
        for token, _count in token_counter.most_common(5)
    ] or signature_tokens(cluster_title)[:5]
    base = "-".join(signature[:4]) or slugify(cluster_title)
    return f"story::{base}", signature[:5]


def story_signal(story_score: float, lead_signal: str) -> str:
    if story_score >= 19 or lead_signal == "high":
        return "high"
    if story_score >= 12:
        return "medium"
    return "low"


SIGNAL_QUALITY_RANK = {"weak": 0, "medium": 1, "strong": 2}


def strongest_signal_quality(items: List[Dict[str, Any]]) -> str:
    return max(
        (str(item.get("signal_quality", "medium") or "medium").lower() for item in items),
        key=lambda quality: SIGNAL_QUALITY_RANK.get(quality, 1),
        default="medium",
    )


def story_low_signal_announcement(story: Dict[str, Any]) -> bool:
    if "low_signal_announcement" in story:
        return bool(story.get("low_signal_announcement"))
    return bool(classify_mapping_materiality(story)["low_signal_announcement"])


def story_material_operator_signal(story: Dict[str, Any]) -> bool:
    if "material_operator_signal" in story:
        return bool(story.get("material_operator_signal"))
    return bool(classify_mapping_materiality(story)["material_operator_signal"])


def story_signal_quality_label(story: Dict[str, Any]) -> str:
    explicit = str(story.get("signal_quality", "") or "").lower()
    if explicit in SIGNAL_QUALITY_RANK:
        return explicit
    return str(classify_mapping_materiality(story)["signal_quality"])


def build_story_why_it_matters(story: Dict[str, Any]) -> str:
    lead_item = story["_lead_item"]
    source_confidence = str(story.get("confidence", "Medium") or "Medium").lower()
    guidance = workflow_guidance_for_item(lead_item["_item"])
    actions = workflow_actions_for_item(lead_item["_item"])
    workflow_name = guidance["workflow"]
    item_type = lead_item["item_type"]

    if story_low_signal_announcement(story):
        return (
            "Treat this as watchlist context, not a workflow trigger; revisit only if follow-on evidence shows "
            f"deployment, policy, reimbursement, or measurable operator impact. Confidence is {source_confidence}."
        )

    if lead_item.get("is_generic_devtool") and not lead_item.get("generic_repo_cap_exempt"):
        return (
            f"This is more useful for governed {workflow_name} prototyping than for immediate production ROI; "
            f"treat it as a tooling signal until it proves integration, controls, and measurable workflow lift."
        )

    if item_type == "regulatory":
        return (
            f"{sentence_start(actions['actors'])} should map this to active {workflow_name} backlog work in the next 30 days; "
            f"the concrete job is to {actions['regulatory_action']}. Confidence is {source_confidence}."
        )

    if item_type == "repo":
        repo_action = actions["repo_action"]
        audit_tail = "" if "audit trail" in repo_action.lower() else " with an audit trail"
        return (
            f"Builders working on {workflow_name} should test whether this can {repo_action}{audit_tail} in the next sprint; "
            f"confidence is {source_confidence}."
        )

    if lead_item.get("reliability_score", 0) < 60:
        return (
            f"{sentence_start(actions['actors'])} should add this to the {workflow_name} watchlist but not move roadmap time yet; "
            f"the current evidence is {source_confidence} and still needs primary confirmation."
        )

    return (
        f"{sentence_start(actions['actors'])} should use the next backlog review to {actions['news_action']} in {workflow_name}; "
        f"confidence is {source_confidence}."
    )


def build_story_action(story: Dict[str, Any]) -> str:
    lead_item = story["_lead_item"]
    guidance = workflow_guidance_for_item(lead_item["_item"])
    actions = workflow_actions_for_item(lead_item["_item"])

    if story_low_signal_announcement(story):
        return "Do not move roadmap time without concrete deployment, policy, reimbursement, or workflow evidence."
    if lead_item.get("is_generic_devtool") and not lead_item.get("generic_repo_cap_exempt"):
        return "Pressure-test it on one governed workflow before assigning production roadmap weight."
    if lead_item["item_type"] == "regulatory":
        return f"Audit backlog, trading-partner, and control gaps in {guidance['workflow']} this week."
    if lead_item["item_type"] == "repo":
        return f"Prototype it against one live {guidance['workflow']} queue and measure handoff reduction, auditability, and integration effort."
    return f"Review whether this changes workflow throughput, handoffs, or integration burden in {guidance['workflow']} before moving roadmap time."


def build_stories(
    normalized_items: List[Dict[str, Any]],
    *,
    market_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    clusters: List[List[Dict[str, Any]]] = []

    for item in sorted(
        normalized_items,
        key=lambda candidate: (
            float(candidate.get("priority_score", 0.0) or 0.0),
            int(candidate.get("reliability_score", 0) or 0),
            candidate.get("published_at", ""),
        ),
        reverse=True,
    ):
        attached = False
        for cluster in clusters:
            if any(should_merge(item, existing) for existing in cluster):
                cluster.append(item)
                attached = True
                break
        if not attached:
            clusters.append([item])

    stories: List[Dict[str, Any]] = []
    for cluster in clusters:
        lead_item = choose_lead_item(cluster)
        cluster_title = derive_cluster_title(cluster, lead_item, market_map)
        story_id, story_signature = story_identifier(cluster_title, cluster)
        reliability_score = max(int(item.get("reliability_score", 0) or 0) for item in cluster)
        objective_scores = objective_scores_for_story(cluster, reliability_score)
        support_count = len(cluster)
        cluster_material_signal = any(bool(item.get("material_operator_signal")) for item in cluster)
        cluster_signal_quality = "strong" if cluster_material_signal else strongest_signal_quality(cluster)
        cluster_low_signal_announcement = bool(lead_item.get("low_signal_announcement")) and not cluster_material_signal
        cluster_soft_funding_or_challenge = any(bool(item.get("soft_funding_or_challenge")) for item in cluster)
        cluster_materiality_signals = unique(
            str(signal)
            for item in cluster
            for signal in (item.get("materiality_signals") or [])
            if str(signal).strip()
        )
        cluster_selection_penalties = unique(
            str(penalty)
            for item in cluster
            for penalty in (item.get("selection_penalties") or [])
            if str(penalty).strip()
        )
        thesis_links = unique(
            [
                json.dumps(
                    {
                        "thesis_id": link.get("thesis_id", ""),
                        "title": link.get("title", ""),
                        "relation": link.get("relation", ""),
                    },
                    sort_keys=True,
                )
                for item in cluster
                for link in item.get("thesis_links", [])
            ]
        )
        story_thesis_links = [json.loads(value) for value in thesis_links]
        watchlist_matches = unique(
            [
                json.dumps(match, sort_keys=True)
                for item in cluster
                for match in item.get("watchlist_matches", [])
            ]
        )
        story_watchlist_matches = [json.loads(value) for value in watchlist_matches]
        repo_name = normalize_text(str(lead_item.get("_item", {}).get("repo_name", "") or ""))
        raw_repo_text = normalize_text(str(lead_item.get("_item", {}).get("raw_text", "") or ""))
        docs_only_repo = bool(
            lead_item["item_type"] == "repo"
            and (
                repo_name in {"docs", "documentation"}
                or "product documentation" in raw_repo_text
                or "documentation for" in raw_repo_text
            )
            and not story_watchlist_matches
        )
        story_score = round(
            max(float(item.get("priority_score", 0.0) or 0.0) for item in cluster)
            + max(0, support_count - 1) * 2.8
            + max(0.0, (reliability_score - 60) / 10.0)
            + (1.3 * len([link for link in story_thesis_links if link.get("relation") == "supports"]))
            + (1.2 * len(story_watchlist_matches))
            - (3.0 if lead_item.get("is_generic_devtool") and not lead_item.get("generic_repo_cap_exempt") else 0.0),
            2,
        )
        if cluster_low_signal_announcement:
            cluster_selection_penalties = unique(
                [
                    *cluster_selection_penalties,
                    "story_score_demoted_for_soft_announcement",
                    "confidence_capped_by_materiality",
                ]
            )
            story_score = round(
                max(
                    0.0,
                    story_score - (10.0 if cluster_soft_funding_or_challenge else 7.0),
                ),
                2,
            )
        if docs_only_repo:
            story_score = round(max(0.0, story_score - 8.0), 2)
        story = {
            "story_id": story_id,
            "cluster_id": story_id,
            "duplicate_group_id": story_id,
            "cluster_title": cluster_title,
            "title": cluster_title,
            "category": lead_item.get("category", ""),
            "item_type": lead_item["item_type"],
            "canonical_url": lead_item["canonical_url"],
            "url": lead_item["canonical_url"],
            "source": lead_item["source_name"],
            "topic_key": str(lead_item.get("_item", {}).get("topic_key", "") or ""),
            "source_names": unique(item["source_name"] for item in cluster),
            "source_domains": unique(item["source_domain"] for item in cluster),
            "supporting_item_ids": [item["item_id"] for item in cluster],
            "supporting_items": [
                {
                    "item_id": item["item_id"],
                    "title": item["title"],
                    "item_type": item["item_type"],
                    "source_name": item["source_name"],
                    "source_domain": item["source_domain"],
                    "canonical_url": item["canonical_url"],
                    "reliability_label": item["reliability_label"],
                    "signal": item["signal"],
                }
                for item in cluster
            ],
            "supporting_item_count": support_count,
            "summary": str(lead_item.get("summary", "") or ""),
            "evidence": str(lead_item.get("evidence", "") or ""),
            "why_it_matters": str(lead_item.get("why_it_matters", "") or ""),
            "action_suggestion": "",
            "market_bucket_ids": unique(
                bucket_id
                for item in cluster
                for bucket_id in item.get("market_bucket_ids", [])
            ),
            "market_buckets": unique(
                label
                for item in cluster
                for label in item.get("market_buckets", [])
            ),
            "novelty_score": round(
                max(float(item.get("novelty_score", 0.0) or 0.0) for item in cluster),
                1,
            ),
            "reliability_score": reliability_score,
            "reliability_label": label_for_reliability_score(reliability_score),
            "reliability_reason": max(cluster, key=lambda item: int(item.get("reliability_score", 0) or 0)).get("reliability_reason", ""),
            "objective_scores": objective_scores,
            "thesis_links": story_thesis_links,
            "watchlist_matches": story_watchlist_matches,
            "change_status": "new",
            "confidence": confidence_for_item(
                reliability_score=reliability_score,
                signal=str(lead_item.get("signal", "medium") or "medium"),
                support_count=support_count,
                signal_quality=cluster_signal_quality,
                material_operator_signal=cluster_material_signal,
                low_signal_announcement=cluster_low_signal_announcement,
            ),
            "uncertainty": "Low" if reliability_score >= 85 else ("Medium" if reliability_score >= 60 else "High"),
            "story_score": story_score,
            "priority_score": story_score,
            "signal": story_signal(story_score, str(lead_item.get("signal", "medium") or "medium")),
            "matched_themes": unique(
                value
                for item in cluster
                for value in item.get("matched_themes", [])
            ),
            "workflow_wedges": unique(
                value
                for item in cluster
                for value in item.get("workflow_wedges", [])
            ),
            "operator_relevance": lead_item.get("operator_relevance", "low"),
            "near_term_actionability": lead_item.get("near_term_actionability", "low"),
            "is_generic_devtool": bool(lead_item.get("is_generic_devtool")),
            "generic_repo_cap_exempt": bool(lead_item.get("generic_repo_cap_exempt")),
            "signal_quality": cluster_signal_quality,
            "low_signal_announcement": cluster_low_signal_announcement,
            "soft_funding_or_challenge": cluster_soft_funding_or_challenge,
            "material_operator_signal": cluster_material_signal,
            "materiality_signals": cluster_materiality_signals,
            "materiality_reason": (
                "soft announcement without concrete operator materiality"
                if cluster_low_signal_announcement
                else str(lead_item.get("materiality_reason", "") or "")
            ),
            "selection_penalties": cluster_selection_penalties,
            "docs_only_repo": docs_only_repo,
            "signature_tokens": story_signature,
            "_lead_item": lead_item,
            "_items": cluster,
        }
        story.update(confidence_display_for_story(story))
        if cluster_low_signal_announcement:
            for objective in OBJECTIVE_DISPLAY_ORDER:
                story["objective_scores"][objective] = round(
                    max(0.0, float(story["objective_scores"].get(objective, 0.0) or 0.0) - 1.8),
                    2,
                )
        if docs_only_repo:
            for objective in ("career", "build", "content"):
                story["objective_scores"][objective] = round(
                    max(0.0, float(story["objective_scores"].get(objective, 0.0) or 0.0) - 1.6),
                    2,
                )
        if not why_it_matters_is_specific(story["why_it_matters"]) or support_count > 1:
            story["why_it_matters"] = build_story_why_it_matters(story)
        story["action_suggestion"] = build_story_action(story)
        stories.append(story)

    return sorted(
        stories,
        key=lambda story: (
            float(story.get("story_score", 0.0) or 0.0),
            int(story.get("reliability_score", 0) or 0),
            story.get("cluster_title", ""),
        ),
        reverse=True,
    )


def previous_story_match(current_story: Dict[str, Any], previous_brief: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not previous_brief:
        return None

    previous_stories = [
        story
        for story in previous_brief.get("stories", [])
        if isinstance(story, dict)
    ]
    by_id = {
        str(story.get("story_id", "") or ""): story
        for story in previous_stories
        if str(story.get("story_id", "") or "").strip()
    }
    if current_story["story_id"] in by_id:
        return by_id[current_story["story_id"]]

    current_tokens = set(current_story.get("signature_tokens", []))
    current_markets = {str(value).strip() for value in current_story.get("market_bucket_ids", []) if str(value).strip()}
    current_sources = {str(value).strip() for value in current_story.get("source_domains", []) if str(value).strip()}
    current_theses = {
        str(link.get("thesis_id", "") or "").strip()
        for link in current_story.get("thesis_links", [])
        if isinstance(link, dict) and str(link.get("thesis_id", "") or "").strip()
    }
    best_match = None
    best_score = 0.0
    for story in previous_stories:
        previous_tokens = {
            str(value).strip()
            for value in story.get("signature_tokens", [])
            if str(value).strip()
        }
        token_overlap = 0.0
        if current_tokens and previous_tokens:
            token_overlap = len(current_tokens & previous_tokens) / len(current_tokens | previous_tokens)
        previous_markets = {
            str(value).strip()
            for value in story.get("market_bucket_ids", [])
            if str(value).strip()
        }
        previous_sources = {
            str(value).strip()
            for value in story.get("source_domains", [])
            if str(value).strip()
        }
        previous_theses = {
            str(link.get("thesis_id", "") or "").strip()
            for link in story.get("thesis_links", [])
            if isinstance(link, dict) and str(link.get("thesis_id", "") or "").strip()
        }
        overlap = token_overlap * 0.55
        if current_markets & previous_markets:
            overlap += 0.18
        if current_sources & previous_sources:
            overlap += 0.14
        if current_theses & previous_theses:
            overlap += 0.18
        if overlap > best_score:
            best_score = overlap
            best_match = story
    if best_score >= 0.42:
        return best_match
    return None


def apply_change_status(
    stories: List[Dict[str, Any]],
    *,
    previous_brief: Dict[str, Any] | None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    today_story_ids = {story["story_id"] for story in stories}
    change_entries: List[Dict[str, Any]] = []

    for story in stories:
        previous_story = previous_story_match(story, previous_brief)
        if previous_story is None:
            story["change_status"] = "new"
            change_entries.append(
                {
                    "change_type": "New",
                    "story_id": story["story_id"],
                    "headline": story["cluster_title"],
                    "detail": f"{story['cluster_title']} surfaced today with {story['reliability_label'].lower()}-reliability evidence from {len(story['source_domains'])} source(s).",
                    "weight": story["story_score"],
                }
            )
            continue

        previous_support = int(previous_story.get("supporting_item_count", 0) or 0)
        previous_score = float(previous_story.get("story_score", 0.0) or 0.0)
        previous_domains = {
            str(value).strip()
            for value in previous_story.get("source_domains", [])
            if str(value).strip()
        }
        new_domains = [
            domain
            for domain in story.get("source_domains", [])
            if domain not in previous_domains
        ]

        if int(story["supporting_item_count"]) > previous_support or story["story_score"] >= previous_score + 3.0:
            story["change_status"] = "escalating"
            change_entries.append(
                {
                    "change_type": "Escalating",
                    "story_id": story["story_id"],
                    "headline": story["cluster_title"],
                    "detail": f"{story['cluster_title']} now appears across {story['supporting_item_count']} items and {len(story['source_domains'])} sources.",
                    "weight": story["story_score"],
                }
            )
        elif new_domains and story["reliability_score"] >= int(previous_story.get("reliability_score", 0) or 0):
            story["change_status"] = "repeated_stronger"
            change_entries.append(
                {
                    "change_type": "Repeated but stronger",
                    "story_id": story["story_id"],
                    "headline": story["cluster_title"],
                    "detail": f"{story['cluster_title']} repeated, but today adds stronger source support from {len(new_domains)} new domain(s).",
                    "weight": story["story_score"],
                }
            )
        elif story["story_score"] <= previous_score - 3.0:
            story["change_status"] = "fading"
        else:
            story["change_status"] = "repeated"

    if previous_brief:
        for previous_story in previous_brief.get("stories", []):
            if not isinstance(previous_story, dict):
                continue
            previous_story_id = str(previous_story.get("story_id", "") or "")
            if not previous_story_id or previous_story_id in today_story_ids:
                continue
            previous_score = float(previous_story.get("story_score", 0.0) or 0.0)
            if previous_score < 10:
                continue
            previous_title = str(previous_story.get("cluster_title", "") or "Yesterday's story")
            change_entries.append(
                {
                    "change_type": "Fading",
                    "story_id": previous_story_id,
                    "headline": str(previous_story.get("cluster_title", "") or "Prior story"),
                    "detail": f"{previous_title} did not pick up fresh evidence today.",
                    "weight": previous_score - 2.5,
                }
            )

    change_entries = sorted(
        change_entries,
        key=lambda entry: (float(entry.get("weight", 0.0) or 0.0), entry.get("headline", "")),
        reverse=True,
    )
    return stories, change_entries[:6]


def select_story_cards(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    per_category_cap = {"Repo": 2, "News": 3, "Regulatory": 2}
    category_counts = Counter()

    for category in ("Regulatory", "News", "Repo"):
        candidate = next(
            (
                story
                for story in stories
                if story.get("category") == category
                and story_is_surface_worthy(story)
                and category_counts[category] < per_category_cap.get(category, OPERATOR_STORY_LIMIT)
            ),
            None,
        )
        if candidate:
            selected.append(candidate)
            category_counts[category] += 1

    for story in stories:
        if story in selected:
            continue
        if not story_is_surface_worthy(story):
            continue
        category = str(story.get("category", "") or "")
        if category_counts[category] >= per_category_cap.get(category, OPERATOR_STORY_LIMIT):
            continue
        selected.append(story)
        category_counts[category] += 1
        if len(selected) >= OPERATOR_STORY_LIMIT:
            break

    return selected[:OPERATOR_STORY_LIMIT]


def build_story_top_picks(stories: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    picks: Dict[str, Dict[str, Any]] = {}
    used_story_ids: set[str] = set()

    for objective in OBJECTIVE_DISPLAY_ORDER:
        ranked = sorted(
            stories,
            key=lambda story: (
                float((story.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
                float(story.get("story_score", 0.0) or 0.0),
                int(story.get("reliability_score", 0) or 0),
            ),
            reverse=True,
        )
        if objective == "regulatory":
            ranked = [story for story in ranked if story.get("category") == "Regulatory"]

        best = ranked[0] if ranked else None
        if not best or float((best.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0) < OBJECTIVE_MIN_SCORES[objective]:
            picks[objective] = {
                "objective": objective,
                "label": OBJECTIVE_LABELS[objective],
                "item": None,
                "score": 0.0,
                "message": OBJECTIVE_EMPTY_MESSAGES[objective],
                "empty": True,
                "reused": False,
                "reuse_reason": "",
            }
            continue

        choice = best
        if choice["story_id"] in used_story_ids:
            alternative = next(
                (
                    story
                    for story in ranked[1:]
                    if story["story_id"] not in used_story_ids
                    and float((story.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0)
                    >= OBJECTIVE_MIN_SCORES[objective]
                    and float((choice.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0)
                    - float((story.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0)
                    <= 1.5
                ),
                None,
            )
            if alternative is not None:
                choice = alternative

        reused = choice["story_id"] in used_story_ids
        if not reused:
            used_story_ids.add(choice["story_id"])

        picks[objective] = {
            "objective": objective,
            "label": OBJECTIVE_LABELS[objective],
            "item": {
                "title": choice["cluster_title"],
                "url": choice["canonical_url"],
                "story_id": choice["story_id"],
                "change_status": choice["change_status"],
                "reliability_label": choice["reliability_label"],
            },
            "score": float((choice.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
            "message": "",
            "empty": False,
            "reused": reused,
            "reuse_reason": (
                "Reused because it still beat the next-best alternative by a clear margin."
                if reused
                else ""
            ),
        }

    return picks


def build_market_map(
    stories: List[Dict[str, Any]],
    *,
    market_map: Dict[str, Any],
    previous_brief: Dict[str, Any] | None,
) -> Dict[str, Any]:
    current_intensity: Dict[str, float] = defaultdict(float)
    previous_intensity: Dict[str, float] = defaultdict(float)

    for story in stories:
        weight = float(story.get("story_score", 0.0) or 0.0) * (int(story.get("reliability_score", 0) or 0) / 100.0)
        for bucket_id in story.get("market_bucket_ids", []):
            current_intensity[bucket_id] += weight

    if previous_brief:
        for story in previous_brief.get("stories", []):
            if not isinstance(story, dict):
                continue
            weight = float(story.get("story_score", 0.0) or 0.0) * (
                1.0 if str(story.get("reliability_label", "") or "").lower() == "high" else 0.75
            )
            for bucket_id in story.get("market_bucket_ids", []):
                if str(bucket_id).strip():
                    previous_intensity[str(bucket_id).strip()] += weight

    pulse = []
    for bucket_id, intensity in sorted(current_intensity.items(), key=lambda entry: (-entry[1], entry[0])):
        previous_value = previous_intensity.get(bucket_id, 0.0)
        pulse.append(
            {
                "bucket_id": bucket_id,
                "label": human_label_for_bucket(bucket_id, market_map),
                "intensity": round(intensity, 2),
                "delta_vs_yesterday": round(intensity - previous_value, 2),
            }
        )

    hot_zones = [entry for entry in pulse if entry["delta_vs_yesterday"] > 0][:3]
    quiet_zones = [
        {
            "bucket_id": bucket_id,
            "label": human_label_for_bucket(bucket_id, market_map),
            "intensity": round(current_intensity.get(bucket_id, 0.0), 2),
            "delta_vs_yesterday": round(current_intensity.get(bucket_id, 0.0) - previous_value, 2),
        }
        for bucket_id, previous_value in sorted(previous_intensity.items(), key=lambda entry: entry[1], reverse=True)
        if current_intensity.get(bucket_id, 0.0) < previous_value
    ][:3]
    spillover = [
        {
            "story_id": story["story_id"],
            "cluster_title": story["cluster_title"],
            "market_buckets": story["market_buckets"],
        }
        for story in stories
        if len(story.get("market_bucket_ids", [])) > 1
    ][:3]

    return {
        "pulse": pulse,
        "hot_zones": hot_zones,
        "quiet_zones": quiet_zones,
        "spillover": spillover,
    }


def build_thesis_tracker(
    stories: List[Dict[str, Any]],
    *,
    theses: Dict[str, Any],
    previous_brief: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    previous_status = {}
    if previous_brief:
        previous_status = {
            str(entry.get("thesis_id", "") or ""): entry
            for entry in previous_brief.get("thesis_tracker", [])
            if isinstance(entry, dict) and str(entry.get("thesis_id", "") or "").strip()
        }

    entries: List[Dict[str, Any]] = []
    for thesis in theses.get("theses", []):
        if not isinstance(thesis, dict):
            continue
        thesis_id = str(thesis.get("id", "") or "").strip()
        relevant_stories = []
        relation_counts = Counter()
        for story in stories:
            matches = [
                link
                for link in story.get("thesis_links", [])
                if str(link.get("thesis_id", "") or "") == thesis_id
            ]
            if not matches:
                continue
            relation = matches[0].get("relation", "adjacent")
            relation_counts[relation] += 1
            relevant_stories.append(
                {
                    "story_id": story["story_id"],
                    "cluster_title": story["cluster_title"],
                    "relation": relation,
                }
            )

        if not relevant_stories:
            continue

        previous_entry = previous_status.get(thesis_id, {})
        previous_supports = int((previous_entry.get("relation_counts", {}) or {}).get("supports", 0) or 0)
        supports = relation_counts.get("supports", 0)
        weakens = relation_counts.get("weakens", 0)
        complicates = relation_counts.get("complicates", 0)
        if supports > previous_supports and supports >= weakens:
            status = "strengthening"
        elif weakens > 0:
            status = "weakening"
        elif complicates > 0:
            status = "mixed"
        else:
            status = "active"

        entries.append(
            {
                "thesis_id": thesis_id,
                "title": str(thesis.get("title", "") or ""),
                "status": status,
                "relation_counts": dict(relation_counts),
                "evidence": relevant_stories[:3],
            }
        )

    return entries


def build_watchlist_hits(
    stories: List[Dict[str, Any]],
    *,
    previous_brief: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    previous_ids = {
        str(entry.get("story_id", "") or "")
        for entry in (previous_brief or {}).get("watchlist_hits", [])
        if isinstance(entry, dict)
    }

    hits = []
    for story in stories:
        if not any(item.get("item_type") == "repo" for item in story.get("supporting_items", [])):
            continue
        if not story.get("watchlist_matches"):
            continue
        hits.append(
            {
                "story_id": story["story_id"],
                "cluster_title": story["cluster_title"],
                "status": "sustained" if story["story_id"] in previous_ids else "new",
                "matches": story["watchlist_matches"],
                "change_status": story["change_status"],
            }
        )

    return hits[:WATCHLIST_STORY_LIMIT]


def max_story_objective_score(story: Dict[str, Any]) -> float:
    return float(max((story.get("objective_scores", {}) or {}).values(), default=0.0) or 0.0)


def story_is_recall_enforcement(story: Dict[str, Any]) -> bool:
    return (
        str(story.get("category", "") or "") == "Regulatory"
        and str(story.get("topic_key", "") or "").strip().lower() == RECALL_ENFORCEMENT_TOPIC_KEY
    )


def recall_enforcement_has_primary_slot_signal(story: Dict[str, Any]) -> bool:
    operator_relevance = str(story.get("operator_relevance", "low") or "low")
    workflow_wedges = [str(value) for value in story.get("workflow_wedges", []) or []]
    matched_themes = {str(value) for value in story.get("matched_themes", []) or []}
    support_count = int(story.get("supporting_item_count", 0) or 0)

    return (
        operator_relevance in {"high", "medium"}
        or bool(workflow_wedges)
        or support_count >= 2
        or bool(story.get("watchlist_matches"))
        or bool(matched_themes & TARGET_THEME_KEYS)
    )


def story_has_target_fit(story: Dict[str, Any]) -> bool:
    category = str(story.get("category", "") or "")
    operator_relevance = str(story.get("operator_relevance", "low") or "low")
    actionability = str(story.get("near_term_actionability", "low") or "low")
    workflow_wedges = [str(value) for value in story.get("workflow_wedges", []) or []]
    matched_themes = {str(value) for value in story.get("matched_themes", []) or []}
    has_watchlist_match = bool(story.get("watchlist_matches"))

    if bool(story.get("docs_only_repo")):
        return False
    if story_low_signal_announcement(story) or story_signal_quality_label(story) == "weak":
        return False

    if category == "Regulatory":
        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        return (
            regulatory_score >= OBJECTIVE_MIN_SCORES["regulatory"]
            or bool(workflow_wedges)
            or operator_relevance in {"high", "medium"}
        )

    if category == "Repo":
        if bool(story.get("is_generic_devtool")) and not bool(story.get("generic_repo_cap_exempt")):
            return has_watchlist_match or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_story_objective_score(story) >= 7.2
                and actionability != "low"
            )
        return (
            has_watchlist_match
            or bool(workflow_wedges)
            or operator_relevance == "high"
            or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_story_objective_score(story) >= STORY_STRONG_OBJECTIVE_SCORE
                and actionability != "low"
            )
        )

    if category == "News":
        return (
            operator_relevance in {"high", "medium"}
            and (
                bool(workflow_wedges)
                or actionability in {"high", "medium"}
                or bool(matched_themes & TARGET_THEME_KEYS)
            )
        )

    return False


def story_surface_worthiness(story: Dict[str, Any]) -> Tuple[bool, str]:
    if story_low_signal_announcement(story):
        return False, "soft announcement lacks concrete operator materiality."
    if story_signal_quality_label(story) == "weak":
        return False, "story signal quality is weak."
    if not story_has_target_fit(story):
        return False, "target-fit check failed."
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return False, "reliability is low without corroborating support."

    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    actionability = str(story.get("near_term_actionability", "low") or "low")
    support_count = int(story.get("supporting_item_count", 0) or 0)

    if story.get("category") == "Regulatory":
        if story_is_recall_enforcement(story) and not recall_enforcement_has_primary_slot_signal(story):
            return False, "recall/enforcement story lacks a stronger primary-slot usefulness signal."

        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        if story_score >= 18.0:
            return True, "regulatory story score threshold passed."
        if regulatory_score >= OBJECTIVE_MIN_SCORES["regulatory"]:
            return True, "regulatory objective threshold passed."
        if support_count >= 2:
            return True, "regulatory story has corroborating support."
        return False, "regulatory story score/objective/support thresholds were not strong enough."

    if story_score >= STORY_STRONG_SCORE:
        return True, "story score threshold passed."
    if max_objective >= STORY_STRONG_OBJECTIVE_SCORE and actionability != "low":
        return True, "strong objective threshold passed."
    if support_count >= 2 and actionability in {"high", "medium"}:
        return True, "story has corroborating support and actionability."
    return False, "story score/objective thresholds were not strong enough."


def story_surface_worthiness_reason(story: Dict[str, Any]) -> str:
    return story_surface_worthiness(story)[1]


def story_is_surface_worthy(story: Dict[str, Any]) -> bool:
    return story_surface_worthiness(story)[0]


def compact_one_line(value: object, *, max_length: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""

    sentence_match = re.search(r"^(.+?[.!?])(?:\s|$)", text)
    line = sentence_match.group(1).strip() if sentence_match else text
    if len(line) > max_length:
        trimmed = line[: max_length - 1].rsplit(" ", 1)[0].strip()
        line = f"{trimmed}." if trimmed else line[:max_length].strip()
    if line and line[-1] not in ".!?":
        line = f"{line}."
    return line


def near_miss_summary_is_clean(value: str) -> bool:
    normalized = normalize_text(value)
    if len(normalized.split()) < 5:
        return False
    if any(phrase in normalized for phrase in NEAR_MISS_BLOCKED_SUMMARY_PHRASES):
        return False
    if " should " in f" {normalized} ":
        return False
    return True


def near_miss_summary_for_story(story: Dict[str, Any]) -> str:
    lead_item = story.get("_lead_item", {}) if isinstance(story.get("_lead_item"), dict) else {}
    raw_item = lead_item.get("_item", {}) if isinstance(lead_item.get("_item"), dict) else {}
    candidates = [
        story.get("summary", ""),
        lead_item.get("summary", ""),
        raw_item.get("summary", ""),
        story.get("evidence", ""),
        raw_item.get("raw_text", ""),
    ]
    for candidate in candidates:
        line = compact_one_line(candidate)
        if line and near_miss_summary_is_clean(line):
            return line
    return ""


def near_miss_reason_for_story(story: Dict[str, Any], rejection_reason: str) -> str:
    reason = str(rejection_reason or "").lower()
    if "regulatory story score" in reason:
        return "regulatory usefulness stayed below the operator-grade threshold"
    if "recall/enforcement" in reason:
        return "the recall/enforcement angle lacked a stronger workflow signal"
    if "score/objective" in reason or "threshold" in reason:
        return "score and objective evidence stayed below the operator-grade threshold"
    if "corroborating support" in reason:
        return "source support was too thin"
    if "target-fit" in reason:
        return "operator fit was too indirect"
    return "evidence was not strong enough for the main digest"


def story_has_near_miss_floor(story: Dict[str, Any]) -> bool:
    if story_low_signal_announcement(story):
        return False
    if story_signal_quality_label(story) == "weak":
        return False
    if not story_has_target_fit(story):
        return False
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return False

    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    support_count = int(story.get("supporting_item_count", 0) or 0)
    actionability = str(story.get("near_term_actionability", "low") or "low")

    if story.get("category") == "Regulatory":
        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        return (
            story_score >= 12.0
            or regulatory_score >= NEAR_MISS_MIN_REGULATORY_OBJECTIVE_SCORE
            or support_count >= 2
        )

    return (
        story_score >= NEAR_MISS_MIN_STORY_SCORE
        or max_objective >= NEAR_MISS_MIN_OBJECTIVE_SCORE
        or (support_count >= 2 and actionability in {"high", "medium"})
    )


def near_miss_rank(story: Dict[str, Any]) -> Tuple[float, float, int, int, str]:
    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    support_count = int(story.get("supporting_item_count", 0) or 0)
    reliability_score = int(story.get("reliability_score", 0) or 0)
    if story.get("category") == "Regulatory":
        score_ratio = story_score / 18.0
        objective_ratio = (
            float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
            / OBJECTIVE_MIN_SCORES["regulatory"]
        )
    else:
        score_ratio = story_score / STORY_STRONG_SCORE
        objective_ratio = max_objective / STORY_STRONG_OBJECTIVE_SCORE
    return (
        max(score_ratio, objective_ratio) + min(support_count, 2) * 0.05,
        story_score,
        reliability_score,
        support_count,
        str(story.get("cluster_title", "") or ""),
    )


def build_near_miss_items(
    stories: List[Dict[str, Any]],
    *,
    selected_stories: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    selected_story_ids = {
        str(story.get("story_id", "") or "")
        for story in selected_stories
        if str(story.get("story_id", "") or "").strip()
    }
    candidates: List[Tuple[Tuple[float, float, int, int, str], Dict[str, Any]]] = []
    for story in stories:
        story_id = str(story.get("story_id", "") or "")
        if story_id in selected_story_ids:
            continue

        surface_worthy, rejection_reason = story_surface_worthiness(story)
        if surface_worthy or not story_has_near_miss_floor(story):
            continue

        summary = near_miss_summary_for_story(story)
        if not summary:
            continue

        candidates.append(
            (
                near_miss_rank(story),
                {
                    "story_id": story_id,
                    "title": str(story.get("cluster_title", "") or story.get("title", "") or "Untitled story"),
                    "source": str(story.get("source", "") or ""),
                    "summary": summary,
                    "miss_reason": near_miss_reason_for_story(story, rejection_reason),
                    "rejection_reason": rejection_reason,
                    "story_score": round(float(story.get("story_score", 0.0) or 0.0), 2),
                    "max_objective_score": round(max_story_objective_score(story), 2),
                    "signal_quality": story_signal_quality_label(story),
                },
            )
        )

    ranked = sorted(
        candidates,
        key=lambda entry: (entry[0], entry[1]["title"]),
        reverse=True,
    )
    return [item for _rank, item in ranked[:NEAR_MISS_LIMIT]]


def repeated_sentence_shells(lines: List[str]) -> int:
    shells = Counter(
        " ".join(signature_tokens(line)[:6])
        for line in lines
        if str(line).strip()
    )
    return sum(1 for _shell, count in shells.items() if count > 1)


def build_quality_eval(
    *,
    raw_item_count: int,
    stories: List[Dict[str, Any]],
    story_cards: List[Dict[str, Any]],
    top_picks: Dict[str, Dict[str, Any]],
    watchlist_hits: List[Dict[str, Any]],
    previous_brief: Dict[str, Any] | None,
) -> Dict[str, Any]:
    why_lines = [story.get("why_it_matters", "") for story in story_cards]
    source_domains = {
        domain
        for story in story_cards
        for domain in story.get("source_domains", [])
        if str(domain).strip()
    }
    distinct_pick_count = len(
        {
            (pick.get("item") or {}).get("story_id")
            for pick in top_picks.values()
            if isinstance(pick, dict) and pick.get("item")
        }
    )
    top_pick_count = sum(1 for pick in top_picks.values() if isinstance(pick, dict) and pick.get("item"))
    low_signal_repos = [
        story
        for story in story_cards
        if story.get("category") == "Repo"
        and (
            story.get("confidence") == "Low"
            or (story.get("is_generic_devtool") and not story.get("generic_repo_cap_exempt"))
        )
    ]
    thesis_linked = [
        story
        for story in story_cards
        if any(link.get("relation") != "adjacent" for link in story.get("thesis_links", []))
    ]
    low_reliability = [
        story
        for story in story_cards
        if story.get("reliability_label") == "Low"
    ]

    metrics = {
        "duplication": round(max(0.0, 100.0 - max(0, raw_item_count - len(stories)) * 8.0), 1),
        "novelty": round(
            sum(float(story.get("novelty_score", 0.0) or 0.0) for story in story_cards) / max(len(story_cards), 1),
            1,
        ),
        "source_quality": round(
            sum(int(story.get("reliability_score", 0) or 0) for story in story_cards) / max(len(story_cards), 1),
            1,
        ),
        "source_diversity": round(min(100.0, (len(source_domains) / max(len(story_cards), 1)) * 100.0), 1),
        "specificity_of_why_it_matters": round(
            (sum(1 for line in why_lines if why_it_matters_is_specific(str(line))) / max(len(why_lines), 1)) * 100.0,
            1,
        ),
        "actionability": round(
            (
                sum(
                    1
                    for story in story_cards
                    if story.get("action_suggestion")
                    and any(word in normalize_text(story.get("action_suggestion", "")) for word in ACTION_WORDS)
                )
                / max(len(story_cards), 1)
            ) * 100.0,
            1,
        ),
        "objective_separation": round(
            (distinct_pick_count / max(top_pick_count, 1)) * 100.0,
            1,
        ),
        "thesis_linkage_coverage": round(
            (len(thesis_linked) / max(len(story_cards), 1)) * 100.0,
            1,
        ),
        "watchlist_usefulness": 100.0 if watchlist_hits else 45.0,
        "signal_to_noise": 0.0,
    }
    metrics["signal_to_noise"] = round(
        (
            metrics["source_quality"]
            + metrics["specificity_of_why_it_matters"]
            + metrics["actionability"]
            + metrics["objective_separation"]
        ) / 4.0
        - (12.0 * len(low_signal_repos) / max(len(story_cards), 1)),
        1,
    )

    warnings = []
    if distinct_pick_count < top_pick_count:
        warnings.append("Same story won multiple objectives; keep the reuse only when the score gap is genuinely large.")
    if repeated_sentence_shells(why_lines) > 0:
        warnings.append("Why-it-matters lines still share repeated sentence shells.")
    if metrics["specificity_of_why_it_matters"] < 70.0:
        warnings.append("Why-it-matters specificity is still weak for too many surfaced stories.")
    if len(low_signal_repos) >= 2:
        warnings.append("Too many low-signal or generic repo stories are taking space.")
    if len(source_domains) < max(2, len(story_cards) // 2):
        warnings.append("Source diversity is thin relative to the number of surfaced stories.")
    if metrics["source_quality"] < 75.0:
        warnings.append("Source quality is soft; too much of the surfaced output depends on medium- or low-reliability evidence.")
    if metrics["novelty"] < 45.0:
        warnings.append("Novelty versus recent days is weak.")
    if metrics["thesis_linkage_coverage"] < 35.0:
        warnings.append("Too few surfaced stories are linked to a saved thesis.")
    if metrics["objective_separation"] < 70.0:
        warnings.append("Objective separation is weak; too few distinct stories won the objective slots.")
    if len(low_reliability) >= 2:
        warnings.append("Multiple low-reliability stories are still surfacing.")
    if previous_brief and float(((previous_brief.get("quality_eval", {}) or {}).get("metrics", {}) or {}).get("signal_to_noise", 0.0) or 0.0) - metrics["signal_to_noise"] >= 10.0:
        warnings.append("Signal-to-noise fell materially versus yesterday.")

    return {
        "metrics": metrics,
        "warnings": warnings[:QUALITY_WARNING_LIMIT],
    }


def apply_story_metadata_to_items(
    items: List[Dict[str, Any]],
    normalized_items: List[Dict[str, Any]],
) -> None:
    story_by_item_id = {
        normalized_item["item_id"]: normalized_item
        for normalized_item in normalized_items
    }
    for item in items:
        item_id = str(item.get("item_key", "") or item.get("id", "") or item.get("url", "") or item.get("title", ""))
        story_item = story_by_item_id.get(item_id)
        if not story_item:
            continue
        item["story_id"] = story_item.get("story_id", "")
        item["cluster_id"] = story_item.get("cluster_id", "")
        item["duplicate_group_id"] = story_item.get("duplicate_group_id", "")
        item["cluster_title"] = story_item.get("cluster_title", "")
        item["market_buckets"] = story_item.get("market_buckets", [])
        item["thesis_links"] = story_item.get("thesis_links", [])
        item["watchlist_matches"] = story_item.get("watchlist_matches", [])
        item["change_status"] = story_item.get("change_status", "")


def serializable_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if not key.startswith("_")
    }


def serializable_story(story: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in story.items()
        if not key.startswith("_")
    }


def build_operator_brief_artifact(
    items: List[Dict[str, Any]],
    *,
    memory: DigestMemory,
    memory_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    source_policies = load_json_config(SOURCE_POLICY_FILE_PATH, {})
    theses = load_json_config(THESES_FILE_PATH, {"theses": []})
    market_map = load_json_config(MARKET_MAP_FILE_PATH, {"buckets": []})
    watchlist = load_json_config(GITHUB_WATCHLIST_FILE_PATH, {"repos": [], "orgs": [], "topics": []})
    normalized_items = [
        normalize_item(
            item,
            policies=source_policies,
            theses=theses,
            market_map=market_map,
            watchlist=watchlist,
        )
        for item in items
    ]
    stories = build_stories(normalized_items, market_map=market_map)
    previous_brief = latest_previous_brief(memory, before_date=local_now().date().isoformat())
    stories, what_changed = apply_change_status(stories, previous_brief=previous_brief)

    story_lookup = {story["story_id"]: story for story in stories}
    for normalized_item in normalized_items:
        parent_story = next(
            (
                story
                for story in stories
                if normalized_item["item_id"] in story.get("supporting_item_ids", [])
            ),
            None,
        )
        if not parent_story:
            continue
        normalized_item["story_id"] = parent_story["story_id"]
        normalized_item["cluster_id"] = parent_story["cluster_id"]
        normalized_item["duplicate_group_id"] = parent_story["duplicate_group_id"]
        normalized_item["cluster_title"] = parent_story["cluster_title"]
        normalized_item["change_status"] = parent_story["change_status"]
        normalized_item["action_suggestion"] = parent_story["action_suggestion"]
        if not why_it_matters_is_specific(normalized_item["why_it_matters"]):
            normalized_item["why_it_matters"] = parent_story["why_it_matters"]

    story_cards = select_story_cards(stories)
    near_miss_items = build_near_miss_items(stories, selected_stories=story_cards)
    top_picks = build_story_top_picks(story_cards)
    thesis_tracker = build_thesis_tracker(stories, theses=theses, previous_brief=previous_brief)
    watchlist_hits = build_watchlist_hits(stories, previous_brief=previous_brief)
    market_pulse = build_market_map(stories, market_map=market_map, previous_brief=previous_brief)
    quality_eval = build_quality_eval(
        raw_item_count=len(items),
        stories=stories,
        story_cards=story_cards,
        top_picks=top_picks,
        watchlist_hits=watchlist_hits,
        previous_brief=previous_brief,
    )
    operator_moves = (
        build_strategy_brief(story_cards, memory_snapshot or {})
        if story_cards
        else dict(NO_STRONG_SIGNAL_OPERATOR_MOVES)
    )

    apply_story_metadata_to_items(items, normalized_items)

    brief = {
        "version": 1,
        "date": local_now().date().isoformat(),
        "generated_at": local_now().astimezone(timezone.utc).isoformat(),
        "summary": {
            "raw_item_count": len(items),
            "normalized_item_count": len(normalized_items),
            "story_count": len(stories),
            "story_card_count": len(story_cards),
        },
        "operator_moves": operator_moves,
        "what_changed": what_changed,
        "thesis_tracker": thesis_tracker,
        "market_map": market_pulse,
        "watchlist_hits": watchlist_hits,
        "quality_eval": quality_eval,
        "top_picks": top_picks,
        "near_miss_items": near_miss_items,
        "stories": [serializable_story(story) for story in stories],
        "story_cards": [serializable_story(story) for story in story_cards],
        "items": [serializable_item(item) for item in normalized_items],
        "memory_snapshot": memory_snapshot or {},
    }

    for story in brief["stories"]:
        if not story.get("why_it_matters"):
            parent = story_lookup.get(story["story_id"])
            if parent:
                story["why_it_matters"] = parent["why_it_matters"]

    return brief

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from config import REGULATORY_TARGET_ITEMS

from data_common import DigestItem, normalize_text, titles_are_similar


REGULATORY_FRESH_WINDOW = timedelta(hours=72)
REGULATORY_RECENT_WINDOW = timedelta(days=7)
REGULATORY_MIN_SELECTION_SCORE = 65
REGULATORY_RECALL_CAP = 1
REGULATORY_SUBCATEGORY_BONUS = {'recall': 0, 'enforcement': 0, 'guidance': 20, 'policy': 16, 'reimbursement': 18, 'interoperability': 20, 'privacy': 18, 'safety_alert': 6}


def regulatory_bucket(subcategory: str) -> str:
    if subcategory in {"recall", "enforcement", "safety_alert"}:
        return "recall_enforcement"
    if subcategory in {"guidance", "policy"}:
        return "policy_guidance"
    if subcategory in {"reimbursement", "interoperability"}:
        return "reimbursement_interoperability"
    if subcategory == "privacy":
        return "privacy_security"
    return subcategory or "other"

def recall_class_level(classification: str) -> int:
    normalized = (classification or "").upper().strip()
    if normalized.startswith("CLASS III"):
        return 3
    if normalized.startswith("CLASS II"):
        return 2
    if normalized.startswith("CLASS I"):
        return 1
    return 0

def regulatory_is_fresh(item: DigestItem, now: datetime) -> bool:
    published_at = item.get("published_at")
    if not isinstance(published_at, datetime):
        return False
    return now - published_at <= REGULATORY_FRESH_WINDOW

def regulatory_base_breakdown(
    item: DigestItem,
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> Dict[str, int]:
    published_at = item.get("published_at")
    freshness = -15
    if isinstance(published_at, datetime):
        age = now - published_at
        if age <= timedelta(hours=24):
            freshness = 120
        elif age <= REGULATORY_FRESH_WINDOW:
            freshness = 90
        elif age <= REGULATORY_RECENT_WINDOW:
            freshness = 45
        else:
            freshness = 5

    novelty = 20
    if item.get("item_key", "") in sent_item_keys:
        novelty = -55 if not regulatory_is_fresh(item, now) else -10

    subcategory = item.get("subcategory", "policy")
    subcategory_bonus = REGULATORY_SUBCATEGORY_BONUS.get(subcategory, 10)

    severity = 0
    class_level = recall_class_level(item.get("classification", ""))
    if class_level == 1:
        severity += 15
    elif class_level == 2:
        severity += 8
    elif class_level == 3:
        severity += 3

    if (item.get("status", "") or "").strip().lower() == "ongoing":
        severity -= 5

    total = freshness + novelty + subcategory_bonus + severity
    return {
        "freshness": freshness,
        "novelty": novelty,
        "subcategory": subcategory_bonus,
        "severity": severity,
        "total": total,
    }

def is_unusually_strong_recall(item: DigestItem, base_breakdown: Dict[str, int]) -> bool:
    return (
        regulatory_bucket(item.get("subcategory", "")) == "recall_enforcement"
        and base_breakdown["freshness"] >= 120
        and base_breakdown["novelty"] >= -10
        and recall_class_level(item.get("classification", "")) == 1
    )

def regulatory_selection_breakdown(
    item: DigestItem,
    selected_items: List[DigestItem],
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> Dict[str, int] | None:
    base = regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)
    bucket = regulatory_bucket(item.get("subcategory", ""))
    recall_count = sum(
        1
        for selected_item in selected_items
        if regulatory_bucket(selected_item.get("subcategory", "")) == "recall_enforcement"
    )

    if bucket == "recall_enforcement" and recall_count >= REGULATORY_RECALL_CAP:
        if not is_unusually_strong_recall(item, base):
            return None

    selected_sources = {selected_item.get("source", "") for selected_item in selected_items}
    selected_orgs = {selected_item.get("organization", "") for selected_item in selected_items}
    selected_buckets = {
        regulatory_bucket(selected_item.get("subcategory", ""))
        for selected_item in selected_items
    }
    selected_topics = {selected_item.get("topic_key", "") for selected_item in selected_items}
    selected_subcategories = {
        selected_item.get("subcategory", "")
        for selected_item in selected_items
    }
    selected_firms = {
        selected_item.get("firm_key", "")
        for selected_item in selected_items
        if selected_item.get("firm_key", "")
    }

    organization_penalty = -10 if item.get("organization", "") in selected_orgs else 0
    source_penalty = -8 if item.get("source", "") in selected_sources else 0
    bucket_penalty = -18 if bucket in selected_buckets else 0
    topic_penalty = -12 if item.get("topic_key", "") in selected_topics else 0
    subcategory_penalty = (
        -8 if item.get("subcategory", "") in selected_subcategories else 0
    )
    same_firm_penalty = (
        -25
        if item.get("firm_key", "") and item.get("firm_key", "") in selected_firms
        else 0
    )

    total = (
        base["total"]
        + organization_penalty
        + source_penalty
        + bucket_penalty
        + topic_penalty
        + subcategory_penalty
        + same_firm_penalty
    )
    return {
        "freshness": base["freshness"],
        "novelty": base["novelty"],
        "subcategory": base["subcategory"],
        "severity": base["severity"],
        "organization_diversity": organization_penalty,
        "source_diversity": source_penalty,
        "bucket_diversity": bucket_penalty,
        "topic_diversity": topic_penalty,
        "subcategory_diversity": subcategory_penalty,
        "same_firm": same_firm_penalty,
        "total": total,
    }

def classify_regulatory_skip_reason(
    item: DigestItem,
    selected_items: List[DigestItem],
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> str:
    base = regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)
    bucket = regulatory_bucket(item.get("subcategory", ""))
    recall_count = sum(
        1
        for selected_item in selected_items
        if regulatory_bucket(selected_item.get("subcategory", "")) == "recall_enforcement"
    )
    if bucket == "recall_enforcement" and recall_count >= REGULATORY_RECALL_CAP:
        if not is_unusually_strong_recall(item, base):
            return "recall_cap"
    if item.get("item_key", "") in sent_item_keys and not regulatory_is_fresh(item, now):
        return "already_sent_stale"
    if item.get("firm_key", "") and item.get("firm_key", "") in {
        selected_item.get("firm_key", "")
        for selected_item in selected_items
    }:
        return "same_firm"
    if regulatory_selection_breakdown(
        item,
        selected_items,
        now=now,
        sent_item_keys=sent_item_keys,
    ):
        breakdown = regulatory_selection_breakdown(
            item,
            selected_items,
            now=now,
            sent_item_keys=sent_item_keys,
        )
        if breakdown and breakdown["total"] < REGULATORY_MIN_SELECTION_SCORE:
            return "low_score"
        if breakdown and breakdown["bucket_diversity"] < 0:
            return "bucket_cluster"
        if breakdown and breakdown["topic_diversity"] < 0:
            return "topic_cluster"
        if breakdown and breakdown["source_diversity"] < 0:
            return "source_cluster"
    return "rank_cutoff"

def select_regulatory_items(
    items: List[DigestItem],
    sent_item_keys: set[str],
    *,
    now: datetime | None = None,
    max_items: int = REGULATORY_TARGET_ITEMS,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    dedupe_exclusions: Counter[str] = Counter()

    ranked = sorted(
        items,
        key=lambda item: (
            regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)["total"],
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )

    seen_ids = set()
    deduped: List[DigestItem] = []
    for item in ranked:
        unique_id = normalize_text(str(item.get("id", "")))
        if unique_id and unique_id in seen_ids:
            dedupe_exclusions["duplicate_id"] += 1
            continue
        if any(titles_are_similar(item.get("title", ""), other.get("title", "")) for other in deduped):
            dedupe_exclusions["similar_title"] += 1
            continue
        if unique_id:
            seen_ids.add(unique_id)
        deduped.append(item)

    selected: List[DigestItem] = []
    remaining = deduped[:]
    fallback_reason = ""
    best_remaining_score: int | None = None

    while len(selected) < max_items and remaining:
        scored_candidates: List[Tuple[int, DigestItem, Dict[str, int]]] = []
        for item in remaining:
            breakdown = regulatory_selection_breakdown(
                item,
                selected,
                now=now,
                sent_item_keys=sent_item_keys,
            )
            if not breakdown:
                continue
            scored_candidates.append((breakdown["total"], item, breakdown))

        if not scored_candidates:
            fallback_reason = "no_candidates_after_recall_cap_and_diversity"
            break

        scored_candidates.sort(
            key=lambda entry: (
                entry[0],
                entry[1].get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
                entry[1].get("title", ""),
            ),
            reverse=True,
        )
        best_score, best_item, best_breakdown = scored_candidates[0]
        best_remaining_score = best_score

        if best_score < REGULATORY_MIN_SELECTION_SCORE:
            fallback_reason = (
                f"best_remaining_score_below_threshold:{best_score}<{REGULATORY_MIN_SELECTION_SCORE}"
            )
            break

        selected.append(
            {
                **best_item,
                "selection_score": best_score,
                "score_breakdown": best_breakdown,
            }
        )
        remaining = [
            item
            for item in remaining
            if item.get("id", "") != best_item.get("id", "")
        ]

    selection_exclusions: Counter[str] = Counter()
    for item in remaining:
        selection_exclusions[
            classify_regulatory_skip_reason(
                item,
                selected,
                now=now,
                sent_item_keys=sent_item_keys,
            )
        ] += 1

    if len(selected) < max_items and not fallback_reason:
        fallback_reason = "insufficient_high_quality_candidates"

    return selected, {
        "filtered_count": len(deduped),
        "excluded_reasons": dedupe_exclusions + selection_exclusions,
        "fallback_reason": fallback_reason or "none",
        "best_remaining_score": best_remaining_score,
    }


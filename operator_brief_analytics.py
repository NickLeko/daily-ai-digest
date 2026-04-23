from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List

from scoring import OBJECTIVE_DISPLAY_ORDER


ACTION_WORDS = {
    "audit",
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


def build_story_top_picks(
    stories: List[Dict[str, Any]],
    *,
    objective_min_scores: Dict[str, float],
) -> Dict[str, Dict[str, Any]]:
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
        if not best or float((best.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0) < objective_min_scores[objective]:
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
                    >= objective_min_scores[objective]
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
    human_label_for_bucket: Callable[[str, Dict[str, Any]], str],
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
    watchlist_story_limit: int,
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

    return hits[:watchlist_story_limit]


def repeated_sentence_shells(
    lines: List[str],
    *,
    signature_tokens: Callable[[str], List[str]],
) -> int:
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
    normalize_text: Callable[[str], str],
    signature_tokens: Callable[[str], List[str]],
    why_it_matters_is_specific: Callable[[str], bool],
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
    if repeated_sentence_shells(why_lines, signature_tokens=signature_tokens) > 0:
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

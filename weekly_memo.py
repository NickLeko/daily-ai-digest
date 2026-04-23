from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app_logging import configure_logging, info
from config import OPERATOR_BRIEF_FILE_PATH
from memory import DigestMemory, load_digest_memory
from selection_audit import SELECTION_AUDIT_FILE_PATH
from state import local_now
from storage import read_json_file


WEEKLY_MEMO_FILE_PATH = "latest_weekly_operator_memo.md"
DEFAULT_LOOKBACK_DAYS = 7
MIN_MEDIUM_CONFIDENCE_BRIEFS = 2
MIN_MEDIUM_CONFIDENCE_SIGNALS = 3
MIN_HIGH_CONFIDENCE_BRIEFS = 4
MIN_HIGH_CONFIDENCE_SIGNALS = 8

CORE_WEDGE_TERMS = {
    "admin",
    "ambient",
    "appeal",
    "audit",
    "authorization",
    "claim",
    "claims",
    "clinical",
    "denial",
    "denials",
    "documentation",
    "ehr",
    "evidence",
    "fhir",
    "governance",
    "handoff",
    "healthcare",
    "interoperability",
    "intake",
    "payer",
    "prior auth",
    "prior authorization",
    "provider",
    "rcm",
    "referral",
    "revenue cycle",
    "tefca",
    "workflow",
}

STRONG_OPERATOR_WEDGE_TERMS = {
    "ambient",
    "appeal",
    "authorization",
    "claim",
    "claims",
    "denial",
    "denials",
    "documentation",
    "ehr",
    "evidence handoff",
    "fhir",
    "handoff",
    "interoperability",
    "intake",
    "payer",
    "prior auth",
    "prior authorization",
    "provider workflow",
    "rcm",
    "referral",
    "revenue cycle",
    "tefca",
}

LOW_FIT_REGULATORY_NOISE_TERMS = {
    "bottle",
    "capsule",
    "capsules",
    "drug recall",
    "hydrochloride",
    "manufactured by",
    "pharmaceutical",
    "recall",
    "tablet",
    "tablets",
    "usp",
}

GENERIC_THEME_LABELS = {
    "Buyer Adoption / Cio / Enterprise Demand",
    "Infrastructure / Developer Tooling",
}


def load_json_file(path: str) -> Dict[str, Any]:
    return read_json_file(path, {}, expected_type=dict)


def parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def sentence(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text.rstrip(".")


def compact_reason(value: Any) -> str:
    text = sentence(value)
    return text.replace("Filtered because ", "").replace("Selected because ", "")


def labelize(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(r"[_-]+", " ", raw).title()


def append_unique(lines: List[str], line: str) -> None:
    normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
    existing = {
        re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        for value in lines
    }
    if normalized and normalized not in existing:
        lines.append(line)


def recurring_topic_label(line: str) -> str:
    label = line.lstrip("- ").split(":", 1)[0]
    if label in {"Thesis thread", "Repeated language"}:
        return ""
    return label


def story_title(story: Dict[str, Any]) -> str:
    return sentence(story.get("cluster_title") or story.get("title") or "Untitled story")


def story_score(story: Dict[str, Any]) -> float:
    return float(story.get("story_score", story.get("priority_score", 0.0)) or 0.0)


def story_text_blob(story: Dict[str, Any]) -> str:
    values: List[str] = [
        story_title(story),
        str(story.get("category", "") or ""),
        str(story.get("item_type", "") or ""),
        *[str(value) for value in story.get("workflow_wedges", []) or []],
        *[str(value) for value in story.get("matched_themes", []) or []],
        *[str(value) for value in story.get("market_bucket_ids", []) or []],
        *[str(value) for value in story.get("market_buckets", []) or []],
        *[str(value) for value in story.get("signature_tokens", []) or []],
        *story_thesis_labels(story),
    ]
    return " ".join(values).lower()


def story_matches_core_wedge(story: Dict[str, Any]) -> bool:
    text = story_text_blob(story)
    has_strong_operator_wedge = any(term in text for term in STRONG_OPERATOR_WEDGE_TERMS)
    if any(term in text for term in LOW_FIT_REGULATORY_NOISE_TERMS) and not has_strong_operator_wedge:
        return False
    return any(term in text for term in CORE_WEDGE_TERMS)


def eligible_signal_stories(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        story
        for story in stories
        if story_matches_core_wedge(story)
        and (
            story_score(story) >= 24.0
            or str(story.get("change_status", "") or "") in {"escalating", "repeated_stronger"}
            or story.get("reliability_label") == "High"
        )
    ]


def story_bucket_labels(story: Dict[str, Any]) -> List[str]:
    labels = [labelize(value) for value in story.get("market_buckets", []) or [] if labelize(value)]
    if labels:
        return labels
    return [
        labelize(value)
        for value in story.get("market_bucket_ids", []) or []
        if labelize(value)
    ]


def story_thesis_labels(story: Dict[str, Any]) -> List[str]:
    labels = []
    for link in story.get("thesis_links", []) or []:
        if not isinstance(link, dict):
            continue
        label = sentence(link.get("title") or labelize(link.get("thesis_id")))
        relation = str(link.get("relation", "") or "")
        if label and relation != "adjacent":
            labels.append(label)
    return labels


def confidence_profile(brief_count: int, eligible_signal_count: int) -> Dict[str, str]:
    if (
        brief_count >= MIN_HIGH_CONFIDENCE_BRIEFS
        and eligible_signal_count >= MIN_HIGH_CONFIDENCE_SIGNALS
    ):
        return {
            "level": "High",
            "summary": "enough saved history to treat recurring patterns as weekly signals",
        }
    if (
        brief_count >= MIN_MEDIUM_CONFIDENCE_BRIEFS
        and eligible_signal_count >= MIN_MEDIUM_CONFIDENCE_SIGNALS
    ):
        return {
            "level": "Medium",
            "summary": "enough data for directional synthesis, not enough for strong trend claims",
        }
    return {
        "level": "Low",
        "summary": "not enough saved briefs or eligible wedge signals for a confident weekly read",
    }


def confidence_line(profile: Dict[str, str], *, brief_count: int, eligible_signal_count: int) -> str:
    return (
        f"- Confidence: {profile['level']} - {profile['summary']} "
        f"({brief_count} saved brief(s), {eligible_signal_count} eligible wedge signal(s))."
    )


def normalize_latest_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    if not brief:
        return {}
    stories = brief.get("story_cards") or brief.get("stories") or []
    if not isinstance(stories, list):
        stories = []
    return {
        "date": str(brief.get("date", "") or ""),
        "generated_at": str(brief.get("generated_at", "") or ""),
        "top_insight": sentence((brief.get("operator_moves", {}) or {}).get("top_insight", "")),
        "stories": [story for story in stories if isinstance(story, dict)],
        "operator_moves": brief.get("operator_moves", {}) if isinstance(brief.get("operator_moves", {}), dict) else {},
        "quality_eval": brief.get("quality_eval", {}) if isinstance(brief.get("quality_eval", {}), dict) else {},
        "thesis_tracker": [
            entry
            for entry in brief.get("thesis_tracker", []) or []
            if isinstance(entry, dict)
        ],
        "watchlist_hits": [
            entry
            for entry in brief.get("watchlist_hits", []) or []
            if isinstance(entry, dict)
        ],
        "top_picks": brief.get("top_picks", {}) if isinstance(brief.get("top_picks", {}), dict) else {},
    }


def recent_briefs(
    memory: DigestMemory,
    *,
    latest_brief: Dict[str, Any] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> List[Dict[str, Any]]:
    cutoff = local_now().date() - timedelta(days=max(1, lookback_days) - 1)
    by_date: Dict[str, Dict[str, Any]] = {}

    for brief in memory.get("daily_briefs", []) or []:
        if not isinstance(brief, dict):
            continue
        brief_date = parse_date(brief.get("date") or brief.get("generated_at"))
        if brief_date and brief_date < cutoff:
            continue
        key = brief_date.isoformat() if brief_date else str(brief.get("date", "") or "")
        if key:
            by_date[key] = brief

    normalized_latest = normalize_latest_brief(latest_brief or {})
    latest_date = parse_date(normalized_latest.get("date") or normalized_latest.get("generated_at"))
    if normalized_latest and (latest_date is None or latest_date >= cutoff):
        key = latest_date.isoformat() if latest_date else str(normalized_latest.get("date", "") or "latest")
        by_date[key] = normalized_latest

    return [
        brief
        for _key, brief in sorted(
            by_date.items(),
            key=lambda item: parse_date(item[0]) or date.min,
        )
    ][-lookback_days:]


def all_stories(briefs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stories: List[Dict[str, Any]] = []
    for brief in briefs:
        brief_date = str(brief.get("date", "") or "")
        for story in brief.get("stories", []) or []:
            if not isinstance(story, dict):
                continue
            stories.append({**story, "_brief_date": brief_date})
    return stories


def build_recurring_themes(stories: List[Dict[str, Any]]) -> List[str]:
    bucket_counts: Counter[str] = Counter()
    thesis_counts: Counter[str] = Counter()
    token_counts: Counter[str] = Counter()

    for story in stories:
        bucket_counts.update(story_bucket_labels(story))
        thesis_counts.update(story_thesis_labels(story))
        tokens = [
            str(token).strip()
            for token in story.get("signature_tokens", []) or []
            if str(token).strip()
        ]
        if tokens:
            token_counts[" ".join(tokens[:3])] += 1

    lines = []
    for label, count in bucket_counts.most_common(4):
        lines.append(f"- {label}: appeared in {count} story signal(s).")
    for label, count in thesis_counts.most_common(2):
        lines.append(f"- Thesis thread: {label} ({count} supporting signal(s)).")
    for label, count in token_counts.most_common(2):
        if count > 1:
            lines.append(f"- Repeated language: {label} ({count} mentions).")
    return lines[:6] or ["- Not enough recurring story history yet."]


def build_signals_that_matter(stories: List[Dict[str, Any]]) -> List[str]:
    stories = eligible_signal_stories(stories)
    grouped: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "max_score": 0.0,
            "dates": set(),
            "reliability": "",
            "change_status": "",
            "title": "",
        }
    )
    for story in stories:
        title = story_title(story)
        key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip() or title.lower()
        entry = grouped[key]
        entry["count"] += 1
        entry["max_score"] = max(float(entry["max_score"]), story_score(story))
        if story.get("_brief_date"):
            entry["dates"].add(str(story.get("_brief_date")))
        entry["reliability"] = str(story.get("reliability_label", "") or entry["reliability"])
        entry["change_status"] = str(story.get("change_status", "") or entry["change_status"])
        entry["title"] = title

    ranked = sorted(
        grouped.values(),
        key=lambda entry: (entry["count"], entry["max_score"], entry["title"]),
        reverse=True,
    )
    lines = []
    for entry in ranked[:5]:
        dates = ", ".join(sorted(entry["dates"])) if entry["dates"] else "recent run"
        status = f"; {entry['change_status']}" if entry["change_status"] else ""
        reliability = f"; reliability {entry['reliability']}" if entry["reliability"] else ""
        lines.append(
            f"- {entry['title']}: seen {entry['count']}x ({dates}); "
            f"max score {entry['max_score']:.2f}{reliability}{status}."
        )
    return lines or ["- No eligible operator-wedge signals surfaced yet."]


def latest_full_brief(briefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return briefs[-1] if briefs else {}


def pick_item_title(pick: Dict[str, Any]) -> str:
    item = pick.get("item", {}) if isinstance(pick, dict) else {}
    if not isinstance(item, dict):
        return ""
    return story_title(item)


def strongest_wedge_label(stories: List[Dict[str, Any]]) -> str:
    counts: Counter[str] = Counter()
    for story in stories:
        labels = [
            label
            for label in story_bucket_labels(story)
            if label and label not in GENERIC_THEME_LABELS
        ]
        if not labels:
            labels = [
                labelize(value)
                for value in story.get("workflow_wedges", []) or []
                if labelize(value)
            ]
        counts.update(labels)
    if counts:
        return counts.most_common(1)[0][0]
    return "the strongest operator wedge"


def build_opportunities(
    *,
    strongest_wedge: str,
    confidence: Dict[str, str],
    eligible_stories: List[Dict[str, Any]],
) -> List[str]:
    lines = []
    wedge = strongest_wedge.lower()
    if confidence.get("level") == "Low":
        append_unique(
            lines,
            f"- Hold roadmap commitments on {wedge}; collect another week of primary or implementation evidence first.",
        )
    append_unique(
        lines,
        f"- Map one {wedge} workflow from trigger to evidence, status, owner, and audit trail.",
    )
    append_unique(
        lines,
        f"- Look for a narrow tool that reduces handoff ambiguity in {wedge}, not a broad agent demo.",
    )
    if len(eligible_stories) >= 2:
        append_unique(
            lines,
            f"- Compare the strongest {wedge} signals side by side and isolate the repeated operational bottleneck.",
        )
    return lines or ["- No concrete build opportunity stood out from the saved briefs."]


def build_content_angles(
    *,
    strongest_wedge: str,
    recurring_lines: List[str],
    confidence: Dict[str, str],
) -> List[str]:
    lines = []
    wedge = strongest_wedge.lower()
    if confidence.get("level") == "Low":
        append_unique(
            lines,
            f"- Frame {wedge} as a watchlist, not a market conclusion.",
        )
    append_unique(
        lines,
        f"- Explain what would make {wedge} operationally real: evidence quality, integration burden, and ownership.",
    )
    append_unique(
        lines,
        f"- Contrast concrete {wedge} workflow proof against generic AI tooling noise.",
    )

    for line in recurring_lines[:2]:
        label = recurring_topic_label(line)
        if label and not label.startswith("Not enough"):
            append_unique(
                lines,
                f"- Explain why {label.lower()} keeps recurring and what operators should ignore.",
            )
        if len(lines) >= 4:
            break
    return lines or ["- No clear content angle stood out from the saved briefs."]


def audit_filtered_stories(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    stories = [row for row in audit.get("stories", []) or [] if isinstance(row, dict)]
    return sorted(
        [row for row in stories if not row.get("selected")],
        key=lambda row: float(((row.get("score_summary", {}) or {}).get("story_score", 0.0)) or 0.0),
        reverse=True,
    )


def build_noise(
    audit: Dict[str, Any],
    briefs: List[Dict[str, Any]],
    *,
    ineligible_stories: List[Dict[str, Any]] | None = None,
) -> List[str]:
    lines = []
    for row in audit_filtered_stories(audit)[:4]:
        title = sentence(row.get("title", "Untitled"))
        reason = compact_reason(row.get("primary_reason", "filtered"))
        score = float(((row.get("score_summary", {}) or {}).get("story_score", 0.0)) or 0.0)
        append_unique(lines, f"- {title}: filtered at score {score:.2f}; {reason}.")

    for story in sorted(ineligible_stories or [], key=story_score, reverse=True)[:3]:
        append_unique(
            lines,
            f"- {story_title(story)}: high score {story_score(story):.2f}, but outside the core operator wedges.",
        )

    for brief in reversed(briefs):
        quality = brief.get("quality_eval", {}) if isinstance(brief.get("quality_eval", {}), dict) else {}
        warnings = quality.get("warnings", []) if isinstance(quality.get("warnings", []), list) else []
        for warning in warnings:
            warning_text = sentence(warning)
            if warning_text and warning_text not in " ".join(lines):
                append_unique(lines, f"- Quality warning: {warning_text}.")
            if len(lines) >= 5:
                break
        if len(lines) >= 5:
            break
    return lines or ["- No obvious noise pattern in the saved audit/briefs."]


def build_watch_next_week(briefs: List[Dict[str, Any]], recurring_lines: List[str]) -> List[str]:
    latest = latest_full_brief(briefs)
    lines = []
    for hit in latest.get("watchlist_hits", []) or []:
        if isinstance(hit, dict):
            title = sentence(hit.get("cluster_title", ""))
            status = sentence(hit.get("status", ""))
            if title:
                append_unique(lines, f"- Watchlist: {title} ({status or 'active'}).")

    for story in latest.get("stories", []) or []:
        if not isinstance(story, dict):
            continue
        status = str(story.get("change_status", "") or "")
        if status in {"escalating", "repeated_stronger"}:
            append_unique(lines, f"- Recheck: {story_title(story)} ({status}).")
        if len(lines) >= 4:
            break

    for line in recurring_lines[:2]:
        label = recurring_topic_label(line)
        if label and not label.startswith("Not enough"):
            append_unique(
                lines,
                f"- Track whether {label.lower()} produces concrete implementation evidence.",
            )
        if len(lines) >= 5:
            break
    return lines or ["- Watch for whether today's strongest signals repeat with better evidence."]


def build_weekly_memo_markdown(
    *,
    memory: DigestMemory,
    latest_brief: Dict[str, Any] | None = None,
    selection_audit: Dict[str, Any] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> str:
    briefs = recent_briefs(memory, latest_brief=latest_brief, lookback_days=lookback_days)
    stories = all_stories(briefs)
    eligible_stories = eligible_signal_stories(stories)
    ineligible_stories = [
        story
        for story in stories
        if story not in eligible_stories and story_score(story) >= 24.0
    ]
    latest = latest_full_brief(briefs)
    recurring = build_recurring_themes(eligible_stories)
    strongest_wedge = strongest_wedge_label(eligible_stories)
    confidence = confidence_profile(len(briefs), len(eligible_stories))
    generated_at = local_now().strftime("%Y-%m-%d %H:%M:%S %Z")
    top_insight = sentence(latest.get("top_insight", ""))
    signal_lines = build_signals_that_matter(eligible_stories)
    material_signal_count = len(signal_lines) if eligible_stories else 0

    lines = [
        "# Weekly Operator Memo",
        "",
        f"Generated: {generated_at}",
        f"Lookback: {lookback_days} days, {len(briefs)} saved digest brief(s), {len(stories)} story signal(s).",
        "",
        "## Weekly Summary",
    ]
    if top_insight:
        lines.append(f"- Latest operator insight: {top_insight}.")
    lines.append(
        confidence_line(
            confidence,
            brief_count=len(briefs),
            eligible_signal_count=len(eligible_stories),
        )
    )
    lines.append(
        f"- Main read: {material_signal_count} material signal thread(s), "
        f"{len(audit_filtered_stories(selection_audit or {}))} filtered near-miss(es) in the latest audit."
    )

    sections = [
        ("Recurring Themes", recurring),
        ("Signals That Matter", signal_lines),
        (
            "Product / Build Opportunities",
            build_opportunities(
                strongest_wedge=strongest_wedge,
                confidence=confidence,
                eligible_stories=eligible_stories,
            ),
        ),
        (
            "Content Angles",
            build_content_angles(
                strongest_wedge=strongest_wedge,
                recurring_lines=recurring,
                confidence=confidence,
            ),
        ),
        (
            "Likely Noise / Overhyped Items",
            build_noise(
                selection_audit or {},
                briefs,
                ineligible_stories=ineligible_stories,
            ),
        ),
        ("Watch Next Week", build_watch_next_week(briefs, recurring)),
    ]
    for title, bullets in sections:
        lines.extend(["", f"## {title}"])
        lines.extend(bullets)

    return "\n".join(lines) + "\n"


def write_weekly_memo(
    *,
    output_path: str = WEEKLY_MEMO_FILE_PATH,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    memory: DigestMemory | None = None,
    latest_brief_path: str = OPERATOR_BRIEF_FILE_PATH,
    selection_audit_path: str = SELECTION_AUDIT_FILE_PATH,
) -> str:
    memo = build_weekly_memo_markdown(
        memory=memory if memory is not None else load_digest_memory(),
        latest_brief=load_json_file(latest_brief_path),
        selection_audit=load_json_file(selection_audit_path),
        lookback_days=lookback_days,
    )
    Path(output_path).write_text(memo, encoding="utf-8")
    return memo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a local weekly operator memo.")
    parser.add_argument(
        "--output",
        default=WEEKLY_MEMO_FILE_PATH,
        help="Markdown output path.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Number of recent days to summarize.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    configure_logging()
    args = parse_args()
    write_weekly_memo(output_path=args.output, lookback_days=args.lookback_days)
    info("Weekly operator memo saved", path=args.output)

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

from config import OPERATOR_BRIEF_FILE_PATH
from memory import DigestMemory, load_digest_memory
from selection_audit import SELECTION_AUDIT_FILE_PATH
from state import local_now


WEEKLY_MEMO_FILE_PATH = "latest_weekly_operator_memo.md"
DEFAULT_LOOKBACK_DAYS = 7


def load_json_file(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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
    return lines or ["- No surfaced story signals available yet."]


def latest_full_brief(briefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return briefs[-1] if briefs else {}


def pick_item_title(pick: Dict[str, Any]) -> str:
    item = pick.get("item", {}) if isinstance(pick, dict) else {}
    if not isinstance(item, dict):
        return ""
    return story_title(item)


def build_opportunities(brief: Dict[str, Any]) -> List[str]:
    lines = []
    operator_moves = brief.get("operator_moves", {}) if isinstance(brief.get("operator_moves", {}), dict) else {}
    build_idea = sentence(operator_moves.get("build_idea", ""))
    if build_idea:
        append_unique(lines, f"- {build_idea}.")

    top_picks = brief.get("top_picks", {}) if isinstance(brief.get("top_picks", {}), dict) else {}
    build_pick = pick_item_title(top_picks.get("build", {}))
    if build_pick:
        append_unique(lines, f"- Pressure-test the build pick: {build_pick}.")

    for story in sorted(brief.get("stories", []) or [], key=story_score, reverse=True):
        action = sentence(story.get("action_suggestion", ""))
        if action:
            append_unique(lines, f"- {action}.")
        if len(lines) >= 4:
            break
    return lines or ["- No concrete build opportunity stood out from the saved briefs."]


def build_content_angles(brief: Dict[str, Any], recurring_lines: List[str]) -> List[str]:
    lines = []
    operator_moves = brief.get("operator_moves", {}) if isinstance(brief.get("operator_moves", {}), dict) else {}
    content_angle = sentence(operator_moves.get("content_angle", ""))
    if content_angle:
        append_unique(lines, f"- {content_angle}.")

    top_picks = brief.get("top_picks", {}) if isinstance(brief.get("top_picks", {}), dict) else {}
    content_pick = pick_item_title(top_picks.get("content", {}))
    if content_pick:
        append_unique(lines, f"- Use the content pick as a concrete example: {content_pick}.")

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


def build_noise(audit: Dict[str, Any], briefs: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for row in audit_filtered_stories(audit)[:4]:
        title = sentence(row.get("title", "Untitled"))
        reason = compact_reason(row.get("primary_reason", "filtered"))
        score = float(((row.get("score_summary", {}) or {}).get("story_score", 0.0)) or 0.0)
        append_unique(lines, f"- {title}: filtered at score {score:.2f}; {reason}.")

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
    latest = latest_full_brief(briefs)
    recurring = build_recurring_themes(stories)
    generated_at = local_now().strftime("%Y-%m-%d %H:%M:%S %Z")
    top_insight = sentence(latest.get("top_insight", ""))
    signal_lines = build_signals_that_matter(stories)
    material_signal_count = len(signal_lines) if stories else 0

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
        f"- Main read: {material_signal_count} material signal thread(s), "
        f"{len(audit_filtered_stories(selection_audit or {}))} filtered near-miss(es) in the latest audit."
    )

    sections = [
        ("Recurring Themes", recurring),
        ("Signals That Matter", signal_lines),
        ("Product / Build Opportunities", build_opportunities(latest)),
        ("Content Angles", build_content_angles(latest, recurring)),
        ("Likely Noise / Overhyped Items", build_noise(selection_audit or {}, briefs)),
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
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(memo)
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
    args = parse_args()
    write_weekly_memo(output_path=args.output, lookback_days=args.lookback_days)
    print(f"Weekly operator memo saved to {args.output}")

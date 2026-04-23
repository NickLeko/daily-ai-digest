from __future__ import annotations

from html import escape
import re
from typing import Dict, List

from selection_policy import (
    confidence_display_for_story,
    story_has_material_signal_for_policy,
    story_is_low_signal_for_policy,
    story_signal_quality_for_policy,
)


CATEGORY_HEADINGS = {
    "Repo": "Repos",
    "News": "News",
    "Regulatory": "Regulatory Updates",
}

SIGNAL_STYLES = {
    "high": {
        "label": "HIGH SIGNAL",
        "bg": "#fde68a",
        "color": "#7c2d12",
    },
    "medium": {
        "label": "MEDIUM SIGNAL",
        "bg": "#dbeafe",
        "color": "#1e3a8a",
    },
    "low": {
        "label": "LOW SIGNAL",
        "bg": "#e5e7eb",
        "color": "#374151",
    },
}

RELIABILITY_STYLES = {
    "High": {"bg": "#dcfce7", "color": "#166534"},
    "Medium": {"bg": "#fef3c7", "color": "#92400e"},
    "Low": {"bg": "#fee2e2", "color": "#991b1b"},
}

CHANGE_STYLES = {
    "new": {"label": "NEW", "bg": "#dbeafe", "color": "#1d4ed8"},
    "escalating": {"label": "ESCALATING", "bg": "#fef3c7", "color": "#92400e"},
    "repeated_stronger": {"label": "STRONGER", "bg": "#ede9fe", "color": "#6d28d9"},
    "repeated": {"label": "REPEATED", "bg": "#e5e7eb", "color": "#374151"},
    "fading": {"label": "FADING", "bg": "#fce7f3", "color": "#9d174d"},
}

SECTION_ORDER = ["Repo", "News", "Regulatory"]
ACTION_WORDS = {
    "audit",
    "check",
    "decide",
    "inventory",
    "map",
    "pilot",
    "prioritize",
    "prototype",
    "rank",
    "review",
    "test",
    "validate",
}

GENERIC_ACTION_PHRASES = {
    "keep an eye",
    "monitor developments",
    "stay informed",
    "watch this space",
    "review whether this changes",
}

THIS_WEEK_TERMS = {
    "this week",
    "next 7",
    "next seven",
    "next sprint",
    "today",
    "tomorrow",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
}

RENDER_TITLE_STOPWORDS = {
    "and",
    "for",
    "from",
    "into",
    "news",
    "repo",
    "signal",
    "the",
    "this",
    "update",
    "with",
}

SENTENCE_ABBREVIATION_RE = re.compile(
    r"\b(?:[A-Za-z]\.){2,}|\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|Inc|Ltd|Corp|Co|vs|etc)\.",
    re.IGNORECASE,
)
SENTENCE_DOT_PLACEHOLDER = "<DOT>"


def render_signal_badge(signal: str) -> str:
    style = SIGNAL_STYLES.get(signal.lower(), SIGNAL_STYLES["medium"])
    return (
        f"<span style=\"display:inline-block; margin-bottom:8px; padding:4px 8px; "
        f"font-size:12px; font-weight:bold; border-radius:999px; "
        f"background:{style['bg']}; color:{style['color']};\">"
        f"{style['label']}</span>"
    )


def render_inline_badge(label: str, *, bg: str, color: str) -> str:
    return (
        f"<span style=\"display:inline-block; margin:0 6px 6px 0; padding:4px 8px; "
        f"font-size:11px; font-weight:700; border-radius:999px; "
        f"background:{bg}; color:{color}; letter-spacing:0.02em;\">"
        f"{escaped(label)}</span>"
    )


def render_reliability_badge(label: str) -> str:
    style = RELIABILITY_STYLES.get(label, RELIABILITY_STYLES["Medium"])
    return render_inline_badge(
        f"RELIABILITY {label.upper()}",
        bg=style["bg"],
        color=style["color"],
    )


def render_change_badge(change_status: str) -> str:
    style = CHANGE_STYLES.get(change_status, CHANGE_STYLES["repeated"])
    return render_inline_badge(style["label"], bg=style["bg"], color=style["color"])


def render_category_badge(category: str) -> str:
    return render_inline_badge(
        category.upper(),
        bg="#e0f2fe",
        color="#075985",
    )


def escaped(value: object) -> str:
    return escape(str(value or ""), quote=True)


def compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sentence_limited(value: object, max_sentences: int = 1) -> str:
    text = compact_text(value)
    if not text:
        return ""

    protected_text = SENTENCE_ABBREVIATION_RE.sub(
        lambda match: match.group(0).replace(".", SENTENCE_DOT_PLACEHOLDER),
        text,
    )
    sentences = [
        match.group(0).replace(SENTENCE_DOT_PLACEHOLDER, ".").strip()
        for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", protected_text)
        if match.group(0).strip()
    ]
    if not sentences:
        return text
    return " ".join(sentences[:max_sentences]).strip()


def normalized_words(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def singular_plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def sort_items_for_render(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        items,
        key=lambda item: (
            float(item.get("priority_score", 0.0) or 0.0),
            -rank.get(item.get("signal", "medium"), 1),
        ),
        reverse=True,
    )


def build_section_counts(items: List[Dict[str, str]]) -> Dict[str, int]:
    counts = {category: 0 for category in SECTION_ORDER}
    for item in items:
        category = item.get("category", "")
        if category in counts:
            counts[category] += 1
    return counts


def validate_digest_items(items: List[Dict[str, str]]) -> Dict[str, int]:
    unknown_categories = sorted(
        {item.get("category", "") for item in items if item.get("category", "") not in CATEGORY_HEADINGS}
    )
    if unknown_categories:
        raise ValueError(
            f"Unknown digest categories encountered during render: {', '.join(unknown_categories)}"
        )

    counts = build_section_counts(items)
    assert sum(counts.values()) == len(items), "Digest section counts do not match the rendered item count."
    return counts


def category_count_label(category: str, count: int) -> str:
    if category == "Repo":
        return f"{count} {'repo' if count == 1 else 'repos'}"
    if category == "News":
        return f"{count} {'news item' if count == 1 else 'news items'}"
    return f"{count} {'regulatory update' if count == 1 else 'regulatory updates'}"


def build_summary_line(counts: Dict[str, int]) -> str:
    return (
        f"{category_count_label('Repo', counts['Repo'])}, "
        f"{category_count_label('News', counts['News'])}, "
        f"and {category_count_label('Regulatory', counts['Regulatory'])}."
    )


def story_id_for_render(story: Dict[str, object]) -> str:
    return compact_text(
        story.get("story_id")
        or story.get("cluster_id")
        or story.get("canonical_url")
        or story.get("url")
        or story.get("cluster_title")
        or story.get("title")
    )


def story_title_for_render(story: Dict[str, object]) -> str:
    return compact_text(story.get("cluster_title") or story.get("title") or "Untitled story")


def story_url_for_render(story: Dict[str, object]) -> str:
    return compact_text(story.get("canonical_url") or story.get("url") or "#")


def render_title_tokens(story: Dict[str, object]) -> set[str]:
    return {
        token
        for token in normalized_words(story_title_for_render(story))
        if len(token) > 2 and token not in RENDER_TITLE_STOPWORDS
    }


def stories_are_render_duplicates(
    story: Dict[str, object],
    selected_stories: List[Dict[str, object]],
) -> bool:
    story_url = story_url_for_render(story)
    story_title = story_title_for_render(story).lower()
    story_tokens = render_title_tokens(story)

    for selected in selected_stories:
        if story_url != "#" and story_url == story_url_for_render(selected):
            return True
        if story_title and story_title == story_title_for_render(selected).lower():
            return True
        selected_tokens = render_title_tokens(selected)
        if story_tokens and selected_tokens:
            overlap = len(story_tokens & selected_tokens) / max(len(story_tokens), len(selected_tokens))
            if overlap >= 0.8:
                return True
    return False


def story_source_names(story: Dict[str, object]) -> List[str]:
    raw_sources = story.get("source_names") or []
    if not isinstance(raw_sources, list):
        raw_sources = [raw_sources]

    sources = [
        compact_text(source)
        for source in raw_sources
        if compact_text(source)
    ]
    fallback_source = compact_text(story.get("source") or story.get("source_name"))
    if fallback_source:
        sources.append(fallback_source)

    seen: set[str] = set()
    result: List[str] = []
    for source in sources:
        if source in seen:
            continue
        seen.add(source)
        result.append(source)
    return result


def story_confidence_label(story: Dict[str, object]) -> str:
    explicit_display = compact_text(story.get("confidence_display"))
    if explicit_display:
        return explicit_display
    return confidence_display_for_story(story)["confidence_display"]


def story_source_confidence_line(story: Dict[str, object]) -> str:
    sources = story_source_names(story)
    source_line = ", ".join(sources[:2]) if sources else "Unknown source"
    if len(sources) > 2:
        source_line += f" + {len(sources) - 2} more"

    return f"{source_line} | Confidence: {story_confidence_label(story)}"


def should_render_daily_action(story: Dict[str, object], action: str) -> bool:
    if story_confidence_label(story).lower() != "high":
        return False

    action_text = compact_text(action)
    normalized_action = action_text.lower()
    if len(action_text) < 20 or len(action_text) > 180:
        return False
    if any(phrase in normalized_action for phrase in GENERIC_ACTION_PHRASES):
        return False
    if not (ACTION_WORDS & normalized_words(action_text)):
        return False

    has_this_week_relevance = (
        any(term in normalized_action for term in THIS_WEEK_TERMS)
        or "by " in normalized_action
        or compact_text(story.get("near_term_actionability")).lower() == "high"
    )
    has_story_context = bool(story.get("workflow_wedges")) or compact_text(story.get("category")).lower() == "regulatory"
    return has_this_week_relevance and has_story_context


def story_float(story: Dict[str, object], key: str, default: float = 0.0) -> float:
    try:
        return float(story.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def story_int(story: Dict[str, object], key: str, default: int = 0) -> int:
    try:
        return int(story.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def story_objective_score(story: Dict[str, object], objective: str) -> float:
    raw_scores = story.get("objective_scores", {}) or {}
    if not isinstance(raw_scores, dict):
        return 0.0
    try:
        return float(raw_scores.get(objective, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def max_story_objective_score_for_render(story: Dict[str, object]) -> float:
    raw_scores = story.get("objective_scores", {}) or {}
    if not isinstance(raw_scores, dict):
        return 0.0
    values = []
    for value in raw_scores.values():
        try:
            values.append(float(value or 0.0))
        except (TypeError, ValueError):
            continue
    return max(values, default=0.0)


def story_list_values(story: Dict[str, object], key: str) -> List[str]:
    raw_values = story.get(key) or []
    if not isinstance(raw_values, list):
        raw_values = [raw_values]
    return [compact_text(value) for value in raw_values if compact_text(value)]


def story_is_low_signal_for_render(story: Dict[str, object]) -> bool:
    return story_is_low_signal_for_policy(story)


def story_has_material_signal_for_render(story: Dict[str, object]) -> bool:
    return story_has_material_signal_for_policy(story)


def story_signal_quality_for_render(story: Dict[str, object]) -> str:
    return story_signal_quality_for_policy(story)

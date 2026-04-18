from html import escape
import re
from typing import Dict, List

from signal_quality import classify_mapping_materiality
from state import local_now


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
DAILY_STORY_LIMIT = 4
DAILY_MIN_STORY_COUNT = 3
DAILY_BACKFILL_MIN_STORY_SCORE = 24.0
DAILY_BACKFILL_MIN_OBJECTIVE_SCORE = 5.8
DAILY_SINGLE_STORY_MIN_STORY_SCORE = 32.0
DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE = 6.4

DAILY_TARGET_THEME_KEYS = {
    "healthcare_ai_pm",
    "healthcare_admin_automation",
    "low_reg_friction_wedges",
    "llm_eval_rag_governance_safety",
}

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


def render_top_picks(top_picks: List[Dict[str, object]] | None) -> str:
    if isinstance(top_picks, dict):
        top_picks = [top_picks.get(objective, {}) for objective in ("career", "build", "content", "regulatory")]

    if not top_picks:
        return ""

    rows = []
    for pick in top_picks:
        item = pick.get("item", {}) or {}
        if pick.get("empty") or not item:
            rows.append(
                f"""
                <p style="margin: 0 0 8px 0;">
                  <strong>{escaped(pick.get('label', 'Top pick'))}:</strong>
                  <span style="color: #555;">{escaped(pick.get('message', 'No qualifying item today.'))}</span>
                </p>
                """
            )
            continue
        rows.append(
            f"""
            <p style="margin: 0 0 8px 0;">
              <strong>{escaped(pick.get('label', 'Top pick'))}:</strong>
              <a href="{escaped(item.get('url', '#'))}" style="color: #0b57d0; text-decoration: none; font-weight: 600;">
                {escaped(item.get('title', 'Untitled'))}
              </a>
              {'<span style="color:#555;"> (reused with intent)</span>' if pick.get('reused') else ''}
            </p>
            """
        )

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #d6e4ff; border-radius: 10px; background: #f8fbff;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #0b57d0; letter-spacing: 0.02em;">
            TOP PICKS BY OBJECTIVE
          </p>
          {''.join(rows)}
        </div>
    """


def render_action_footer(action_brief: Dict[str, str] | None) -> str:
    if not action_brief:
        return ""

    action_labels = [
        ("content_angle", "Content angle"),
        ("build_idea", "Build idea"),
        ("interview_talking_point", "Interview talking point"),
        ("watch_item", "Watch"),
    ]
    rows = []
    for key, label in action_labels:
        value = str(action_brief.get(key, "") or "").strip()
        if not value:
            continue
        rows.append(
            f"<p style=\"margin: 0 0 8px 0;\"><strong>{escaped(label)}:</strong> {escaped(value)}</p>"
        )

    if not rows:
        return ""

    return f"""
        <div style="margin: 20px 0 8px 0; padding: 14px 16px; border-left: 4px solid #0f766e; background: #f0fdfa;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #0f766e; letter-spacing: 0.02em;">
            OPERATOR MOVES
          </p>
          {''.join(rows)}
        </div>
    """


def render_change_section(entries: List[Dict[str, object]] | None) -> str:
    if not entries:
        return ""

    rows = []
    for entry in entries:
        rows.append(
            f"""
            <p style="margin: 0 0 10px 0;">
              <strong>{escaped(entry.get('change_type', 'Change'))}:</strong>
              {escaped(entry.get('detail', ''))}
            </p>
            """
        )

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #bfdbfe; border-radius: 10px; background: #f8fbff;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #1d4ed8; letter-spacing: 0.02em;">
            WHAT CHANGED SINCE YESTERDAY
          </p>
          {''.join(rows)}
        </div>
    """


def render_thesis_tracker(entries: List[Dict[str, object]] | None) -> str:
    if not entries:
        return ""

    rows = []
    for entry in entries[:4]:
        evidence = ", ".join(
            escaped(item.get("cluster_title", ""))
            for item in (entry.get("evidence", []) or [])[:2]
            if str(item.get("cluster_title", "")).strip()
        )
        rows.append(
            f"""
            <p style="margin: 0 0 10px 0;">
              <strong>{escaped(entry.get('title', 'Thesis'))}</strong>
              <span style="color:#0f766e;">[{escaped(str(entry.get('status', '')).upper())}]</span><br/>
              <span style="color:#444;">Evidence: {evidence or 'No concrete story attached.'}</span>
            </p>
            """
        )

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #99f6e4; border-radius: 10px; background: #f0fdfa;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #0f766e; letter-spacing: 0.02em;">
            THESIS TRACKER
          </p>
          {''.join(rows)}
        </div>
    """


def render_market_map(market_map: Dict[str, object] | None) -> str:
    if not market_map:
        return ""

    hot = market_map.get("hot_zones", []) or []
    quiet = market_map.get("quiet_zones", []) or []
    spillover = market_map.get("spillover", []) or []

    rows = []
    if hot:
        rows.append(
            "<p style=\"margin:0 0 8px 0;\"><strong>Hot:</strong> "
            + ", ".join(
                escaped(f"{entry.get('label', '')} ({entry.get('delta_vs_yesterday', 0):+g})")
                for entry in hot
            )
            + "</p>"
        )
    if quiet:
        rows.append(
            "<p style=\"margin:0 0 8px 0;\"><strong>Quiet:</strong> "
            + ", ".join(
                escaped(f"{entry.get('label', '')} ({entry.get('delta_vs_yesterday', 0):+g})")
                for entry in quiet
            )
            + "</p>"
        )
    if spillover:
        rows.append(
            "<p style=\"margin:0;\"><strong>Cross-category spillover:</strong> "
            + ", ".join(
                escaped(item.get("cluster_title", ""))
                for item in spillover
            )
            + "</p>"
        )

    if not rows:
        return ""

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #e9d5ff; border-radius: 10px; background: #faf5ff;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #7c3aed; letter-spacing: 0.02em;">
            MARKET MAP PULSE
          </p>
          {''.join(rows)}
        </div>
    """


def render_watchlist_hits(entries: List[Dict[str, object]] | None) -> str:
    if not entries:
        return ""

    rows = []
    for entry in entries:
        match_text = ", ".join(
            escaped(f"{match.get('type', '')}: {match.get('value', '')}")
            for match in (entry.get("matches", []) or [])[:3]
        )
        rows.append(
            f"""
            <p style="margin: 0 0 10px 0;">
              <strong>{escaped(entry.get('cluster_title', 'Watched repo'))}</strong>
              <span style="color:#555;">[{escaped(str(entry.get('status', '')).upper())}]</span><br/>
              <span style="color:#444;">Matches: {match_text}</span>
            </p>
            """
        )

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #d9f99d; border-radius: 10px; background: #f7fee7;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: bold; color: #4d7c0f; letter-spacing: 0.02em;">
            WATCHED REPOS
          </p>
          {''.join(rows)}
        </div>
    """


def render_quality_flags(quality_eval: Dict[str, object] | None) -> str:
    if not quality_eval:
        return ""

    metrics = quality_eval.get("metrics", {}) or {}
    warnings = quality_eval.get("warnings", []) or []
    metric_line = ", ".join(
        f"{label}: {metrics.get(key, 0)}"
        for key, label in [
            ("signal_to_noise", "Signal/noise"),
            ("novelty", "Novelty"),
            ("source_quality", "Source quality"),
            ("objective_separation", "Objective separation"),
        ]
    )

    warning_rows = "".join(
        f"<p style=\"margin:0 0 8px 0; color:#7f1d1d;\">{escaped(str(warning))}</p>"
        for warning in warnings[:4]
    )

    return f"""
        <div style="margin: 18px 0 16px 0; padding: 14px 16px; border: 1px solid #fecaca; border-radius: 10px; background: #fef2f2;">
          <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: bold; color: #b91c1c; letter-spacing: 0.02em;">
            DIGEST QUALITY
          </p>
          <p style="margin: 0 0 10px 0; color:#444;">{escaped(metric_line)}</p>
          {warning_rows if warning_rows else '<p style="margin:0; color:#166534;">No major quality warnings triggered today.</p>'}
        </div>
    """


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
    label = compact_text(story.get("confidence") or story.get("reliability_label") or "Medium")
    signal_quality = story_signal_quality_for_render(story)
    if story_is_low_signal_for_render(story) or signal_quality == "weak":
        return "Low"
    if signal_quality == "medium" and label == "High":
        return "Medium"
    return label


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


def daily_backfill_has_target_fit(story: Dict[str, object]) -> bool:
    category = compact_text(story.get("category"))
    operator_relevance = compact_text(story.get("operator_relevance") or "low").lower()
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    workflow_wedges = story_list_values(story, "workflow_wedges")
    matched_themes = set(story_list_values(story, "matched_themes"))
    max_objective = max_story_objective_score_for_render(story)
    has_watchlist_match = bool(story.get("watchlist_matches"))

    if bool(story.get("docs_only_repo")):
        return False
    if story_is_low_signal_for_render(story) or story_signal_quality_for_render(story) == "weak":
        return False

    if category == "Regulatory":
        regulatory_score = story_objective_score(story, "regulatory")
        return (
            regulatory_score >= 6.1
            or bool(workflow_wedges)
            or operator_relevance in {"high", "medium"}
        )

    if category == "Repo":
        is_generic = bool(story.get("is_generic_devtool"))
        is_exempt = bool(story.get("generic_repo_cap_exempt"))
        if is_generic and not is_exempt:
            return has_watchlist_match or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_objective >= 7.2
                and actionability != "low"
            )
        return (
            has_watchlist_match
            or bool(workflow_wedges)
            or operator_relevance == "high"
            or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_objective >= DAILY_BACKFILL_MIN_OBJECTIVE_SCORE
                and actionability != "low"
            )
        )

    if category == "News":
        return (
            operator_relevance in {"high", "medium"}
            and (
                bool(workflow_wedges)
                or actionability in {"high", "medium"}
                or bool(matched_themes & DAILY_TARGET_THEME_KEYS)
            )
        )

    return False


def daily_backfill_story_is_worthy(story: Dict[str, object]) -> bool:
    if not daily_backfill_has_target_fit(story):
        return False
    if compact_text(story.get("reliability_label")).lower() == "low" and story_int(story, "supporting_item_count") < 2:
        return False

    story_score = story_float(story, "story_score", story_float(story, "priority_score"))
    max_objective = max_story_objective_score_for_render(story)
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    support_count = story_int(story, "supporting_item_count")

    return (
        story_score >= DAILY_BACKFILL_MIN_STORY_SCORE
        or max_objective >= DAILY_BACKFILL_MIN_OBJECTIVE_SCORE
        or (support_count >= 2 and actionability in {"high", "medium"})
    )


def story_materiality_for_render(story: Dict[str, object]) -> Dict[str, object]:
    return classify_mapping_materiality(story)


def story_is_low_signal_for_render(story: Dict[str, object]) -> bool:
    if "low_signal_announcement" in story:
        return bool(story.get("low_signal_announcement"))
    return bool(story_materiality_for_render(story)["low_signal_announcement"])


def story_has_material_signal_for_render(story: Dict[str, object]) -> bool:
    if "material_operator_signal" in story:
        return bool(story.get("material_operator_signal"))
    return bool(story_materiality_for_render(story)["material_operator_signal"])


def story_signal_quality_for_render(story: Dict[str, object]) -> str:
    explicit = compact_text(story.get("signal_quality")).lower()
    if explicit in {"strong", "medium", "weak"}:
        return explicit
    return compact_text(story_materiality_for_render(story)["signal_quality"]).lower()


def daily_story_passes_render_quality(story: Dict[str, object]) -> bool:
    return not story_is_low_signal_for_render(story) and story_signal_quality_for_render(story) != "weak"


def single_daily_story_is_worthy(story: Dict[str, object]) -> bool:
    if not daily_story_passes_render_quality(story):
        return False

    story_score = story_float(story, "story_score", story_float(story, "priority_score"))
    max_objective = max_story_objective_score_for_render(story)
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    support_count = story_int(story, "supporting_item_count", 1)
    has_score_evidence = (
        "story_score" in story
        or "priority_score" in story
        or bool(story.get("objective_scores"))
    )

    if story_has_material_signal_for_render(story):
        if not has_score_evidence:
            return True
        return (
            story_score >= DAILY_SINGLE_STORY_MIN_STORY_SCORE
            or max_objective >= DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE
            or support_count >= 2
        )

    return (
        story_score >= DAILY_SINGLE_STORY_MIN_STORY_SCORE
        and max_objective >= DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE
        and actionability == "high"
    )


def daily_backfill_rank(story: Dict[str, object]) -> tuple[float, float, int, int, str]:
    return (
        story_float(story, "story_score", story_float(story, "priority_score")),
        max_story_objective_score_for_render(story),
        story_int(story, "reliability_score"),
        story_int(story, "supporting_item_count"),
        story_title_for_render(story),
    )


def append_daily_story(
    story: Dict[str, object],
    selected: List[Dict[str, object]],
    seen: set[str],
) -> bool:
    story_id = story_id_for_render(story)
    if story_id and story_id in seen:
        return False
    if stories_are_render_duplicates(story, selected):
        return False
    if story_id:
        seen.add(story_id)
    selected.append(story)
    return True


def select_daily_stories(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> List[Dict[str, object]]:
    story_limit = max(1, story_limit)
    story_cards = operator_brief.get("story_cards")
    all_stories = [
        story
        for story in (operator_brief.get("stories", []) or [])
        if isinstance(story, dict)
    ]
    primary_candidates = story_cards if isinstance(story_cards, list) else all_stories
    candidates = [
        story
        for story in (primary_candidates or [])
        if isinstance(story, dict)
    ]

    selected: List[Dict[str, object]] = []
    seen: set[str] = set()
    for story in candidates:
        if not daily_story_passes_render_quality(story):
            continue
        append_daily_story(story, selected, seen)
        if len(selected) >= story_limit:
            break

    # Daily emails should not collapse to a single card when the broader story board
    # still has credible near-misses. Story cards remain the primary path; this
    # fallback only fills a thin daily render with conservative, target-fit stories.
    backfill_target = min(story_limit, DAILY_MIN_STORY_COUNT)
    if isinstance(story_cards, list) and len(selected) < backfill_target:
        backfill_candidates = [
            story
            for story in all_stories
            if daily_backfill_story_is_worthy(story)
        ]
        for story in sorted(backfill_candidates, key=daily_backfill_rank, reverse=True):
            append_daily_story(story, selected, seen)
            if len(selected) >= backfill_target:
                break

    if len(selected) == 1 and not single_daily_story_is_worthy(selected[0]):
        return []

    return selected


def build_daily_story_header(
    operator_brief: Dict[str, object],
    stories: List[Dict[str, object]],
) -> str:
    summary = operator_brief.get("summary", {}) or {}
    # Legacy artifacts call this raw_item_count, but the value is the number of
    # post-fetch, screened items that entered the operator brief.
    screened_count = int(summary.get("raw_item_count", 0) or 0)
    if screened_count <= 0:
        screened_count = len(stories)

    counts = {category: 0 for category in SECTION_ORDER}
    for story in stories:
        category = compact_text(story.get("category"))
        if category in counts:
            counts[category] += 1

    category_parts = [
        category_count_label(category, count)
        for category, count in counts.items()
        if count
    ]
    screened_label = singular_plural(screened_count, "screened item")
    if not stories:
        return f"No strong signal today from {screened_label}."
    if len(category_parts) == 1:
        category = next(category for category, count in counts.items() if count)
        category_story_label = {
            "Repo": ("repo story", "repo stories"),
            "News": ("news story", "news stories"),
            "Regulatory": ("regulatory story", "regulatory stories"),
        }[category]
        return (
            f"{singular_plural(len(stories), category_story_label[0], category_story_label[1])} "
            f"selected from {screened_label}."
        )

    category_tail = f" ({', '.join(category_parts)})" if category_parts else ""
    return (
        f"{singular_plural(len(stories), 'story', 'stories')} selected from "
        f"{screened_label}{category_tail}."
    )


def render_daily_headlines(stories: List[Dict[str, object]]) -> str:
    if not stories:
        return """
        <p style="margin: 8px 0 14px 0; color:#555;">No operator-grade stories cleared today's quality bar.</p>
        """
    if len(stories) == 1:
        return ""

    return f"""
        <p style="margin: 12px 0 8px 0; font-size: 12px; font-weight: 700; color:#555; letter-spacing: 0.02em;">
          HEADLINES
        </p>
    """


def render_daily_story_cards(stories: List[Dict[str, object]]) -> str:
    if not stories:
        return ""

    cards = []
    for story in stories:
        summary = sentence_limited(story.get("summary"), 1)
        why_it_matters = sentence_limited(story.get("why_it_matters"), 1)
        action = sentence_limited(story.get("action_suggestion"), 1).rstrip(".!?")
        action_line = ""
        if action and should_render_daily_action(story, action):
            action_line = f"""
              <p style="margin: 0 0 8px 0;"><strong>Action:</strong> {escaped(action)}</p>
            """

        cards.append(
            f"""
            <div style="padding: 14px 0; border-top: 1px solid #e5e7eb;">
              <p style="margin: 0 0 4px 0; font-size: 17px; font-weight: 700; line-height: 1.3;">
                {escaped(story_title_for_render(story))}
              </p>
              <p style="margin: 0 0 8px 0; color:#555; font-size: 13px;">
                {escaped(story_source_confidence_line(story))}
              </p>
              <p style="margin: 0 0 8px 0;"><strong>Summary:</strong> {escaped(summary)}</p>
              <p style="margin: 0 0 8px 0;"><strong>Why it matters:</strong> {escaped(why_it_matters)}</p>
              {action_line}
              <p style="margin: 0;">
                <a href="{escaped(story_url_for_render(story))}" style="color:#0b57d0; text-decoration:none; font-weight:700;">Link</a>
              </p>
            </div>
            """
        )

    return f"""
        <div style="margin: 0;">
          {''.join(cards)}
        </div>
    """


def render_weekly_story_cards(stories: List[Dict[str, object]] | None) -> str:
    if not stories:
        return ""

    cards = []
    for story in stories:
        supporting_sources = ", ".join(
            escaped(source_name)
            for source_name in (story.get("source_names", []) or [])[:3]
        )
        thesis_line = ", ".join(
            escaped(f"{link.get('title', '')} [{str(link.get('relation', '')).upper()}]")
            for link in (story.get("thesis_links", []) or [])[:2]
        )
        market_line = ", ".join(escaped(bucket) for bucket in (story.get("market_buckets", []) or [])[:3])
        badges = (
            render_category_badge(str(story.get("category", "")))
            + render_change_badge(str(story.get("change_status", "")))
            + render_signal_badge(str(story.get("signal", "medium")))
            + render_reliability_badge(str(story.get("reliability_label", "Medium")))
        )
        cards.append(
            f"""
            <div style="margin-bottom: 20px; padding: 16px; border: 1px solid #e5e7eb; border-radius: 12px; background: #ffffff;">
              <div style="margin-bottom: 6px;">{badges}</div>
              <p style="margin: 0 0 6px 0;">
                <a href="{escaped(story.get('canonical_url', '#'))}" style="font-size: 17px; font-weight: bold; color: #0b57d0; text-decoration: none;">
                  {escaped(story.get('cluster_title', 'Untitled story'))}
                </a>
              </p>
              <p style="margin: 0 0 8px 0; color:#444;">
                <strong>Supporting sources:</strong> {supporting_sources or 'None'}.
                <strong>Confidence:</strong> {escaped(story_confidence_label(story))}.
              </p>
              <p style="margin: 0 0 8px 0;">{escaped(story.get('summary', ''))}</p>
              <p style="margin: 0 0 8px 0; color: #444;"><strong>Why it matters:</strong> {escaped(story.get('why_it_matters', ''))}</p>
              <p style="margin: 0 0 8px 0; color: #444;"><strong>Action:</strong> {escaped(story.get('action_suggestion', ''))}</p>
              {'<p style="margin: 0 0 6px 0; color:#555;"><strong>Market buckets:</strong> ' + market_line + '</p>' if market_line else ''}
              {'<p style="margin: 0; color:#555;"><strong>Thesis links:</strong> ' + thesis_line + '</p>' if thesis_line else ''}
            </div>
            """
        )

    return f"""
        <div style="margin: 20px 0 8px 0;">
          <p style="margin: 0 0 12px 0; font-size: 13px; font-weight: bold; color: #0b57d0; letter-spacing: 0.02em;">
            OPERATOR STORY BOARD
          </p>
          {''.join(cards)}
        </div>
    """


def format_daily_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    date_str = local_now().strftime("%B %d, %Y")
    stories = select_daily_stories(operator_brief, story_limit=story_limit)

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.42; color: #222; max-width: 680px; margin: 0 auto; padding: 12px; background: #ffffff;">
        <h2 style="margin: 0 0 4px 0; font-size: 22px; line-height: 1.25;">Daily AI Digest - {date_str}</h2>
        <p style="margin: 0 0 8px 0; color:#444;">{escaped(build_daily_story_header(operator_brief, stories))}</p>
        {render_daily_headlines(stories)}
        {render_daily_story_cards(stories)}
      </body>
    </html>
    """
    return html


def format_weekly_operator_brief_html(operator_brief: Dict[str, object]) -> str:
    date_str = local_now().strftime("%B %d, %Y")
    summary = operator_brief.get("summary", {}) or {}
    operator_moves = operator_brief.get("operator_moves", {}) or {}
    story_cards = operator_brief.get("story_cards", []) or []

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222; max-width: 860px; margin: 0 auto; padding: 12px; background: #f8fafc;">
        <h2 style="margin-bottom: 8px;">Weekly AI Digest - Operator Review</h2>
        <p style="margin-top: 0;"><strong>Date:</strong> {date_str}</p>
        <p style="margin: 0 0 16px 0;">
          {escaped(str(summary.get('raw_item_count', 0)))} screened items organized into
          {escaped(str(summary.get('story_count', 0)))} story clusters, with
          {escaped(str(summary.get('story_card_count', 0)))} surfaced in the email.
        </p>
        {render_change_section(operator_brief.get("what_changed", []) or [])}
        {render_top_picks(operator_brief.get("top_picks", {}) or {})}
        {render_thesis_tracker(operator_brief.get("thesis_tracker", []) or [])}
        {render_market_map(operator_brief.get("market_map", {}) or {})}
        {render_watchlist_hits(operator_brief.get("watchlist_hits", []) or [])}
        <div style="margin: 18px 0 24px 0; padding: 14px 16px; border-left: 4px solid #0b57d0; background: #eff6ff;">
          <p style="margin: 0 0 6px 0; font-size: 13px; font-weight: bold; color: #0b57d0; letter-spacing: 0.02em;">
            TOP INSIGHT
          </p>
          <p style="margin: 0; font-size: 16px;">{escaped(operator_moves.get('top_insight', ''))}</p>
        </div>
        {render_weekly_story_cards(story_cards)}
        {render_action_footer(operator_moves)}
        {render_quality_flags(operator_brief.get("quality_eval", {}) or {})}
      </body>
    </html>
    """
    return html


def format_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    mode: str = "daily",
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    normalized_mode = compact_text(mode).lower() or "daily"
    if normalized_mode == "daily":
        return format_daily_operator_brief_html(operator_brief, story_limit=story_limit)
    if normalized_mode == "weekly":
        return format_weekly_operator_brief_html(operator_brief)
    raise ValueError("mode must be 'daily' or 'weekly'.")


def format_operator_cockpit_html(operator_brief: Dict[str, object]) -> str:
    return format_weekly_operator_brief_html(operator_brief)


def format_digest_html(
    items: List[Dict[str, str]],
    top_insight: str,
    top_picks: List[Dict[str, object]] | None = None,
    action_brief: Dict[str, str] | None = None,
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    counts = validate_digest_items(items)
    sorted_items = sort_items_for_render(items)
    surfaced_items = sorted_items[: max(1, story_limit)]
    stories: List[Dict[str, object]] = []
    for item in surfaced_items:
        confidence = compact_text(item.get("confidence") or item.get("signal", "medium")).title()
        stories.append(
            {
                "cluster_title": item.get("title", "Untitled"),
                "canonical_url": item.get("url", "#"),
                "source_names": [item.get("source") or CATEGORY_HEADINGS.get(item.get("category", ""), "Unknown source")],
                "confidence": confidence,
                "summary": item.get("summary", ""),
                "why_it_matters": item.get("why_it_matters", ""),
                "category": item.get("category", ""),
                "priority_score": item.get("priority_score", 0.0),
            }
        )
    date_str = local_now().strftime("%B %d, %Y")
    header = f"Showing {singular_plural(len(stories), 'story', 'stories')} from {singular_plural(len(items), 'item')}: {build_summary_line(counts)}"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.42; color: #222; max-width: 680px; margin: 0 auto; padding: 12px;">
        <h2 style="margin: 0 0 4px 0; font-size: 22px; line-height: 1.25;">Daily AI Digest - {date_str}</h2>
        <p style="margin: 0 0 8px 0; color:#444;">{escaped(header)}</p>
        {render_daily_headlines(stories)}
        {render_daily_story_cards(stories)}
      </body>
    </html>
    """
    return html

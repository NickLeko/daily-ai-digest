from collections import defaultdict
from html import escape
from typing import Dict, List

from state import local_now


CATEGORY_HEADINGS = {
    "Repo": "Repos",
    "News": "News",
    "Regulatory": "Regulatory Updates",
}

EMPTY_SECTION_MESSAGES = {
    "Repo": "No qualifying repositories were available today.",
    "News": "No high-signal general AI/healthcare news passed filters today.",
    "Regulatory": "No high-signal regulatory updates passed filters today.",
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
        f"and {category_count_label('Regulatory', counts['Regulatory'])}. "
        "Concise and signal-heavy."
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


def render_story_cards(stories: List[Dict[str, object]] | None) -> str:
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
                <strong>Confidence:</strong> {escaped(story.get('confidence', 'Medium'))}.
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


def format_operator_brief_html(operator_brief: Dict[str, object]) -> str:
    date_str = local_now().strftime("%B %d, %Y")
    summary = operator_brief.get("summary", {}) or {}
    operator_moves = operator_brief.get("operator_moves", {}) or {}
    story_cards = operator_brief.get("story_cards", []) or []

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222; max-width: 860px; margin: 0 auto; padding: 12px; background: #f8fafc;">
        <h2 style="margin-bottom: 8px;">Daily AI Digest v2: Operator Cockpit</h2>
        <p style="margin-top: 0;"><strong>Date:</strong> {date_str}</p>
        <p style="margin: 0 0 16px 0;">
          {escaped(str(summary.get('raw_item_count', 0)))} raw signals normalized into
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
        {render_story_cards(story_cards)}
        {render_action_footer(operator_moves)}
        {render_quality_flags(operator_brief.get("quality_eval", {}) or {})}
      </body>
    </html>
    """
    return html


def format_operator_cockpit_html(operator_brief: Dict[str, object]) -> str:
    return format_operator_brief_html(operator_brief)


def format_digest_html(
    items: List[Dict[str, str]],
    top_insight: str,
    top_picks: List[Dict[str, object]] | None = None,
    action_brief: Dict[str, str] | None = None,
) -> str:
    counts = validate_digest_items(items)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        grouped[item["category"]].append(item)

    date_str = local_now().strftime("%B %d, %Y")

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222; max-width: 800px; margin: 0 auto; padding: 12px;">
        <h2>Daily AI Digest v2</h2>
        <p><strong>Date:</strong> {date_str}</p>
        <p>{build_summary_line(counts)}</p>

        {render_top_picks(top_picks)}
        <div style="margin: 18px 0 24px 0; padding: 14px 16px; border-left: 4px solid #0b57d0; background: #f8fbff;">
          <p style="margin: 0 0 6px 0; font-size: 13px; font-weight: bold; color: #0b57d0; letter-spacing: 0.02em;">
            TOP INSIGHT
          </p>
          <p style="margin: 0; font-size: 16px;">{escaped(top_insight)}</p>
        </div>
    """

    for category in SECTION_ORDER:
        heading = CATEGORY_HEADINGS.get(category, category)
        html += f"<h3>{heading}</h3>"

        sorted_items = sort_items_for_render(grouped.get(category, []))
        if not sorted_items:
            html += (
                f"<p style=\"margin: 0 0 16px 0; color: #666;\">"
                f"<em>{escaped(EMPTY_SECTION_MESSAGES[category])}</em>"
                f"</p>"
            )
            continue

        for item in sorted_items:
            badge_html = render_signal_badge(item.get("signal", "medium"))
            html += f"""
            <div style="margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #ddd;">
              {badge_html}
              <p style="margin: 0 0 6px 0;">
                <a href="{escaped(item['url'])}" style="font-size: 16px; font-weight: bold; color: #0b57d0; text-decoration: none;">
                  {escaped(item['title'])}
                </a>
              </p>
              <p style="margin: 0 0 8px 0;">{escaped(item['summary'])}</p>
              <p style="margin: 0; color: #444;"><strong>Why it matters:</strong> {escaped(item['why_it_matters'])}</p>
            </div>
            """

    html += render_action_footer(action_brief)
    html += """
      </body>
    </html>
    """
    return html

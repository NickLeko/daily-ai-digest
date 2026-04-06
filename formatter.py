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

SECTION_ORDER = ["Repo", "News", "Regulatory"]


def render_signal_badge(signal: str) -> str:
    style = SIGNAL_STYLES.get(signal.lower(), SIGNAL_STYLES["medium"])
    return (
        f"<span style=\"display:inline-block; margin-bottom:8px; padding:4px 8px; "
        f"font-size:12px; font-weight:bold; border-radius:999px; "
        f"background:{style['bg']}; color:{style['color']};\">"
        f"{style['label']}</span>"
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

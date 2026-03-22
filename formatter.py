from collections import defaultdict
from datetime import datetime
from typing import Dict, List


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


def render_signal_badge(signal: str) -> str:
    style = SIGNAL_STYLES.get(signal.lower(), SIGNAL_STYLES["medium"])
    return (
        f"<span style=\"display:inline-block; margin-bottom:8px; padding:4px 8px; "
        f"font-size:12px; font-weight:bold; border-radius:999px; "
        f"background:{style['bg']}; color:{style['color']};\">"
        f"{style['label']}</span>"
    )


def sort_items_by_signal(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda x: rank.get(x.get("signal", "medium"), 1))


def format_digest_html(items: List[Dict[str, str]], top_insight: str) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        grouped[item["category"]].append(item)

    date_str = datetime.now().strftime("%B %d, %Y")

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222; max-width: 800px; margin: 0 auto; padding: 12px;">
        <h2>Daily AI Digest</h2>
        <p><strong>Date:</strong> {date_str}</p>
        <p>3 repos, 3 news items, and 3 regulatory updates. Concise and signal-heavy.</p>

        <div style="margin: 18px 0 24px 0; padding: 14px 16px; border-left: 4px solid #0b57d0; background: #f8fbff;">
          <p style="margin: 0 0 6px 0; font-size: 13px; font-weight: bold; color: #0b57d0; letter-spacing: 0.02em;">
            TOP INSIGHT
          </p>
          <p style="margin: 0; font-size: 16px;">{top_insight}</p>
        </div>
    """

    for category in ["Repo", "News", "Regulatory"]:
        heading = CATEGORY_HEADINGS.get(category, category)
        html += f"<h3>{heading}</h3>"

        sorted_items = sort_items_by_signal(grouped.get(category, []))
        for item in sorted_items:
            badge_html = render_signal_badge(item.get("signal", "medium"))
            html += f"""
            <div style="margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #ddd;">
              {badge_html}
              <p style="margin: 0 0 6px 0;">
                <a href="{item['url']}" style="font-size: 16px; font-weight: bold; color: #0b57d0; text-decoration: none;">
                  {item['title']}
                </a>
              </p>
              <p style="margin: 0 0 8px 0;">{item['summary']}</p>
              <p style="margin: 0; color: #444;"><strong>Why it matters:</strong> {item['why_it_matters']}</p>
            </div>
            """

    html += """
      </body>
    </html>
    """
    return html
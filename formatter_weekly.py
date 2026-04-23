from __future__ import annotations

from typing import Callable, Dict, List

from state import local_now

from formatter_shared import (
    compact_text,
    escaped,
    render_category_badge,
    render_change_badge,
    render_reliability_badge,
    render_signal_badge,
    story_confidence_label,
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


def format_weekly_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    now_fn: Callable[[], object] = local_now,
) -> str:
    date_str = now_fn().strftime("%B %d, %Y")
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

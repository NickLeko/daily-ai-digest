import difflib
import unittest
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from formatter import format_operator_brief_html


FIXED_NOW = datetime(2026, 4, 9, 16, 0, tzinfo=timezone.utc)
SNAPSHOT_DIR = Path(__file__).with_name("snapshots")


class SemanticHTMLSnapshotParser(HTMLParser):
    PRESERVED_ATTRS = {"a": {"href"}}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.lines.append(f"{self._indent()}<{tag}{self._format_attrs(tag, attrs)}>")
        self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.depth = max(0, self.depth - 1)
        self.lines.append(f"{self._indent()}</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.lines.append(f"{self._indent()}<{tag}{self._format_attrs(tag, attrs)} />")

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.lines.append(f"{self._indent()}{text}")

    def _indent(self) -> str:
        return "  " * self.depth

    def _format_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        preserved = self.PRESERVED_ATTRS.get(tag, set())
        rendered = [
            f'{name}="{escape(value or "", quote=True)}"'
            for name, value in attrs
            if name in preserved
        ]
        return f" {' '.join(rendered)}" if rendered else ""


def normalize_rendered_html(html: str) -> str:
    parser = SemanticHTMLSnapshotParser()
    parser.feed(html)
    parser.close()
    return "\n".join(parser.lines) + "\n"


def story_card(
    *,
    story_id: str,
    title: str,
    url: str,
    category: str,
    source_names: list[str],
    confidence: str,
    reliability_label: str,
    action_suggestion: str,
    change_status: str,
    signal: str,
    market_buckets: list[str],
    thesis_links: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "story_id": story_id,
        "title": title,
        "url": url,
        "cluster_title": title,
        "canonical_url": url,
        "source_names": source_names,
        "confidence": confidence,
        "reliability_label": reliability_label,
        "summary": f"{title} summary. Weekly-only detail should not appear in daily.",
        "why_it_matters": f"{title} matters to operator planning. Weekly-only context should not appear in daily.",
        "action_suggestion": action_suggestion,
        "category": category,
        "workflow_wedges": ["prior auth"],
        "near_term_actionability": "high",
        "change_status": change_status,
        "signal": signal,
        "market_buckets": market_buckets,
        "thesis_links": thesis_links,
    }


def operator_brief_fixture() -> dict[str, object]:
    regulatory_story = story_card(
        story_id="cms-prior-auth-final-rule",
        title="CMS final rule tightens prior auth evidence exchange",
        url="https://www.cms.gov/example/prior-auth-final-rule",
        category="Regulatory",
        source_names=["CMS Newsroom", "Federal Register"],
        confidence="High",
        reliability_label="High",
        action_suggestion="Audit one prior auth evidence handoff this week against the new CMS fields.",
        change_status="escalating",
        signal="high",
        market_buckets=["Prior auth", "Interoperability"],
        thesis_links=[
            {
                "title": "Prior auth is becoming workflow infrastructure",
                "relation": "supports",
            }
        ],
    )
    repo_story = story_card(
        story_id="audit-lane-repo",
        title="Audit-lane repo packages prior-auth evidence checks",
        url="https://github.com/example/audit-lane",
        category="Repo",
        source_names=["GitHub Search"],
        confidence="High",
        reliability_label="Medium",
        action_suggestion="Prototype a narrow audit lane by Friday using one denial category.",
        change_status="new",
        signal="high",
        market_buckets=["Eval tooling", "Prior auth"],
        thesis_links=[
            {
                "title": "Healthcare evals need operator-owned audit trails",
                "relation": "supports",
            }
        ],
    )
    news_story = story_card(
        story_id="payer-ai-governance-roles",
        title="Payer operations roles ask for AI governance fluency",
        url="https://example.com/career/payer-ai-governance",
        category="News",
        source_names=["Healthcare Jobs Weekly"],
        confidence="Medium",
        reliability_label="Medium",
        action_suggestion="Map three interview stories to governance, workflow, and measurement examples.",
        change_status="repeated",
        signal="medium",
        market_buckets=["Career"],
        thesis_links=[],
    )

    return {
        "summary": {
            "raw_item_count": 6,
            "story_count": 3,
            "story_card_count": 3,
        },
        "what_changed": [
            {
                "change_type": "Escalating",
                "detail": "Prior authorization automation moved from pilot notes into CMS operating guidance.",
            },
        ],
        "top_picks": {
            "career": {"label": "Top item for career", "item": news_story},
            "build": {"label": "Top item for build", "item": repo_story},
            "content": {"label": "Top item for content", "item": news_story},
            "regulatory": {"label": "Top item for regulatory", "item": regulatory_story},
        },
        "thesis_tracker": [
            {
                "title": "Prior auth is becoming workflow infrastructure",
                "status": "strengthening",
                "evidence": [
                    {"cluster_title": regulatory_story["cluster_title"]},
                    {"cluster_title": repo_story["cluster_title"]},
                ],
            },
        ],
        "market_map": {
            "hot_zones": [{"label": "Prior auth", "delta_vs_yesterday": 2}],
            "quiet_zones": [{"label": "Generic agent demos", "delta_vs_yesterday": -2}],
            "spillover": [{"cluster_title": regulatory_story["cluster_title"]}],
        },
        "watchlist_hits": [
            {
                "cluster_title": "audit-lane",
                "status": "new",
                "matches": [{"type": "repo", "value": "github.com/example/audit-lane"}],
            },
        ],
        "operator_moves": {
            "top_insight": "Prior auth is the clearest wedge because policy, payer operations, and eval tooling all point at auditable evidence exchange.",
            "content_angle": "Write about why evidence exchange beats generic agent demos for healthcare operators.",
            "build_idea": "Prototype an intake-to-appeal audit lane for one prior-auth workflow.",
        },
        "story_cards": [regulatory_story, repo_story, news_story],
        "quality_eval": {
            "metrics": {
                "signal_to_noise": 4,
                "novelty": 4,
                "source_quality": 5,
                "objective_separation": 4,
            },
            "warnings": ["Recheck the jobs signal before using it as external proof."],
        },
    }


class DigestRenderSnapshotTests(unittest.TestCase):
    maxDiff = None

    def assert_matches_snapshot(self, snapshot_name: str, actual: str) -> None:
        snapshot_path = SNAPSHOT_DIR / snapshot_name
        expected = snapshot_path.read_text(encoding="utf-8")
        if actual != expected:
            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile=str(snapshot_path),
                    tofile="actual",
                    lineterm="",
                )
            )
            self.fail(f"Snapshot mismatch for {snapshot_name}:\n{diff}")

    def test_daily_and_weekly_operator_brief_render_snapshots(self) -> None:
        fixture = operator_brief_fixture()
        with patch("formatter.local_now", return_value=FIXED_NOW):
            daily_html = format_operator_brief_html(fixture, mode="daily")
            weekly_html = format_operator_brief_html(fixture, mode="weekly")

        daily_snapshot = normalize_rendered_html(daily_html)
        weekly_snapshot = normalize_rendered_html(weekly_html)

        self.assertIn("HEADLINES", daily_snapshot)
        self.assertNotIn("WHAT CHANGED SINCE YESTERDAY", daily_snapshot)
        self.assertNotIn("TOP PICKS BY OBJECTIVE", daily_snapshot)
        self.assertNotIn("THESIS TRACKER", daily_snapshot)
        self.assertNotIn("MARKET MAP PULSE", daily_snapshot)
        self.assertNotIn("WATCHED REPOS", daily_snapshot)
        self.assertNotIn("TOP INSIGHT", daily_snapshot)
        self.assertNotIn("OPERATOR MOVES", daily_snapshot)
        self.assertNotIn("DIGEST QUALITY", daily_snapshot)
        self.assertNotIn("OPERATOR STORY BOARD", daily_snapshot)
        self.assertNotIn("Market buckets:", daily_snapshot)
        self.assertNotIn("Thesis links:", daily_snapshot)
        self.assertNotIn("RELIABILITY HIGH", daily_snapshot)

        for weekly_section in (
            "WHAT CHANGED SINCE YESTERDAY",
            "TOP PICKS BY OBJECTIVE",
            "THESIS TRACKER",
            "MARKET MAP PULSE",
            "WATCHED REPOS",
            "TOP INSIGHT",
            "OPERATOR STORY BOARD",
            "OPERATOR MOVES",
            "DIGEST QUALITY",
            "RELIABILITY HIGH",
            "Market buckets:",
            "Thesis links:",
        ):
            self.assertIn(weekly_section, weekly_snapshot)

        self.assertLess(len(daily_snapshot), len(weekly_snapshot) * 0.55)
        self.assert_matches_snapshot("operator_brief_daily.semhtml.snap", daily_snapshot)
        self.assert_matches_snapshot("operator_brief_weekly.semhtml.snap", weekly_snapshot)


if __name__ == "__main__":
    unittest.main()

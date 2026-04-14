import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from weekly_memo import build_weekly_memo_markdown, write_weekly_memo


FIXED_NOW = datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def memory_story(
    title: str,
    *,
    score: float,
    bucket: str,
    change_status: str = "new",
) -> dict[str, object]:
    return {
        "story_id": f"story::{title.lower().replace(' ', '-')}",
        "cluster_title": title,
        "change_status": change_status,
        "supporting_item_count": 1,
        "source_domains": ["example.com"],
        "market_bucket_ids": [bucket],
        "reliability_label": "High",
        "story_score": score,
        "signature_tokens": title.lower().split()[:4],
        "thesis_links": [
            {
                "thesis_id": "prior_auth_infra",
                "title": "Prior auth is becoming workflow infrastructure",
                "relation": "supports",
            }
        ],
    }


def latest_story(
    title: str,
    *,
    category: str = "Regulatory",
    score: float = 36.0,
    action: str = "Audit one prior auth evidence handoff this week",
) -> dict[str, object]:
    return {
        "story_id": f"story::{title.lower().replace(' ', '-')}",
        "cluster_title": title,
        "category": category,
        "item_type": category.lower(),
        "source_names": ["CMS Newsroom"],
        "market_buckets": ["Prior auth"],
        "market_bucket_ids": ["prior_auth"],
        "reliability_label": "High",
        "story_score": score,
        "priority_score": score,
        "change_status": "escalating",
        "signature_tokens": title.lower().split()[:4],
        "action_suggestion": action,
        "thesis_links": [
            {
                "thesis_id": "prior_auth_infra",
                "title": "Prior auth is becoming workflow infrastructure",
                "relation": "supports",
            }
        ],
    }


class WeeklyMemoTests(unittest.TestCase):
    def test_weekly_memo_renders_operator_sections_from_saved_artifacts(self) -> None:
        memory = {
            "version": 2,
            "events": [],
            "daily_briefs": [
                {
                    "date": "2026-04-08",
                    "top_insight": "Prior auth evidence keeps recurring.",
                    "stories": [
                        memory_story(
                            "CMS prior auth evidence exchange",
                            score=34.0,
                            bucket="prior_auth",
                            change_status="new",
                        )
                    ],
                    "quality_eval": {"warnings": ["Generic agent demos are crowding the feed."]},
                }
            ],
        }
        latest_brief = {
            "date": "2026-04-14",
            "operator_moves": {
                "top_insight": "Prior auth remains the clearest operator wedge.",
                "build_idea": "Prototype an evidence packet audit lane.",
                "content_angle": "Write about prior auth evidence exchange instead of generic agents.",
            },
            "story_cards": [
                latest_story("CMS prior auth evidence exchange"),
                latest_story(
                    "Audit-lane repo packages denial evidence",
                    category="Repo",
                    score=31.0,
                    action="Prototype it against one denial queue this week",
                ),
            ],
            "top_picks": {
                "build": {"item": {"cluster_title": "Audit-lane repo packages denial evidence"}},
                "content": {"item": {"cluster_title": "CMS prior auth evidence exchange"}},
            },
            "watchlist_hits": [
                {
                    "cluster_title": "audit-lane",
                    "status": "new",
                }
            ],
        }
        audit = {
            "stories": [
                {
                    "title": "Generic agent platform launch",
                    "selected": False,
                    "primary_reason": "Filtered because target-fit check failed.",
                    "score_summary": {"story_score": 29.0},
                }
            ]
        }

        with patch("weekly_memo.local_now", return_value=FIXED_NOW):
            memo = build_weekly_memo_markdown(
                memory=memory,
                latest_brief=latest_brief,
                selection_audit=audit,
            )

        for section in (
            "## Weekly Summary",
            "## Recurring Themes",
            "## Signals That Matter",
            "## Product / Build Opportunities",
            "## Content Angles",
            "## Likely Noise / Overhyped Items",
            "## Watch Next Week",
        ):
            self.assertIn(section, memo)

        self.assertIn("Prior auth remains the clearest operator wedge", memo)
        self.assertIn("Prototype an evidence packet audit lane", memo)
        self.assertIn("Generic agent platform launch", memo)
        self.assertIn("Watchlist: audit-lane", memo)

    def test_write_weekly_memo_uses_local_files(self) -> None:
        memory = {"version": 2, "events": [], "daily_briefs": []}
        latest_brief = {
            "date": "2026-04-14",
            "operator_moves": {"top_insight": "Saved artifact only."},
            "story_cards": [latest_story("Saved prior auth story")],
        }
        audit = {"stories": []}

        with TemporaryDirectory() as tmpdir:
            latest_path = Path(tmpdir) / "latest_operator_brief.json"
            audit_path = Path(tmpdir) / "latest_selection_audit.json"
            output_path = Path(tmpdir) / "weekly.md"
            latest_path.write_text(json.dumps(latest_brief), encoding="utf-8")
            audit_path.write_text(json.dumps(audit), encoding="utf-8")

            with patch("weekly_memo.local_now", return_value=FIXED_NOW):
                memo = write_weekly_memo(
                    output_path=str(output_path),
                    memory=memory,
                    latest_brief_path=str(latest_path),
                    selection_audit_path=str(audit_path),
                )

            self.assertTrue(output_path.exists())
            self.assertEqual(memo, output_path.read_text(encoding="utf-8"))
            self.assertIn("Saved artifact only", memo)
            self.assertIn("Saved prior auth story", memo)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from formatter import format_operator_brief_html
from operator_brief import build_operator_brief_artifact


def sample_item(
    *,
    category: str,
    title: str,
    url: str,
    source: str,
    item_key: str,
    raw_text: str,
    priority_score: float,
    objective_scores: dict[str, float],
    workflow_wedges: list[str] | None = None,
    matched_themes: list[str] | None = None,
    entity_keys: list[str] | None = None,
    signal: str = "high",
) -> dict[str, object]:
    return {
        "category": category,
        "title": title,
        "url": url,
        "source": source,
        "item_key": item_key,
        "raw_text": raw_text,
        "summary": f"{title} summary.",
        "why_it_matters": "Integration leads should review this workflow in the next sprint.",
        "signal": signal,
        "matched_themes": matched_themes or ["healthcare_admin_automation"],
        "workflow_wedges": workflow_wedges or ["interoperability"],
        "entity_keys": entity_keys or ["cms", "fhir"],
        "objective_scores": objective_scores,
        "score_dimensions": {
            "career_relevance": 4.2,
            "build_relevance": 4.4,
            "content_potential": 3.8,
            "regulatory_significance": 4.7,
            "side_hustle_relevance": 2.8,
            "timeliness": 5.0,
            "novelty": 5.0,
            "theme_momentum": 2.5,
        },
        "priority_score": priority_score,
        "operator_relevance": "high",
        "near_term_actionability": "high",
        "is_generic_devtool": False,
        "generic_repo_cap_exempt": False,
        "published_at": datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
    }


class OperatorBriefTests(unittest.TestCase):
    def test_operator_brief_clusters_related_news_and_regulatory_items(self) -> None:
        items = [
            sample_item(
                category="News",
                title="CMS advances claims attachments interoperability",
                url="https://www.cms.gov/newsroom/fact-sheets/claims-attachments",
                source="CMS Newsroom",
                item_key="news::claims-attachments",
                raw_text="Claims attachments, interoperability, FHIR, and prior authorization workflow updates.",
                priority_score=39.0,
                objective_scores={
                    "career": 7.8,
                    "build": 7.2,
                    "content": 6.5,
                    "regulatory": 8.4,
                },
                workflow_wedges=["RCM/denials", "interoperability"],
                matched_themes=["healthcare_admin_automation", "healthcare_ai_pm"],
            ),
            sample_item(
                category="Regulatory",
                title="Administrative simplification final rule for claims attachments",
                url="https://www.cms.gov/newsroom/fact-sheets/administrative-simplification-final-rule",
                source="CMS Newsroom",
                item_key="reg::claims-attachments",
                raw_text="CMS final rule on claims attachments, electronic signatures, and API exchange.",
                priority_score=41.0,
                objective_scores={
                    "career": 7.0,
                    "build": 6.8,
                    "content": 5.8,
                    "regulatory": 9.2,
                },
                workflow_wedges=["RCM/denials", "interoperability"],
                matched_themes=["healthcare_admin_automation", "healthcare_ai_pm"],
            ),
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "For claims attachments, PMs should prioritize audit-ready exchange and status visibility.",
                "content_angle": "",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ):
            brief = build_operator_brief_artifact(
                items,
                memory={"version": 2, "events": [], "daily_briefs": []},
                memory_snapshot={},
            )

        self.assertEqual(brief["summary"]["raw_item_count"], 2)
        self.assertEqual(brief["summary"]["story_count"], 1)
        story = brief["stories"][0]
        self.assertEqual(story["supporting_item_count"], 2)
        self.assertEqual(story["reliability_label"], "High")
        self.assertTrue(any(entry["thesis_id"] == "interop_distribution_layer" for entry in story["thesis_links"]))
        self.assertEqual(brief["what_changed"][0]["change_type"], "New")

    def test_operator_brief_marks_story_as_escalating_against_previous_day(self) -> None:
        first_day_items = [
            sample_item(
                category="News",
                title="FHIR attachment exchange pilot expands",
                url="https://www.cms.gov/newsroom/fact-sheets/fhir-attachment-pilot",
                source="CMS Newsroom",
                item_key="news::fhir-attachment-pilot",
                raw_text="FHIR attachment exchange pilot expands for prior authorization workflows.",
                priority_score=37.0,
                objective_scores={
                    "career": 7.1,
                    "build": 7.4,
                    "content": 6.4,
                    "regulatory": 7.2,
                },
            )
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "For interoperability, PMs should track attachment exchange proof instead of generic agent demos.",
                "content_angle": "",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ), patch(
            "operator_brief.local_now",
            return_value=datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
        ):
            first_brief = build_operator_brief_artifact(
                first_day_items,
                memory={"version": 2, "events": [], "daily_briefs": []},
                memory_snapshot={},
            )

        previous_memory = {
            "version": 2,
            "events": [],
            "daily_briefs": [
                {
                    "date": "2026-04-08",
                    "generated_at": "2026-04-08T16:00:00+00:00",
                    "top_insight": first_brief["operator_moves"]["top_insight"],
                    "stories": first_brief["stories"],
                    "quality_eval": first_brief["quality_eval"],
                    "market_map": first_brief["market_map"],
                    "thesis_tracker": first_brief["thesis_tracker"],
                    "watchlist_hits": first_brief["watchlist_hits"],
                    "top_picks": first_brief["top_picks"],
                }
            ],
        }
        second_day_items = [
            first_day_items[0],
            sample_item(
                category="Regulatory",
                title="CMS guidance adds another attachment exchange milestone",
                url="https://www.cms.gov/newsroom/fact-sheets/attachment-guidance",
                source="CMS Newsroom",
                item_key="reg::attachment-guidance",
                raw_text="Additional CMS guidance reinforces attachment exchange, prior authorization, and interoperability operations.",
                priority_score=40.0,
                objective_scores={
                    "career": 7.4,
                    "build": 7.0,
                    "content": 6.2,
                    "regulatory": 9.0,
                },
            ),
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "For interoperability, attachment exchange now has broader support across operator-relevant signals.",
                "content_angle": "",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ), patch(
            "operator_brief.local_now",
            return_value=datetime(2026, 4, 9, 16, 0, tzinfo=timezone.utc),
        ):
            second_brief = build_operator_brief_artifact(
                second_day_items,
                memory=previous_memory,
                memory_snapshot={},
            )

        self.assertTrue(
            any(entry["change_type"] == "Escalating" for entry in second_brief["what_changed"])
        )
        self.assertEqual(second_brief["stories"][0]["change_status"], "escalating")

    def test_operator_brief_top_picks_prefer_distinct_story_ids(self) -> None:
        items = [
            sample_item(
                category="News",
                title="Career signal",
                url="https://example.com/career",
                source="Healthcare IT News",
                item_key="news::career",
                raw_text="Healthcare workflow hiring and implementation signal.",
                priority_score=35.0,
                objective_scores={"career": 8.4, "build": 4.0, "content": 5.0, "regulatory": 3.2},
                workflow_wedges=["provider/admin ops"],
            ),
            sample_item(
                category="Repo",
                title="Build signal",
                url="https://github.com/acme/build-signal",
                source="GitHub Search",
                item_key="repo::build",
                raw_text="Prior authorization builder repo with audit trail and denial prep.",
                priority_score=36.0,
                objective_scores={"career": 4.1, "build": 8.5, "content": 4.2, "regulatory": 2.8},
                workflow_wedges=["prior auth"],
            ),
            sample_item(
                category="News",
                title="Content signal",
                url="https://example.com/content",
                source="MobiHealthNews",
                item_key="news::content",
                raw_text="Operator-relevant market trend around ambient workflow deployment.",
                priority_score=34.0,
                objective_scores={"career": 5.1, "build": 4.2, "content": 8.0, "regulatory": 3.0},
                workflow_wedges=["documentation/ambient"],
            ),
            sample_item(
                category="Regulatory",
                title="Regulatory signal",
                url="https://www.fda.gov/medical-devices/reg-signal",
                source="FDA Press Releases",
                item_key="reg::signal",
                raw_text="FDA guidance for workflow monitoring and healthcare AI governance.",
                priority_score=38.0,
                objective_scores={"career": 6.0, "build": 5.4, "content": 5.3, "regulatory": 8.9},
                workflow_wedges=["interoperability"],
                matched_themes=["healthcare_ai_pm", "llm_eval_rag_governance_safety"],
            ),
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "PMs should prioritize distinct workflow signals instead of collapsing every objective into one headline.",
                "content_angle": "",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ):
            brief = build_operator_brief_artifact(
                items,
                memory={"version": 2, "events": [], "daily_briefs": []},
                memory_snapshot={},
            )

        picked_story_ids = {
            pick["item"]["story_id"]
            for pick in brief["top_picks"].values()
            if pick.get("item")
        }
        self.assertEqual(len(picked_story_ids), 4)

    def test_operator_brief_html_defaults_to_scan_first_daily_email(self) -> None:
        items = [
            sample_item(
                category="Regulatory",
                title="CMS final rule for prior authorization attachments",
                url="https://www.cms.gov/newsroom/fact-sheets/prior-auth-attachments",
                source="CMS Newsroom",
                item_key="reg::prior-auth-attachments",
                raw_text="Prior authorization, claims attachments, interoperability, and audit trail requirements.",
                priority_score=40.0,
                objective_scores={"career": 7.2, "build": 7.0, "content": 6.1, "regulatory": 9.1},
                workflow_wedges=["prior auth", "interoperability"],
            )
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "For prior auth, attachment exchange matters because it creates a practical integration and auditability wedge.",
                "content_angle": "Prior-auth ROI beats generic agent theater.",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ):
            brief = build_operator_brief_artifact(
                items,
                memory={"version": 2, "events": [], "daily_briefs": []},
                memory_snapshot={},
            )

        html = format_operator_brief_html(brief)

        self.assertIn("Daily AI Digest", html)
        self.assertIn("HEADLINES", html)
        self.assertIn("CMS final rule for prior authorization attachments", html)
        self.assertIn("CMS Newsroom | Confidence: High", html)
        self.assertNotIn("WHAT CHANGED SINCE YESTERDAY", html)
        self.assertNotIn("TOP PICKS BY OBJECTIVE", html)
        self.assertNotIn("THESIS TRACKER", html)
        self.assertNotIn("MARKET MAP PULSE", html)
        self.assertNotIn("TOP INSIGHT", html)
        self.assertNotIn("OPERATOR MOVES", html)
        self.assertNotIn("DIGEST QUALITY", html)
        self.assertNotIn("OPERATOR STORY BOARD", html)
        self.assertNotIn("RELIABILITY HIGH", html)
        self.assertNotIn("Market buckets:", html)
        self.assertNotIn("Thesis links:", html)

    def test_operator_brief_html_weekly_mode_keeps_operator_sections(self) -> None:
        items = [
            sample_item(
                category="Regulatory",
                title="CMS final rule for prior authorization attachments",
                url="https://www.cms.gov/newsroom/fact-sheets/prior-auth-attachments",
                source="CMS Newsroom",
                item_key="reg::prior-auth-attachments",
                raw_text="Prior authorization, claims attachments, interoperability, and audit trail requirements.",
                priority_score=40.0,
                objective_scores={"career": 7.2, "build": 7.0, "content": 6.1, "regulatory": 9.1},
                workflow_wedges=["prior auth", "interoperability"],
            )
        ]

        with patch(
            "operator_brief.build_strategy_brief",
            return_value={
                "top_insight": "For prior auth, attachment exchange matters because it creates a practical integration and auditability wedge.",
                "content_angle": "Prior-auth ROI beats generic agent theater.",
                "build_idea": "",
                "interview_talking_point": "",
                "watch_item": "",
            },
        ):
            brief = build_operator_brief_artifact(
                items,
                memory={"version": 2, "events": [], "daily_briefs": []},
                memory_snapshot={},
            )

        html = format_operator_brief_html(brief, mode="weekly")

        self.assertIn("WHAT CHANGED SINCE YESTERDAY", html)
        self.assertIn("THESIS TRACKER", html)
        self.assertIn("MARKET MAP PULSE", html)
        self.assertIn("OPERATOR STORY BOARD", html)
        self.assertIn("OPERATOR MOVES", html)
        self.assertIn("DIGEST QUALITY", html)
        self.assertIn("RELIABILITY HIGH", html)


if __name__ == "__main__":
    unittest.main()

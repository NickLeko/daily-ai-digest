from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from selection_audit import (
    build_selection_audit,
    build_selection_diagnostics,
    render_selection_audit_markdown,
    write_selection_audit,
)


def story(
    story_id: str,
    title: str,
    *,
    category: str = "News",
    story_score: float = 32.0,
    operator_relevance: str = "high",
    actionability: str = "high",
    workflow_wedges: list[str] | None = None,
    reliability_label: str = "High",
    is_generic_devtool: bool = False,
    generic_repo_cap_exempt: bool = False,
    supporting_item_count: int = 1,
    topic_key: str = "",
    matched_themes: list[str] | None = None,
    confidence: str = "High",
    signal_quality: str = "strong",
    low_signal_announcement: bool = False,
    material_operator_signal: bool = True,
    selection_penalties: list[str] | None = None,
) -> dict[str, object]:
    return {
        "story_id": story_id,
        "cluster_id": story_id,
        "cluster_title": title,
        "title": title,
        "category": category,
        "item_type": category.lower(),
        "canonical_url": f"https://example.com/{story_id}",
        "source_names": ["Example"],
        "supporting_item_count": supporting_item_count,
        "reliability_score": 90 if reliability_label == "High" else 50,
        "reliability_label": reliability_label,
        "objective_scores": {
            "career": 7.0,
            "build": 7.1,
            "content": 6.8,
            "regulatory": 7.2 if category == "Regulatory" else 3.0,
        },
        "score_dimensions": {
            "career_relevance": 4.0,
            "build_relevance": 4.1,
            "content_potential": 3.8,
            "regulatory_significance": 4.2 if category == "Regulatory" else 1.0,
        },
        "priority_score": story_score,
        "story_score": story_score,
        "signal": "high",
        "confidence": confidence,
        "signal_quality": signal_quality,
        "materiality_reason": "concrete policy, deployment, capability, or workflow consequence",
        "material_operator_signal": material_operator_signal,
        "low_signal_announcement": low_signal_announcement,
        "soft_funding_or_challenge": low_signal_announcement,
        "materiality_signals": ["deployment"] if material_operator_signal else [],
        "selection_penalties": selection_penalties or [],
        "operator_relevance": operator_relevance,
        "near_term_actionability": actionability,
        "workflow_wedges": workflow_wedges if workflow_wedges is not None else ["prior auth"],
        "matched_themes": matched_themes if matched_themes is not None else ["healthcare_admin_automation"],
        "is_generic_devtool": is_generic_devtool,
        "generic_repo_cap_exempt": generic_repo_cap_exempt,
        "topic_key": topic_key,
    }


def item(item_id: str, parent_story: dict[str, object]) -> dict[str, object]:
    return {
        "item_id": item_id,
        "story_id": parent_story["story_id"],
        "duplicate_group_id": parent_story["story_id"],
        "title": parent_story["title"],
        "category": parent_story["category"],
        "item_type": parent_story["item_type"],
        "source_name": "Example",
        "objective_scores": parent_story["objective_scores"],
        "score_dimensions": parent_story["score_dimensions"],
        "priority_score": parent_story["priority_score"],
        "reliability_score": parent_story["reliability_score"],
        "reliability_label": parent_story["reliability_label"],
        "signal": parent_story["signal"],
        "operator_relevance": parent_story["operator_relevance"],
        "near_term_actionability": parent_story["near_term_actionability"],
        "workflow_wedges": parent_story["workflow_wedges"],
        "matched_themes": parent_story["matched_themes"],
        "is_generic_devtool": parent_story["is_generic_devtool"],
        "generic_repo_cap_exempt": parent_story["generic_repo_cap_exempt"],
    }


class SelectionAuditTests(unittest.TestCase):
    def test_selection_audit_marks_story_and_daily_decisions(self) -> None:
        selected = story("selected", "Selected prior auth story")
        filtered = story(
            "filtered",
            "Generic market news",
            story_score=10.0,
            operator_relevance="low",
            actionability="low",
            workflow_wedges=[],
        )
        brief = {
            "summary": {"raw_item_count": 2},
            "stories": [selected, filtered],
            "story_cards": [selected],
            "items": [item("item-selected", selected), item("item-filtered", filtered)],
        }

        audit = build_selection_audit(brief)
        stories = {entry["story_id"]: entry for entry in audit["stories"]}
        items = {entry["item_id"]: entry for entry in audit["items"]}

        self.assertEqual(stories["selected"]["status"], "selected")
        self.assertEqual(
            stories["selected"]["shorter_digest_selection"]["reason"],
            "Selected for shorter daily digest from story_cards.",
        )
        self.assertEqual(stories["filtered"]["status"], "filtered")
        self.assertFalse(stories["filtered"]["target_fit"]["passes"])
        self.assertIn("target-fit", stories["filtered"]["primary_reason"])
        self.assertTrue(stories["filtered"]["shorter_digest_selection"]["backfill_affected"])
        self.assertEqual(items["item-selected"]["status"], "selected")
        self.assertEqual(items["item-filtered"]["status"], "filtered")

        markdown = render_selection_audit_markdown(audit)

        self.assertIn("# Selection Audit Summary", markdown)
        self.assertIn("## Surfaced Stories", markdown)
        self.assertIn("Selected prior auth story", markdown)
        self.assertIn("## Top Filtered Near-Misses", markdown)
        self.assertIn("Generic market news", markdown)
        self.assertIn("## Most Common Exclusion Reasons", markdown)
        self.assertIn("Target-fit failures among filtered stories: 1", markdown)

    def test_selection_diagnostics_emit_selected_story_fields(self) -> None:
        selected = story(
            "selected",
            "Selected prior auth story",
            confidence="High",
            signal_quality="strong",
            selection_penalties=["generic_devtool_score_penalty"],
        )
        brief = {
            "summary": {"raw_item_count": 1},
            "stories": [selected],
            "story_cards": [selected],
            "items": [item("item-selected", selected)],
        }

        diagnostics = build_selection_diagnostics(brief, mode="daily")
        selected_diagnostic = diagnostics["selected_stories"][0]

        self.assertEqual(selected_diagnostic["title"], "Selected prior auth story")
        self.assertEqual(selected_diagnostic["source"], "Example")
        self.assertEqual(selected_diagnostic["signal_quality"], "strong")
        self.assertEqual(selected_diagnostic["materiality_tier"], "strong")
        self.assertEqual(selected_diagnostic["operator_relevance"], "high")
        self.assertEqual(selected_diagnostic["confidence"], "High")
        self.assertEqual(selected_diagnostic["admission_decision"], "daily_selected")
        self.assertEqual(
            selected_diagnostic["primary_reason_selected"],
            "Selected for shorter daily digest from story_cards.",
        )
        self.assertIn(
            "generic_devtool_score_penalty",
            selected_diagnostic["penalties_demotions"],
        )
        self.assertFalse(diagnostics["no_signal_fallback"]["triggered"])

    def test_selection_audit_records_confidence_display_override(self) -> None:
        selected = story(
            "selected",
            "Medium-quality source confidence story",
            confidence="High",
            signal_quality="medium",
        )
        brief = {
            "summary": {"raw_item_count": 1},
            "stories": [selected],
            "story_cards": [selected],
            "items": [item("item-selected", selected)],
        }

        audit = build_selection_audit(brief)
        row = audit["stories"][0]
        diagnostics = build_selection_diagnostics(brief, mode="daily")

        self.assertEqual(row["confidence"], "High")
        self.assertEqual(row["confidence_display"], "Medium")
        self.assertEqual(
            row["confidence_override_reason"],
            "capped_to_medium_for_medium_signal_quality",
        )
        self.assertEqual(diagnostics["selected_stories"][0]["confidence"], "High")
        self.assertEqual(diagnostics["selected_stories"][0]["confidence_display"], "Medium")
        self.assertEqual(
            diagnostics["selected_stories"][0]["confidence_override_reason"],
            "capped_to_medium_for_medium_signal_quality",
        )

    def test_selection_diagnostics_explain_no_signal_fallback(self) -> None:
        weak = story(
            "weak",
            "HHS launches $4M KidneyX challenge",
            story_score=12.0,
            operator_relevance="low",
            actionability="low",
            workflow_wedges=["care coordination"],
            matched_themes=[],
            confidence="Low",
            signal_quality="weak",
            low_signal_announcement=True,
            material_operator_signal=False,
            selection_penalties=["soft_funding_challenge_demoted"],
        )
        brief = {
            "summary": {"raw_item_count": 1},
            "stories": [weak],
            "story_cards": [],
            "items": [item("item-weak", weak)],
        }

        diagnostics = build_selection_diagnostics(brief, mode="daily")
        fallback = diagnostics["no_signal_fallback"]

        self.assertEqual(diagnostics["selected_stories"], [])
        self.assertTrue(fallback["triggered"])
        self.assertEqual(fallback["reason_code"], "no_story_cards_passed_admission")
        self.assertIn("No story cards passed the main admission gates", fallback["reason"])
        self.assertEqual(fallback["screened_item_count"], 1)

    def test_selection_audit_reports_repo_gate_and_daily_limit(self) -> None:
        cards = [
            story("alpha", "Prior auth operating update", category="News"),
            story("bravo", "Ambient documentation rollout", category="News"),
            story("charlie", "Referral intake automation", category="News"),
            story("delta", "Revenue cycle denial workflow", category="News"),
        ]
        limited = story("limited", "Fifth story", category="News")
        generic_repo = story(
            "generic-repo",
            "Generic agent repo",
            category="Repo",
            is_generic_devtool=True,
            generic_repo_cap_exempt=False,
        )
        brief = {
            "summary": {"raw_item_count": 6},
            "stories": [*cards, limited, generic_repo],
            "story_cards": [*cards, limited, generic_repo],
            "items": [],
        }

        audit = build_selection_audit(brief)
        stories = {entry["story_id"]: entry for entry in audit["stories"]}

        self.assertEqual(stories["limited"]["shorter_digest_selection"]["status"], "filtered")
        self.assertTrue(stories["limited"]["shorter_digest_selection"]["shorter_digest_selection_affected"])
        self.assertEqual(
            stories["generic-repo"]["repo_healthcare_anchor_gate"]["status"],
            "generic_repo_not_exempted",
        )
        self.assertTrue(stories["generic-repo"]["repo_healthcare_anchor_gate"]["affected"])

        markdown = render_selection_audit_markdown(audit)

        self.assertIn("Daily digest: 4 selected (0 backfilled), 2 filtered after daily selection", markdown)
        self.assertIn("Short-digest effect: 2 filtered by daily limit", markdown)

    def test_selection_audit_explains_recall_surface_gate(self) -> None:
        cards = [
            story("alpha", "Prior auth operating update", category="News"),
            story("bravo", "Ambient documentation rollout", category="News"),
            story("charlie", "Referral intake automation", category="News"),
        ]
        low_relevance_recall = story(
            "low-relevance-recall",
            "openFDA tramadol enforcement recall",
            category="Regulatory",
            story_score=29.0,
            operator_relevance="low",
            actionability="high",
            workflow_wedges=[],
            topic_key="recall_enforcement",
            matched_themes=[],
        )
        brief = {
            "summary": {"raw_item_count": 4},
            "stories": [*cards, low_relevance_recall],
            "story_cards": cards,
            "items": [],
        }

        audit = build_selection_audit(brief)
        stories = {entry["story_id"]: entry for entry in audit["stories"]}
        recall_row = stories["low-relevance-recall"]

        self.assertEqual(recall_row["status"], "filtered")
        self.assertFalse(recall_row["surface_worthiness"]["passes"])
        self.assertIn("recall/enforcement", recall_row["surface_worthiness"]["reason"])
        self.assertIn("primary-slot usefulness", recall_row["primary_reason"])

        markdown = render_selection_audit_markdown(audit)

        self.assertIn("recall/enforcement story lacks a stronger primary-slot usefulness signal", markdown)

    def test_write_selection_audit_writes_json_and_markdown(self) -> None:
        selected = story("selected", "Selected prior auth story")
        brief = {
            "summary": {"raw_item_count": 1},
            "stories": [selected],
            "story_cards": [selected],
            "items": [item("item-selected", selected)],
        }

        with TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "audit.json"
            markdown_path = Path(tmpdir) / "audit.md"

            write_selection_audit(
                brief,
                path=str(json_path),
                markdown_path=str(markdown_path),
            )

            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertIn("Selected prior auth story", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

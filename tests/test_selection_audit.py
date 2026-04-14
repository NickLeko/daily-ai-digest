import unittest

from selection_audit import build_selection_audit


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
        "operator_relevance": operator_relevance,
        "near_term_actionability": actionability,
        "workflow_wedges": workflow_wedges if workflow_wedges is not None else ["prior auth"],
        "matched_themes": ["healthcare_admin_automation"],
        "is_generic_devtool": is_generic_devtool,
        "generic_repo_cap_exempt": generic_repo_cap_exempt,
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


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone

from scoring import attach_priority_scores
from signal_quality import classify_mapping_materiality


class MaterialityRegressionTests(unittest.TestCase):
    def test_materiality_fixtures_cover_bad_and_strong_patterns(self) -> None:
        fixtures = [
            (
                {
                    "category": "News",
                    "title": "HHS launches $4M KidneyX challenge",
                    "raw_text": (
                        "HHS launched the KidneyX Empower Prize Challenge, awarding $4 million "
                        "for innovations that improve care coordination and kidney disease research."
                    ),
                    "source": "Healthcare IT News",
                },
                "weak",
                False,
                True,
            ),
            (
                {
                    "category": "News",
                    "title": "Foundation announces rural AI innovation grant program",
                    "raw_text": (
                        "A foundation announced a grant program for healthcare AI innovation "
                        "and patient care research."
                    ),
                    "source": "Healthcare IT News",
                },
                "weak",
                False,
                True,
            ),
            (
                {
                    "category": "News",
                    "title": "Trade article discusses referral intake assistant patterns",
                    "raw_text": (
                        "A trade article discussed referral intake assistant patterns "
                        "for patient access workflow without concrete detail."
                    ),
                    "source": "Regional Trade Journal",
                },
                "medium",
                False,
                False,
            ),
            (
                {
                    "category": "Regulatory",
                    "title": "CMS final rule requires prior authorization API status updates",
                    "raw_text": (
                        "CMS issued a final rule requiring health plans to implement FHIR APIs "
                        "for prior authorization status, claims attachments, compliance dates, "
                        "and electronic exchange."
                    ),
                    "source": "CMS Newsroom",
                },
                "strong",
                True,
                False,
            ),
        ]

        for item, signal_quality, material_signal, low_signal in fixtures:
            with self.subTest(title=item["title"]):
                materiality = classify_mapping_materiality(item)
                self.assertEqual(materiality["signal_quality"], signal_quality)
                self.assertEqual(materiality["material_operator_signal"], material_signal)
                self.assertEqual(materiality["low_signal_announcement"], low_signal)

    def test_soft_challenge_is_demoted_by_scoring_profile(self) -> None:
        now = datetime(2026, 4, 18, 15, 0, tzinfo=timezone.utc)
        scored = attach_priority_scores(
            [
                {
                    "category": "News",
                    "title": "HHS launches $4M KidneyX challenge",
                    "url": "https://www.healthcareitnews.com/news/hhs-launches-4m-kidneyx-challenge",
                    "raw_text": (
                        "HHS launched the KidneyX Empower Prize Challenge, awarding $4 million "
                        "for innovations that improve care coordination and research for kidney disease "
                        "and transplantation."
                    ),
                    "item_key": "news::kidneyx",
                    "published_at": now - timedelta(hours=4),
                    "source": "Healthcare IT News",
                }
            ],
            {"version": 1, "events": []},
            now=now,
            sort_items=False,
        )[0]

        self.assertEqual(scored["signal_quality"], "weak")
        self.assertFalse(scored["material_operator_signal"])
        self.assertTrue(scored["low_signal_announcement"])
        self.assertEqual(scored["operator_relevance"], "low")
        self.assertEqual(scored["near_term_actionability"], "low")
        self.assertIn("soft_funding_challenge_demoted", scored["selection_penalties"])


if __name__ == "__main__":
    unittest.main()

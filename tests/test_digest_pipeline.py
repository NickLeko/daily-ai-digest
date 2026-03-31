import unittest
from datetime import datetime, timedelta, timezone

from data import (
    REGULATORY_FEED_SOURCES,
    REGULATORY_TARGET_ITEMS,
    keyword_matches_text,
    parse_cms_newsroom_html,
    regulatory_bucket,
    regulatory_entry_matches_keywords,
    regulatory_relevance_result,
    select_regulatory_items,
)
from formatter import format_digest_html
from summarize import parse_json_payload


def render_item(category: str, title: str) -> dict[str, str]:
    return {
        "category": category,
        "title": title,
        "url": f"https://example.com/{category.lower()}/{title.lower().replace(' ', '-')}",
        "summary": f"{title} summary.",
        "why_it_matters": f"{title} matters.",
        "signal": "high",
    }


def regulatory_item(
    *,
    item_id: str,
    title: str,
    source: str,
    organization: str,
    subcategory: str,
    hours_old: int,
    now: datetime,
    firm_key: str = "",
    classification: str = "",
    status: str = "",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": title,
        "summary": f"{title} source summary",
        "source": source,
        "published_at": now - timedelta(hours=hours_old),
        "url": f"https://example.com/regulatory/{item_id}",
        "category": "Regulatory",
        "subcategory": subcategory,
        "organization": organization,
        "raw_source_type": "test",
        "raw_text": title,
        "item_key": f"regulatory::{item_id}",
        "topic_key": subcategory,
        "firm_key": firm_key,
        "classification": classification,
        "status": status,
    }


class FormatterTests(unittest.TestCase):
    def test_missing_news_section_renders_explicit_fallback(self) -> None:
        html = format_digest_html(
            [
                render_item("Repo", "Repo One"),
                render_item("Regulatory", "Reg One"),
            ],
            "Insight",
        )

        self.assertIn("<h3>News</h3>", html)
        self.assertIn(
            "No high-signal general AI/healthcare news passed filters today.",
            html,
        )
        self.assertIn("1 repo, 0 news items, and 1 regulatory update.", html)

    def test_dynamic_header_count_correctness(self) -> None:
        html = format_digest_html(
            [
                render_item("Repo", "Repo One"),
                render_item("Repo", "Repo Two"),
                render_item("Repo", "Repo Three"),
                render_item("News", "News One"),
                render_item("Regulatory", "Reg One"),
                render_item("Regulatory", "Reg Two"),
            ],
            "Insight",
        )

        self.assertIn("3 repos, 1 news item, and 2 regulatory updates.", html)
        self.assertNotIn("3 news items", html)

    def test_no_quality_regulatory_items_show_fallback(self) -> None:
        html = format_digest_html(
            [
                render_item("Repo", "Repo One"),
                render_item("News", "News One"),
            ],
            "Insight",
        )

        self.assertIn("<h3>Regulatory Updates</h3>", html)
        self.assertIn(
            "No high-signal regulatory updates passed filters today.",
            html,
        )
        self.assertIn("1 repo, 1 news item, and 0 regulatory updates.", html)


class RegulatoryKeywordTests(unittest.TestCase):
    def test_ai_does_not_match_inside_larger_words(self) -> None:
        self.assertFalse(keyword_matches_text("ai", "neurologic manifestations of Hunter Syndrome"))
        self.assertFalse(keyword_matches_text("ai", "alternatives to animal testing"))

    def test_ai_phrase_matches_real_ai_title(self) -> None:
        self.assertTrue(
            regulatory_entry_matches_keywords(
                "FDA publishes AI guidance for clinical software",
                "Draft AI guidance for software developers.",
                ["AI guidance"],
            )
        )

    def test_health_it_and_interoperability_still_match(self) -> None:
        self.assertTrue(
            regulatory_entry_matches_keywords(
                "CMS interoperability final rule for claims attachments",
                "Health IT APIs and interoperability standards are included.",
                ["health IT", "interoperability"],
            )
        )


class RegulatoryRelevanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fda_source = next(
            source for source in REGULATORY_FEED_SOURCES if source["name"] == "FDA Press Releases"
        )
        self.cms_source = next(
            source for source in REGULATORY_FEED_SOURCES if source["name"] == "CMS Newsroom"
        )

    def test_broad_cms_coverage_item_gets_filtered(self) -> None:
        relevance = regulatory_relevance_result(
            "Exchange Coverage Remains Near Record High as 23.1 Million Enroll in 2026",
            "Coverage remains stable and enrollment is high across the marketplace.",
            self.cms_source,
        )

        self.assertFalse(relevance["qualifies"])
        self.assertEqual(relevance["reason"], "broad_only")

    def test_claims_attachments_rule_gets_through(self) -> None:
        relevance = regulatory_relevance_result(
            "Administrative Simplification; Adoption of Standards for Health Care Claims Attachments Transactions and Electronic Signatures Final Rule",
            "CMS finalized claims attachments standards and electronic signatures requirements for data exchange.",
            self.cms_source,
        )

        self.assertTrue(relevance["qualifies"])
        self.assertIn("claims attachments", relevance["strong_matches"])

    def test_fda_ai_digital_health_guidance_gets_through(self) -> None:
        relevance = regulatory_relevance_result(
            "FDA issues AI guidance for clinical decision support software",
            "The draft guidance covers digital health software and algorithm oversight.",
            self.fda_source,
        )

        self.assertTrue(relevance["qualifies"])
        self.assertTrue(relevance["strong_matches"])

    def test_generic_advisory_committee_item_gets_filtered_without_stronger_signal(self) -> None:
        relevance = regulatory_relevance_result(
            "HHS and CMS Announce Healthcare Advisory Committee Members",
            "The committee will improve patient care and modernize the healthcare system.",
            self.cms_source,
        )

        self.assertFalse(relevance["qualifies"])
        self.assertEqual(relevance["reason"], "broad_only")

    def test_advisory_committee_item_can_pass_with_stronger_health_it_signal(self) -> None:
        relevance = regulatory_relevance_result(
            "CMS Advisory Committee Reviews FHIR API Prior Authorization Standards",
            "The committee reviewed interoperability, API, and prior authorization operations for claims workflows.",
            self.cms_source,
        )

        self.assertTrue(relevance["qualifies"])


class SourceParsingTests(unittest.TestCase):
    def test_parse_cms_newsroom_html_extracts_rows(self) -> None:
        html = """
        <div class="views-row"><div class="views-field views-field-nothing"><span class="field-content"><div>
        <div class="ds-u-display--flex ds-u-align-items--center">
        <span class="ds-c-badge ds-c-badge--warn ds-u-margin-right--2">Fact Sheets</span>
        <time datetime="2026-03-20T12:00:00Z"><abbr title="March">Mar</abbr> 20, 2026</time>
        </div>
        <h3 class="ds-u-margin-top--2">Administrative Simplification Final Rule</h3>
        <span class="newsroom-main-view-body ds-u-font-size--md ds-u-margin-top--1">Claims attachments interoperability standard finalized.</span>
        <a href="/newsroom/fact-sheets/administrative-simplification-final-rule" class="ds-c-button newsroom-main-view-link">Read more</a>
        </div></span></div></div>
        """

        rows = parse_cms_newsroom_html(html)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "Fact Sheets")
        self.assertEqual(rows[0]["title"], "Administrative Simplification Final Rule")
        self.assertEqual(
            rows[0]["url"],
            "https://www.cms.gov/newsroom/fact-sheets/administrative-simplification-final-rule",
        )


class SummarizeParsingTests(unittest.TestCase):
    def test_parse_json_payload_handles_code_fences(self) -> None:
        payload = """```json
{"top_insight": "FHIR and workflow automation are converging."}
```"""

        parsed = parse_json_payload(payload)

        self.assertEqual(
            parsed,
            {"top_insight": "FHIR and workflow automation are converging."},
        )

    def test_parse_json_payload_extracts_embedded_json(self) -> None:
        payload = 'Here is the JSON: {"summary": "Two sentences.", "why_it_matters": "One sentence.", "signal": "high"}'

        parsed = parse_json_payload(payload)

        self.assertEqual(
            parsed,
            {
                "summary": "Two sentences.",
                "why_it_matters": "One sentence.",
                "signal": "high",
            },
        )


class RegulatorySelectionTests(unittest.TestCase):
    def test_balanced_regulatory_mix_prefers_distinct_buckets(self) -> None:
        now = datetime(2026, 3, 30, 16, 0, tzinfo=timezone.utc)
        candidates = [
            regulatory_item(
                item_id="fresh-recall",
                title="Fresh device recall",
                source="openFDA Device Enforcement",
                organization="FDA",
                subcategory="recall",
                hours_old=12,
                classification="Class II",
                status="Ongoing",
                firm_key="alpha",
                now=now,
            ),
            regulatory_item(
                item_id="cms-interoperability",
                title="CMS interoperability final rule",
                source="CMS Newsroom",
                organization="CMS",
                subcategory="interoperability",
                hours_old=16,
                now=now,
            ),
            regulatory_item(
                item_id="onc-guidance",
                title="ONC health IT guidance update",
                source="ASTP/ONC Blog",
                organization="ASTP/ONC",
                subcategory="guidance",
                hours_old=20,
                now=now,
            ),
        ]

        selected, _stats = select_regulatory_items(
            candidates,
            set(),
            now=now,
            max_items=REGULATORY_TARGET_ITEMS,
        )

        self.assertEqual(len(selected), 2)
        self.assertEqual(
            len({regulatory_bucket(item["subcategory"]) for item in selected}),
            2,
        )
        self.assertLessEqual(
            sum(1 for item in selected if item["subcategory"] == "recall"),
            1,
        )

    def test_recall_cap_enforced(self) -> None:
        now = datetime(2026, 3, 30, 16, 0, tzinfo=timezone.utc)
        candidates = [
            regulatory_item(
                item_id="fresh-recall-1",
                title="Fresh recall one",
                source="openFDA Device Enforcement",
                organization="FDA",
                subcategory="recall",
                hours_old=10,
                classification="Class II",
                status="Ongoing",
                firm_key="alpha",
                now=now,
            ),
            regulatory_item(
                item_id="fresh-recall-2",
                title="Fresh recall two",
                source="openFDA Drug Enforcement",
                organization="FDA",
                subcategory="recall",
                hours_old=11,
                classification="Class II",
                status="Ongoing",
                firm_key="beta",
                now=now,
            ),
            regulatory_item(
                item_id="cms-policy",
                title="CMS payment policy update",
                source="CMS Newsroom",
                organization="CMS",
                subcategory="reimbursement",
                hours_old=14,
                now=now,
            ),
        ]

        selected, stats = select_regulatory_items(
            candidates,
            set(),
            now=now,
            max_items=REGULATORY_TARGET_ITEMS,
        )

        recall_count = sum(1 for item in selected if item["subcategory"] == "recall")
        self.assertEqual(recall_count, 1)
        self.assertEqual(len(selected), 2)
        self.assertGreater(stats["excluded_reasons"]["recall_cap"], 0)

    def test_no_quality_items_return_fewer_with_fallback_reason(self) -> None:
        now = datetime(2026, 3, 30, 16, 0, tzinfo=timezone.utc)
        candidates = [
            regulatory_item(
                item_id="stale-recall-1",
                title="Stale recall one",
                source="openFDA Device Enforcement",
                organization="FDA",
                subcategory="recall",
                hours_old=24 * 12,
                classification="Class II",
                status="Ongoing",
                firm_key="alpha",
                now=now,
            ),
            regulatory_item(
                item_id="stale-recall-2",
                title="Stale recall two",
                source="openFDA Drug Enforcement",
                organization="FDA",
                subcategory="recall",
                hours_old=24 * 13,
                classification="Class II",
                status="Ongoing",
                firm_key="beta",
                now=now,
            ),
        ]

        sent_keys = {item["item_key"] for item in candidates}
        selected, stats = select_regulatory_items(
            candidates,
            sent_keys,
            now=now,
            max_items=REGULATORY_TARGET_ITEMS,
        )

        self.assertEqual(selected, [])
        self.assertIn("below_threshold", stats["fallback_reason"])


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from agent_brief import (
    DigestOperatorBrief,
    build_agent_brief,
    build_agent_input,
    build_operator_brief,
    coerce_brief_output,
)

from data import (
    REGULATORY_FEED_SOURCES,
    REGULATORY_TARGET_ITEMS,
    keyword_matches_text,
    parse_cms_newsroom_html,
    regulatory_bucket,
    regulatory_entry_matches_keywords,
    regulatory_relevance_result,
    select_scored_items,
    select_regulatory_items,
)
from formatter import format_digest_html
from memory import build_memory_snapshot
from scoring import attach_priority_scores, build_top_picks
from summarize import (
    fallback_digest_strategy,
    fallback_why_it_matters,
    parse_json_payload,
    summarize_items,
    top_insight_is_specific,
    why_it_matters_is_specific,
)


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

    def test_top_picks_and_operator_moves_render_compact_sections(self) -> None:
        items = [
            {
                **render_item("News", "Career Signal"),
                "priority_score": 40.0,
                "objective_scores": {
                    "career": 7.5,
                    "build": 2.0,
                    "content": 5.0,
                    "regulatory": 3.0,
                },
            },
            {
                **render_item("Repo", "Build Signal"),
                "priority_score": 38.0,
                "objective_scores": {
                    "career": 2.0,
                    "build": 8.0,
                    "content": 4.0,
                    "regulatory": 1.0,
                },
            },
            {
                **render_item("Regulatory", "Reg Signal"),
                "priority_score": 35.0,
                "objective_scores": {
                    "career": 4.0,
                    "build": 1.0,
                    "content": 3.0,
                    "regulatory": 8.5,
                },
            },
            {
                **render_item("News", "Content Signal"),
                "priority_score": 33.0,
                "objective_scores": {
                    "career": 3.0,
                    "build": 2.0,
                    "content": 7.2,
                    "regulatory": 1.0,
                },
            },
        ]

        html = format_digest_html(
            items,
            "Bias attention toward admin automation with clean governance signals.",
            top_picks=build_top_picks(items),
            action_brief={
                "content_angle": "Write about why prior auth automation is a wedge, not a feature.",
                "build_idea": "Prototype a denial-appeal summary copilot.",
                "interview_talking_point": "Rank bets by workflow pain and compliance surface area.",
            },
        )

        self.assertIn("TOP PICKS BY OBJECTIVE", html)
        self.assertIn("Top item for career", html)
        self.assertIn("OPERATOR MOVES", html)
        self.assertIn("Build idea:", html)

    def test_top_picks_render_empty_slot_message(self) -> None:
        html = format_digest_html(
            [render_item("News", "News One")],
            "Insight",
            top_picks=[
                {
                    "objective": "regulatory",
                    "label": "Top item for regulatory",
                    "item": None,
                    "score": 0.0,
                    "message": "No high-signal regulatory item today.",
                    "empty": True,
                }
            ],
        )

        self.assertIn("Top item for regulatory", html)
        self.assertIn("No high-signal regulatory item today.", html)
        self.assertNotIn('href="#"', html)

    def test_formatter_escapes_dynamic_html_content(self) -> None:
        html = format_digest_html(
            [
                {
                    **render_item("News", "<Unsafe Title>"),
                    "summary": "Summary with <b>tag</b>.",
                    "why_it_matters": "Because <script>alert(1)</script>.",
                }
            ],
            'Insight with <script>alert("x")</script>',
            top_picks=[
                {
                    "label": "Top item for career",
                    "item": {
                        "title": "<Unsafe Pick>",
                        "url": 'https://example.com/?q=<unsafe>',
                    },
                }
            ],
            action_brief={"build_idea": "Ship <fast> and keep it safe."},
        )

        self.assertIn("&lt;Unsafe Title&gt;", html)
        self.assertIn("Summary with &lt;b&gt;tag&lt;/b&gt;.", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;Unsafe Pick&gt;", html)
        self.assertIn("https://example.com/?q=&lt;unsafe&gt;", html)


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


class AgentBriefTests(unittest.TestCase):
    def test_build_agent_input_uses_compact_item_shape(self) -> None:
        payload = build_agent_input(
            [
                {
                    "category": "News",
                    "title": "Signal",
                    "summary": "Short summary.",
                    "why_it_matters": "Short why.",
                    "signal": "high",
                    "priority_score": 10.2,
                    "objective_scores": {"career": 4.5},
                    "score_focus": ["career_relevance"],
                    "matched_themes": ["healthcare_admin_automation"],
                    "raw_text": "Should not be forwarded.",
                }
            ],
            {"top_themes": [{"theme": "healthcare_admin_automation", "count": 2}]},
        )

        self.assertIn('"today_items"', payload)
        self.assertIn('"matched_themes"', payload)
        self.assertNotIn("Should not be forwarded.", payload)

    def test_coerce_brief_output_requires_top_insight(self) -> None:
        self.assertIsNone(coerce_brief_output({"content_angle": "Only content"}))

        brief = coerce_brief_output(
            {
                "top_insight": "For prior auth, PMs should prioritize attachment exchange and denial-prep automation.",
                "build_idea": "Denial summary copilot.",
            }
        )

        self.assertEqual(
            brief,
            DigestOperatorBrief(
                top_insight="For prior auth, PMs should prioritize attachment exchange and denial-prep automation.",
                content_angle="",
                build_idea="Denial summary copilot.",
                interview_talking_point="",
                watch_item="",
            ),
        )

    def test_build_agent_brief_returns_structured_output_when_agent_succeeds(self) -> None:
        with patch("agent_brief.DIGEST_ANALYST_AGENT_ENABLED", True), patch(
            "agent_brief._run_digest_analyst_agent_sync",
            return_value=DigestOperatorBrief(
                top_insight="For prior auth, the next wedge is audit-ready attachment exchange, so PMs should rank tools by denial lift and status visibility.",
                content_angle="Why prior-auth workflow ROI beats generic copilots.",
            ),
        ):
            brief = build_agent_brief([render_item("News", "Signal")], {})

        self.assertEqual(
            brief,
            DigestOperatorBrief(
                top_insight="For prior auth, the next wedge is audit-ready attachment exchange, so PMs should rank tools by denial lift and status visibility.",
                content_angle="Why prior-auth workflow ROI beats generic copilots.",
                build_idea="",
                interview_talking_point="",
                watch_item="",
            ),
        )

    def test_build_operator_brief_falls_back_when_agent_fails(self) -> None:
        fallback = {
            "top_insight": "Fallback insight.",
            "content_angle": "Fallback content.",
            "build_idea": "",
            "interview_talking_point": "",
            "watch_item": "",
        }

        with patch("agent_brief.DIGEST_ANALYST_AGENT_ENABLED", True), patch(
            "agent_brief._run_digest_analyst_agent_sync",
            side_effect=TimeoutError("agent timed out"),
        ), patch(
            "agent_brief.summarize_digest_strategy",
            return_value=fallback,
        ), patch(
            "builtins.print",
        ):
            result = build_operator_brief([render_item("News", "Signal")], {})

        self.assertEqual(result, fallback)


class PersonalizationScoringTests(unittest.TestCase):
    def test_admin_automation_item_scores_high_for_build_and_side_hustle(self) -> None:
        now = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
        item = {
            "category": "News",
            "title": "CMS prior authorization automation rule",
            "url": "https://example.com/news/prior-auth",
            "raw_text": "Claims attachments, prior auth, workflow automation, and electronic signatures move closer to standardization.",
            "item_key": "news::prior-auth",
            "published_at": now - timedelta(hours=6),
            "source": "CMS Newsroom",
        }

        scored = attach_priority_scores(
            [item],
            {"version": 1, "events": []},
            now=now,
        )[0]

        self.assertIn("healthcare_admin_automation", scored["matched_themes"])
        self.assertGreaterEqual(scored["score_dimensions"]["build_relevance"], 3.0)
        self.assertGreaterEqual(
            scored["score_dimensions"]["side_hustle_relevance"],
            3.0,
        )

    def test_healthcare_workflow_repo_outranks_generic_agent_tooling(self) -> None:
        now = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
        items = [
            {
                "category": "Repo",
                "title": "acme/prior-auth-copilot",
                "url": "https://example.com/repo/prior-auth",
                "raw_text": "Prior authorization automation for claims attachments, payer status checks, and denial-prep workflows with FHIR audit trails.",
                "item_key": "repo::prior-auth",
                "published_at": now - timedelta(hours=2),
                "source": "GitHub Search",
            },
            {
                "category": "Repo",
                "title": "acme/coding-agent-session-manager",
                "url": "https://example.com/repo/coding-agent",
                "raw_text": "Coding agent session manager and multi-agent orchestration framework with API wrappers for autonomous developer workflows.",
                "item_key": "repo::coding-agent",
                "published_at": now - timedelta(hours=1),
                "source": "GitHub Search",
            },
        ]

        scored = attach_priority_scores(items, {"version": 1, "events": []}, now=now)

        self.assertEqual(scored[0]["title"], "acme/prior-auth-copilot")
        self.assertFalse(scored[0]["is_generic_devtool"])
        self.assertTrue(scored[1]["is_generic_devtool"])
        self.assertGreater(scored[0]["priority_score"], scored[1]["priority_score"])

    def test_repeat_detection_lowers_novelty_but_keeps_theme_momentum(self) -> None:
        now = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
        item = {
            "category": "Repo",
            "title": "acme/agent-eval-kit",
            "url": "https://example.com/repo/agent-eval-kit",
            "raw_text": "Agent orchestration and eval tooling for workflow monitoring.",
            "item_key": "repo::agent-eval-kit",
            "published_at": now - timedelta(hours=3),
            "source": "GitHub Search",
        }
        memory = {
            "version": 1,
            "events": [
                {
                    "date": "2026-04-01",
                    "item_key": "repo::agent-eval-kit",
                    "themes": ["agents_workflows", "llm_eval_rag_governance_safety"],
                    "entities": ["openai"],
                },
                {
                    "date": "2026-04-02",
                    "item_key": "news::agentic-workflow",
                    "themes": ["agents_workflows"],
                    "entities": ["openai"],
                },
            ],
        }

        scored = attach_priority_scores([item], memory, now=now)[0]

        self.assertLess(scored["score_dimensions"]["novelty"], 1.0)
        self.assertGreater(scored["score_dimensions"]["theme_momentum"], 2.0)

    def test_memory_snapshot_surfaces_top_recurring_theme(self) -> None:
        now = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
        snapshot = build_memory_snapshot(
            {
                "version": 1,
                "events": [
                    {
                        "date": "2026-04-01",
                        "themes": ["agents_workflows"],
                        "entities": ["openai"],
                    },
                    {
                        "date": "2026-04-02",
                        "themes": ["agents_workflows", "healthcare_admin_automation"],
                        "entities": ["cms"],
                    },
                ],
            },
            now=now,
        )

        self.assertEqual(snapshot["top_themes"][0]["theme"], "agents_workflows")

    def test_top_picks_do_not_backfill_regulatory_with_non_regulatory_items(self) -> None:
        picks = build_top_picks(
            [
                {
                    **render_item("News", "News Winner"),
                    "priority_score": 50.0,
                    "objective_scores": {
                        "career": 8.5,
                        "build": 7.9,
                        "content": 8.2,
                        "regulatory": 9.4,
                    },
                    "item_key": "news::winner",
                },
                {
                    **render_item("Repo", "Repo Builder"),
                    "priority_score": 42.0,
                    "objective_scores": {
                        "career": 3.5,
                        "build": 8.1,
                        "content": 4.2,
                        "regulatory": 1.0,
                    },
                    "item_key": "repo::builder",
                },
            ]
        )

        regulatory_pick = next(
            pick for pick in picks if pick["objective"] == "regulatory"
        )

        self.assertIsNone(regulatory_pick["item"])
        self.assertTrue(regulatory_pick["empty"])
        self.assertEqual(
            regulatory_pick["message"],
            "No high-signal regulatory item today.",
        )

    def test_top_picks_prefer_distinct_items_when_alternatives_exist(self) -> None:
        picks = build_top_picks(
            [
                {
                    **render_item("News", "Career Signal"),
                    "priority_score": 50.0,
                    "objective_scores": {
                        "career": 9.0,
                        "build": 8.7,
                        "content": 8.9,
                        "regulatory": 3.0,
                    },
                    "item_key": "news::career",
                },
                {
                    **render_item("Repo", "Build Signal"),
                    "priority_score": 46.0,
                    "objective_scores": {
                        "career": 3.0,
                        "build": 8.3,
                        "content": 4.8,
                        "regulatory": 1.0,
                    },
                    "item_key": "repo::build",
                },
                {
                    **render_item("News", "Content Signal"),
                    "priority_score": 43.0,
                    "objective_scores": {
                        "career": 5.2,
                        "build": 4.0,
                        "content": 8.1,
                        "regulatory": 2.0,
                    },
                    "item_key": "news::content",
                },
                {
                    **render_item("Regulatory", "Regulatory Signal"),
                    "priority_score": 40.0,
                    "objective_scores": {
                        "career": 5.6,
                        "build": 4.6,
                        "content": 5.1,
                        "regulatory": 8.8,
                    },
                    "item_key": "reg::signal",
                },
            ]
        )

        selected_titles = {
            pick["objective"]: pick["item"]["title"]
            for pick in picks
            if pick["item"] is not None
        }

        self.assertEqual(selected_titles["career"], "Career Signal")
        self.assertEqual(selected_titles["build"], "Build Signal")
        self.assertEqual(selected_titles["content"], "Content Signal")
        self.assertEqual(selected_titles["regulatory"], "Regulatory Signal")
        self.assertEqual(len(set(selected_titles.values())), 4)

    def test_top_picks_can_reuse_item_when_no_valid_alternative_exists(self) -> None:
        picks = build_top_picks(
            [
                {
                    **render_item("News", "Best Overall"),
                    "priority_score": 50.0,
                    "objective_scores": {
                        "career": 9.0,
                        "build": 8.5,
                        "content": 9.1,
                        "regulatory": 2.0,
                    },
                    "item_key": "news::best-overall",
                },
                {
                    **render_item("Repo", "Second Best"),
                    "priority_score": 40.0,
                    "objective_scores": {
                        "career": 5.0,
                        "build": 7.0,
                        "content": 4.0,
                        "regulatory": 1.0,
                    },
                    "item_key": "repo::second-best",
                },
            ]
        )

        selected_titles = {
            pick["objective"]: (pick["item"] or {}).get("title")
            for pick in picks
        }

        self.assertEqual(selected_titles["career"], "Best Overall")
        self.assertEqual(selected_titles["build"], "Second Best")
        self.assertEqual(selected_titles["content"], "Best Overall")
        self.assertIsNone(selected_titles["regulatory"])

    def test_repo_selection_caps_generic_devtools_when_healthcare_options_exist(self) -> None:
        now = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
        items = [
            {
                "category": "Repo",
                "title": "acme/prior-auth-copilot",
                "url": "https://example.com/repo/prior-auth",
                "raw_text": "Prior authorization workflow automation with attachment routing and denial-prep support.",
                "item_key": "repo::prior-auth",
                "published_at": now - timedelta(hours=2),
                "source": "GitHub Search",
            },
            {
                "category": "Repo",
                "title": "acme/referral-intake-router",
                "url": "https://example.com/repo/referral",
                "raw_text": "Referral intake automation for missing documentation, eligibility checks, and routing handoffs.",
                "item_key": "repo::referral",
                "published_at": now - timedelta(hours=3),
                "source": "GitHub Search",
            },
            {
                "category": "Repo",
                "title": "acme/multi-agent-starter",
                "url": "https://example.com/repo/multi-agent",
                "raw_text": "Multi-agent orchestration framework with API wrappers and task runners for autonomous developer workflows.",
                "item_key": "repo::multi-agent",
                "published_at": now - timedelta(hours=1),
                "source": "GitHub Search",
            },
            {
                "category": "Repo",
                "title": "acme/coding-agent-session-manager",
                "url": "https://example.com/repo/coding-agent",
                "raw_text": "Coding agent session manager and developer CLI for autonomous code tasks.",
                "item_key": "repo::coding-agent",
                "published_at": now - timedelta(minutes=30),
                "source": "GitHub Search",
            },
        ]

        selected = select_scored_items(
            items,
            sent_item_keys=set(),
            limit=3,
            memory={"version": 1, "events": []},
            enforce_repo_generic_cap=True,
        )

        selected_titles = [item["title"] for item in selected]

        self.assertIn("acme/prior-auth-copilot", selected_titles)
        self.assertIn("acme/referral-intake-router", selected_titles)
        self.assertEqual(
            sum(1 for item in selected if item["is_generic_devtool"]),
            1,
        )


class DigestStrategyTests(unittest.TestCase):
    def test_top_insight_validation_accepts_prior_authorization_wording(self) -> None:
        self.assertTrue(
            top_insight_is_specific(
                "For prior authorization, PMs should rank attachment exchange bets by denial reduction and status visibility."
            )
        )

    def test_fallback_digest_strategy_names_workflow_wedge_and_operator_implication(self) -> None:
        strategy = fallback_digest_strategy(
            [
                {
                    **render_item("Repo", "Prior Auth Signal"),
                    "priority_score": 42.0,
                    "workflow_wedges": ["prior auth"],
                    "is_generic_devtool": False,
                    "generic_repo_cap_exempt": False,
                },
                {
                    **render_item("Repo", "Generic Agent Framework"),
                    "priority_score": 35.0,
                    "workflow_wedges": [],
                    "is_generic_devtool": True,
                    "generic_repo_cap_exempt": False,
                },
            ]
        )

        self.assertTrue(top_insight_is_specific(strategy["top_insight"]))
        self.assertIn("prior auth", strategy["top_insight"].lower())
        self.assertIn("generic agent tooling", strategy["top_insight"].lower())


class WhyItMattersTests(unittest.TestCase):
    def test_fallback_why_it_matters_is_specific_and_category_aware(self) -> None:
        repo_text = fallback_why_it_matters(
            {
                **render_item("Repo", "Prior Auth Copilot"),
                "raw_text": "Prior authorization workflow automation with claims attachments and payer status checks.",
                "workflow_wedges": ["prior auth"],
            }
        )
        news_text = fallback_why_it_matters(
            {
                **render_item("News", "Referral Launch"),
                "raw_text": "New referral intake launch for routing, eligibility, and intake operations across provider groups.",
                "workflow_wedges": ["referral/intake"],
            }
        )
        regulatory_text = fallback_why_it_matters(
            {
                **render_item("Regulatory", "CMS Claims Attachments Rule"),
                "raw_text": "CMS final rule for claims attachments and electronic signatures.",
                "workflow_wedges": ["RCM/denials"],
            }
        )

        self.assertTrue(why_it_matters_is_specific(repo_text))
        self.assertTrue(why_it_matters_is_specific(news_text))
        self.assertTrue(why_it_matters_is_specific(regulatory_text))
        self.assertIn("real pilot", repo_text.lower())
        self.assertIn("live market signal", news_text.lower())
        self.assertIn("update", regulatory_text.lower())

    def test_summarize_items_replaces_repeated_generic_why_it_matters_with_distinct_fallbacks(self) -> None:
        response = type(
            "Response",
            (),
            {
                "output_text": (
                    '{"summary":"Two short sentences. Still two sentences.",'
                    '"why_it_matters":"Affects workflow; teams should prioritize it soon.",'
                    '"signal":"high"}'
                )
            },
        )()
        items = [
            {
                **render_item("Repo", "Prior Auth Copilot"),
                "raw_text": "Prior authorization repo with claims attachments and payer status checks.",
                "workflow_wedges": ["prior auth"],
            },
            {
                **render_item("News", "Referral Launch"),
                "raw_text": "Referral intake launch for routing and eligibility operations.",
                "workflow_wedges": ["referral/intake"],
            },
            {
                **render_item("Regulatory", "CMS Claims Attachments Rule"),
                "raw_text": "CMS final rule for claims attachments and electronic signatures.",
                "workflow_wedges": ["RCM/denials"],
            },
        ]

        with patch("summarize.client.responses.create", return_value=response):
            summarized = summarize_items(items)

        why_lines = [item["why_it_matters"] for item in summarized]

        self.assertEqual(len(set(why_lines)), 3)
        self.assertTrue(all(why_it_matters_is_specific(line) for line in why_lines))
        self.assertIn("real pilot", why_lines[0].lower())
        self.assertIn("live market signal", why_lines[1].lower())
        self.assertIn("next 30 days", why_lines[2].lower())


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

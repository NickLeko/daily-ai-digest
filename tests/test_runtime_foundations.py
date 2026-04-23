from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import main
import scoring
import summarize
import taxonomy
from config import load_config
from emailer import send_email
from memory import load_digest_memory
from services import get_digest_analyst_service, get_openai_client
from state import load_state


def sample_item() -> dict[str, object]:
    return {
        "category": "News",
        "title": "Operator signal",
        "url": "https://example.com/operator-signal",
        "raw_text": "A concrete workflow signal for testing.",
        "item_key": "news::operator-signal",
        "source": "Example Source",
    }


def sample_brief() -> dict[str, object]:
    return {
        "summary": {
            "story_count": 0,
            "raw_item_count": 1,
        },
        "story_cards": [],
        "stories": [],
        "near_miss_items": [],
        "skipped_news_items": [],
        "operator_moves": {},
        "what_changed": [],
        "thesis_tracker": [],
        "market_map": {},
        "watchlist_hits": [],
        "quality_eval": {},
        "top_picks": {},
    }


class ConfigLoadingTests(unittest.TestCase):
    def test_load_config_allows_missing_openai_key(self) -> None:
        config = load_config(env={})

        self.assertEqual(config.openai_api_key, "")
        self.assertEqual(config.digest_mode, "daily")
        self.assertEqual(config.max_items_per_category, 3)
        self.assertGreaterEqual(len(config.news_feed_urls), 1)


class ServicesTests(unittest.TestCase):
    def test_get_openai_client_uses_lazy_factory(self) -> None:
        config = load_config(env={"OPENAI_API_KEY": "test-key"})

        with patch("services.OpenAI") as openai_cls:
            client = get_openai_client(config)

        openai_cls.assert_called_once_with(api_key="test-key")
        self.assertIs(client, openai_cls.return_value)

    def test_digest_analyst_service_disabled_without_api_key(self) -> None:
        config = load_config(
            env={
                "DIGEST_ANALYST_AGENT_ENABLED": "true",
                "OPENAI_API_KEY": "",
            }
        )

        service = get_digest_analyst_service(config)

        self.assertFalse(service.enabled)
        self.assertGreater(service.timeout_seconds, 0)


class SummarizeRuntimeTests(unittest.TestCase):
    def test_model_response_text_uses_explicit_config_for_client_creation(self) -> None:
        config = load_config(
            env={
                "OPENAI_API_KEY": "config-key",
                "OPENAI_MODEL": "config-model",
            }
        )
        fake_response = type("Response", (), {"output_text": "configured text"})()

        class FakeResponses:
            def create(self, *args: object, **kwargs: object) -> object:
                self.last_args = args
                self.last_kwargs = kwargs
                return fake_response

        fake_client = type("FakeClient", (), {"responses": FakeResponses()})()

        with patch("summarize.get_openai_client", return_value=fake_client) as get_client:
            text = summarize.model_response_text("Prompt", config=config)

        get_client.assert_called_once_with(config)
        self.assertEqual(fake_client.responses.last_kwargs, {"model": "config-model", "input": "Prompt"})
        self.assertEqual(text, "configured text")

    def test_legacy_proxy_is_not_blocked_by_unittest_imports_alone(self) -> None:
        fake_response = type("Response", (), {"output_text": "proxy text"})()

        class FakeResponses:
            def create(self, *args: object, **kwargs: object) -> object:
                self.last_args = args
                self.last_kwargs = kwargs
                return fake_response

        fake_client = type("FakeClient", (), {"responses": FakeResponses()})()

        with patch("summarize._running_under_unittest_runner", return_value=False), patch(
            "summarize.get_openai_client",
            return_value=fake_client,
        ) as get_client:
            text = summarize.model_response_text("Prompt")

        get_client.assert_called_once_with()
        self.assertEqual(fake_client.responses.last_kwargs, {"model": summarize.OPENAI_MODEL, "input": "Prompt"})
        self.assertEqual(text, "proxy text")


class PersistenceRecoveryTests(unittest.TestCase):
    def test_load_state_recovers_from_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "digest_state.json"
            state_path.write_text("{broken", encoding="utf-8")
            config = load_config(
                env={
                    "STATE_FILE_PATH": str(state_path),
                    "LOCAL_TIMEZONE": "America/Los_Angeles",
                }
            )

            with patch("state.current_config", return_value=config):
                loaded = load_state()

        self.assertEqual(loaded, {"last_sent_date": "", "sent_items": []})

    def test_load_digest_memory_recovers_from_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = Path(tmpdir) / "digest_memory.json"
            memory_path.write_text("{broken", encoding="utf-8")
            config = load_config(
                env={
                    "DIGEST_MEMORY_FILE_PATH": str(memory_path),
                    "LOCAL_TIMEZONE": "America/Los_Angeles",
                }
            )

            with patch("memory.current_config", return_value=config):
                loaded = load_digest_memory()

        self.assertEqual(loaded["version"], 2)
        self.assertEqual(loaded["events"], [])
        self.assertEqual(loaded["daily_briefs"], [])

    def test_state_and_memory_helpers_honor_explicit_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "digest_state.json"
            memory_path = Path(tmpdir) / "digest_memory.json"
            state_path.write_text(
                '{"last_sent_date": "2026-04-22", "sent_items": ["news::custom"]}',
                encoding="utf-8",
            )
            memory_path.write_text(
                '{"version": 2, "events": [{"date": "2026-04-22", "item_key": "news::custom"}], "daily_briefs": []}',
                encoding="utf-8",
            )
            config = load_config(
                env={
                    "STATE_FILE_PATH": str(state_path),
                    "DIGEST_MEMORY_FILE_PATH": str(memory_path),
                    "LOCAL_TIMEZONE": "UTC",
                }
            )

            loaded_state = load_state(config=config)
            loaded_memory = load_digest_memory(config=config)

        self.assertEqual(loaded_state["sent_items"], ["news::custom"])
        self.assertEqual(loaded_memory["events"][0]["item_key"], "news::custom")


class EmailerTests(unittest.TestCase):
    def test_send_email_rejects_incomplete_config(self) -> None:
        config = load_config(env={})

        with self.assertRaises(RuntimeError):
            send_email("Subject", "<p>Hello</p>", config=config)

    def test_send_email_uses_configured_smtp_credentials(self) -> None:
        config = load_config(
            env={
                "GMAIL_ADDRESS": "from@example.com",
                "GMAIL_APP_PASSWORD": "app-password",
                "TO_EMAIL": "to@example.com",
            }
        )

        with patch("emailer.smtplib.SMTP") as smtp_cls:
            send_email("Subject", "<p>Hello</p>", config=config)

        smtp_cls.assert_called_once_with("smtp.gmail.com", 587)
        server = smtp_cls.return_value.__enter__.return_value
        server.starttls.assert_called_once_with()
        server.login.assert_called_once_with("from@example.com", "app-password")
        server.sendmail.assert_called_once()


class MainRuntimeTests(unittest.TestCase):
    def test_run_dry_run_threads_config_and_skips_send_side_effects(self) -> None:
        item = sample_item()
        summarized_item = {
            **item,
            "summary": "Useful operator summary.",
            "why_it_matters": "Ops leads should review the workflow this week.",
            "signal": "high",
        }
        memory = {"version": 2, "events": [], "daily_briefs": []}
        diagnostics = {
            "selected_stories": [],
            "no_signal_fallback": {"triggered": False},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(
                env={
                    "DIGEST_MODE": "daily",
                    "OPERATOR_BRIEF_FILE_PATH": str(Path(tmpdir) / "brief.json"),
                    "OPERATOR_COCKPIT_FILE_PATH": str(Path(tmpdir) / "cockpit.html"),
                }
            )

            with patch("main.load_digest_memory", return_value=memory), patch(
                "main.get_real_items", return_value=[item]
            ) as get_items, patch(
                "main.summarize_items", return_value=[summarized_item]
            ) as summarize_items_mock, patch(
                "main.build_memory_snapshot", return_value={}
            ), patch(
                "main.validate_digest_items",
                return_value={"Repo": 0, "News": 1, "Regulatory": 0},
            ), patch(
                "main.build_operator_brief_artifact", return_value=sample_brief()
            ) as brief_builder, patch(
                "main.build_selection_diagnostics", return_value=diagnostics
            ), patch(
                "main.format_operator_brief_html", return_value="<html></html>"
            ), patch(
                "main.format_operator_cockpit_html", return_value="<html></html>"
            ), patch(
                "main.save_artifacts"
            ) as save_artifacts, patch(
                "main.write_selection_audit"
            ), patch(
                "main.send_email"
            ) as send_email_mock, patch(
                "main.mark_sent"
            ) as mark_sent_mock, patch(
                "main.record_digest_items"
            ) as record_items_mock, patch(
                "main.record_operator_brief"
            ) as record_brief_mock:
                main.run(dry_run=True, config=config)

        get_items.assert_called_once_with(memory, config=config)
        summarize_items_mock.assert_called_once_with([item], config=config)
        self.assertIs(brief_builder.call_args.kwargs["config"], config)
        self.assertIs(save_artifacts.call_args.kwargs["config"], config)
        send_email_mock.assert_not_called()
        mark_sent_mock.assert_not_called()
        record_items_mock.assert_not_called()
        record_brief_mock.assert_not_called()

    def test_run_threads_config_into_state_and_memory_side_effects(self) -> None:
        item = sample_item()
        summarized_item = {
            **item,
            "summary": "Useful operator summary.",
            "why_it_matters": "Ops leads should review the workflow this week.",
            "signal": "high",
        }
        memory = {"version": 2, "events": [], "daily_briefs": []}
        diagnostics = {
            "selected_stories": [],
            "no_signal_fallback": {"triggered": False},
        }
        brief = sample_brief()

        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(
                env={
                    "DIGEST_MODE": "daily",
                    "STATE_FILE_PATH": str(Path(tmpdir) / "state.json"),
                    "DIGEST_MEMORY_FILE_PATH": str(Path(tmpdir) / "memory.json"),
                    "OPERATOR_BRIEF_FILE_PATH": str(Path(tmpdir) / "brief.json"),
                    "OPERATOR_COCKPIT_FILE_PATH": str(Path(tmpdir) / "cockpit.html"),
                }
            )

            with patch("main.load_digest_memory", return_value=memory) as load_memory_mock, patch(
                "main.get_real_items", return_value=[item]
            ), patch(
                "main.summarize_items", return_value=[summarized_item]
            ), patch(
                "main.build_memory_snapshot", return_value={}
            ), patch(
                "main.validate_digest_items",
                return_value={"Repo": 0, "News": 1, "Regulatory": 0},
            ), patch(
                "main.build_operator_brief_artifact", return_value=brief
            ), patch(
                "main.build_selection_diagnostics", return_value=diagnostics
            ), patch(
                "main.format_operator_brief_html", return_value="<html></html>"
            ), patch(
                "main.format_operator_cockpit_html", return_value="<html></html>"
            ), patch(
                "main.save_artifacts"
            ), patch(
                "main.write_selection_audit"
            ), patch(
                "main.local_now",
                return_value=datetime(2026, 4, 22),
            ) as local_now_mock, patch(
                "main.already_sent_today",
                return_value=False,
            ) as already_sent_mock, patch(
                "main.send_email"
            ) as send_email_mock, patch(
                "main.mark_sent"
            ) as mark_sent_mock, patch(
                "main.record_digest_items"
            ) as record_items_mock, patch(
                "main.record_operator_brief"
            ) as record_brief_mock:
                main.run(dry_run=False, config=config)

        load_memory_mock.assert_called_once_with(config=config)
        local_now_mock.assert_called_once_with(config=config)
        already_sent_mock.assert_called_once_with(config=config)
        send_email_mock.assert_called_once()
        mark_sent_mock.assert_called_once_with(["news::operator-signal"], config=config)
        record_items_mock.assert_called_once_with([summarized_item], config=config)
        record_brief_mock.assert_called_once_with(brief, config=config)


class ImportSafetyTests(unittest.TestCase):
    def test_importing_runtime_modules_without_openai_key_succeeds(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(repo_root), env.get("PYTHONPATH", "")]
        ).strip(os.pathsep)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import agent_brief, config, memory, state, summarize; print('ok')",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)


class TaxonomyContractTests(unittest.TestCase):
    def test_workflow_rule_tables_stay_aligned(self) -> None:
        self.assertEqual(set(scoring.WORKFLOW_WEDGE_RULES), set(taxonomy.WORKFLOW_RULES))
        for key, rule in taxonomy.WORKFLOW_RULES.items():
            self.assertEqual(scoring.WORKFLOW_WEDGE_RULES[key]["label"], rule["label"])
            self.assertEqual(scoring.WORKFLOW_WEDGE_RULES[key]["keywords"], list(rule["keywords"]))

    def test_summarize_workflow_guidance_uses_taxonomy(self) -> None:
        item = {
            "title": "Prior authorization automation update",
            "raw_text": "Prior authorization teams need stronger attachment exchange support.",
            "summary": "",
            "why_it_matters": "",
            "source": "CMS",
            "topic_key": "",
            "workflow_wedges": [],
        }

        expected = taxonomy.workflow_guidance_for_label("prior auth")

        self.assertEqual(summarize.workflow_guidance_for_item(item), expected)

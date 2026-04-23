import argparse
import json
from pathlib import Path

from app_logging import configure_logging, info
from config import AppConfig, current_config
from data import get_real_items
from formatter import (
    format_operator_brief_html,
    format_operator_cockpit_html,
    validate_digest_items,
)
from operator_brief import build_operator_brief_artifact
from emailer import send_email
from memory import (
    build_memory_snapshot,
    load_digest_memory,
    record_digest_items,
    record_operator_brief,
)
from selection_audit import (
    SELECTION_AUDIT_FILE_PATH,
    SELECTION_AUDIT_MARKDOWN_FILE_PATH,
    build_selection_diagnostics,
    write_selection_audit,
)
from state import already_sent_today, local_now, mark_sent
from storage import write_json_file
from summarize import summarize_items
from weekly_memo import DEFAULT_LOOKBACK_DAYS, WEEKLY_MEMO_FILE_PATH, write_weekly_memo


def log(message: str, **fields: object) -> None:
    info(message, **fields)


def target_count_for_category(category: str, *, config: AppConfig) -> int:
    if category == "Regulatory":
        return config.regulatory_target_items
    return config.max_items_per_category


def normalize_digest_mode(mode: str) -> str:
    normalized = str(mode or "daily").strip().lower()
    if normalized not in {"daily", "weekly"}:
        raise ValueError("Digest mode must be 'daily' or 'weekly'.")
    return normalized


def parse_args(*, config: AppConfig | None = None) -> argparse.Namespace:
    resolved = config or current_config()
    parser = argparse.ArgumentParser(description="Run Daily AI Digest.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and build local artifacts without sending email or mutating send/memory state.",
    )
    parser.add_argument(
        "--digest-mode",
        choices=["daily", "weekly"],
        default=resolved.digest_mode,
        help="Render the scan-first daily email or the analysis-heavy weekly digest.",
    )
    parser.add_argument(
        "--weekly-memo",
        action="store_true",
        help="Generate a local weekly operator memo from saved digest artifacts and exit.",
    )
    parser.add_argument(
        "--weekly-lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Number of recent days to include when generating --weekly-memo.",
    )
    return parser.parse_args()


def save_artifacts(
    operator_brief: dict[str, object],
    html: str,
    cockpit_html: str,
    *,
    config: AppConfig,
) -> None:
    Path("latest_digest.html").write_text(html, encoding="utf-8")
    log("Digest artifact saved", path="latest_digest.html")
    write_json_file(config.operator_brief_file_path, operator_brief)
    log("Operator brief artifact saved", path=config.operator_brief_file_path)
    Path(config.operator_cockpit_file_path).write_text(cockpit_html, encoding="utf-8")
    log("Operator cockpit artifact saved", path=config.operator_cockpit_file_path)


def log_json_event(label: str, payload: dict[str, object]) -> None:
    log(label, payload=json.dumps(payload, sort_keys=True))


def log_selection_diagnostics(diagnostics: dict[str, object]) -> None:
    for story in diagnostics.get("selected_stories", []) or []:
        if isinstance(story, dict):
            log_json_event("Selected story diagnostic", story)

    fallback = diagnostics.get("no_signal_fallback", {}) or {}
    if isinstance(fallback, dict) and fallback.get("triggered"):
        log_json_event("No-signal fallback diagnostic", fallback)


def run(
    *,
    dry_run: bool = False,
    digest_mode: str | None = None,
    config: AppConfig | None = None,
) -> None:
    resolved = config or current_config()
    digest_mode = normalize_digest_mode(digest_mode or resolved.digest_mode)
    memory = load_digest_memory(config=resolved)

    if dry_run:
        log("Dry run enabled: fetch and render will run, but email and state writes are disabled.")

    log("Fetching real items...")
    items = get_real_items(memory, config=resolved)

    if not items:
        raise RuntimeError("No items fetched. Check feeds, API keys, or network.")

    log("Fetched items", count=len(items))
    log("Summarizing items with OpenAI...")
    enriched_items = summarize_items(items, config=resolved)
    memory_snapshot = build_memory_snapshot(memory)

    section_counts = validate_digest_items(enriched_items)
    log(
        "Validated sections before render: "
        f"Repos={section_counts['Repo']} "
        f"News={section_counts['News']} "
        f"Regulatory={section_counts['Regulatory']}"
    )
    for category, count in section_counts.items():
        target_count = target_count_for_category(category, config=resolved)
        if count < target_count:
            log(
                f"{category} section under target count: "
                f"{count}/{target_count}. Continuing with available items."
            )

    log("Generating operator brief...")
    operator_brief = build_operator_brief_artifact(
        enriched_items,
        memory=memory,
        memory_snapshot=memory_snapshot,
        config=resolved,
    )
    log(
        "Operator brief built: "
        f"{operator_brief['summary']['story_count']} stories from "
        f"{operator_brief['summary']['raw_item_count']} screened items."
    )
    selection_diagnostics = build_selection_diagnostics(
        operator_brief,
        mode=digest_mode,
    )
    operator_brief["selection_diagnostics"] = selection_diagnostics
    log_selection_diagnostics(selection_diagnostics)

    log(f"Formatting {digest_mode} HTML email...")
    html = format_operator_brief_html(operator_brief, mode=digest_mode)
    cockpit_html = format_operator_cockpit_html(operator_brief)

    subject_prefix = (
        f"{resolved.email_subject_prefix.strip()} "
        if resolved.email_subject_prefix.strip()
        else ""
    )
    subject_label = "Weekly AI Digest" if digest_mode == "weekly" else "Daily AI Digest"
    subject = f"{subject_prefix}{subject_label} - {local_now(config=resolved).strftime('%Y-%m-%d')}"

    save_artifacts(operator_brief, html, cockpit_html, config=resolved)
    write_selection_audit(operator_brief)
    log(f"Selection audit saved to {SELECTION_AUDIT_FILE_PATH}")
    log(f"Selection audit summary saved to {SELECTION_AUDIT_MARKDOWN_FILE_PATH}")

    if dry_run:
        log("Dry run complete. Local artifacts were written and no email or state updates were performed.")
        return

    if already_sent_today(config=resolved):
        log("Email already sent for the current local day. Skipping duplicate send.")
        return

    log("Sending email...")
    send_email(subject, html, config=resolved)
    mark_sent([item.get("item_key", "") for item in items], config=resolved)
    record_digest_items(enriched_items, config=resolved)
    record_operator_brief(operator_brief, config=resolved)

    log("Done. Check your inbox.")

if __name__ == "__main__":
    configure_logging()
    config = current_config()
    args = parse_args(config=config)
    if args.weekly_memo:
        write_weekly_memo(lookback_days=args.weekly_lookback_days)
        log(f"Weekly operator memo saved to {WEEKLY_MEMO_FILE_PATH}")
    else:
        run(dry_run=args.dry_run, digest_mode=args.digest_mode, config=config)

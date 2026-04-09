import argparse
import json

from data import get_real_items
from config import (
    EMAIL_SUBJECT_PREFIX,
    MAX_ITEMS_PER_CATEGORY,
    OPERATOR_BRIEF_FILE_PATH,
    OPERATOR_COCKPIT_FILE_PATH,
    REGULATORY_TARGET_ITEMS,
)
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
from state import already_sent_today, local_now, mark_sent
from summarize import summarize_items


def log(message: str) -> None:
    timestamp = local_now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{timestamp}] {message}")


def target_count_for_category(category: str) -> int:
    if category == "Regulatory":
        return REGULATORY_TARGET_ITEMS
    return MAX_ITEMS_PER_CATEGORY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Daily AI Digest.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and build local artifacts without sending email or mutating send/memory state.",
    )
    return parser.parse_args()


def save_artifacts(operator_brief: dict[str, object], html: str, cockpit_html: str) -> None:
    log("Digest saved to latest_digest.html")
    with open("latest_digest.html", "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Operator brief saved to {OPERATOR_BRIEF_FILE_PATH}")
    with open(OPERATOR_BRIEF_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(operator_brief, f, indent=2)
    log(f"Operator cockpit saved to {OPERATOR_COCKPIT_FILE_PATH}")
    with open(OPERATOR_COCKPIT_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(cockpit_html)


def run(*, dry_run: bool = False) -> None:
    memory = load_digest_memory()

    if dry_run:
        log("Dry run enabled: fetch and render will run, but email and state writes are disabled.")

    log("Fetching real items...")
    items = get_real_items(memory)

    if not items:
        raise RuntimeError("No items fetched. Check feeds, API keys, or network.")

    log(f"Fetched {len(items)} items.")
    log("Summarizing items with OpenAI...")
    enriched_items = summarize_items(items)
    memory_snapshot = build_memory_snapshot(memory)

    section_counts = validate_digest_items(enriched_items)
    log(
        "Validated sections before render: "
        f"Repos={section_counts['Repo']} "
        f"News={section_counts['News']} "
        f"Regulatory={section_counts['Regulatory']}"
    )
    for category, count in section_counts.items():
        target_count = target_count_for_category(category)
        if count < target_count:
            log(
                f"{category} section under target count: "
                f"{count}/{target_count}. Fallback copy will render."
            )

    log("Generating operator brief...")
    operator_brief = build_operator_brief_artifact(
        enriched_items,
        memory=memory,
        memory_snapshot=memory_snapshot,
    )
    log(
        "Operator brief built: "
        f"{operator_brief['summary']['story_count']} stories from "
        f"{operator_brief['summary']['raw_item_count']} raw items."
    )

    log("Formatting HTML email...")
    html = format_operator_brief_html(operator_brief)
    cockpit_html = format_operator_cockpit_html(operator_brief)

    subject_prefix = f"{EMAIL_SUBJECT_PREFIX.strip()} " if EMAIL_SUBJECT_PREFIX.strip() else ""
    subject = f"{subject_prefix}Daily AI Digest - {local_now().strftime('%Y-%m-%d')}"

    save_artifacts(operator_brief, html, cockpit_html)

    if dry_run:
        log("Dry run complete. Local artifacts were written and no email or state updates were performed.")
        return

    if already_sent_today():
        log("Email already sent for the current local day. Skipping duplicate send.")
        return

    log("Sending email...")
    send_email(subject, html)
    mark_sent([item.get("item_key", "") for item in items])
    record_digest_items(enriched_items)
    record_operator_brief(operator_brief)

    log("Done. Check your inbox.")

if __name__ == "__main__":
    args = parse_args()
    run(dry_run=args.dry_run)

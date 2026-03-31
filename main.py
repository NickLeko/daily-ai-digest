from data import get_real_items
from config import EMAIL_SUBJECT_PREFIX, MAX_ITEMS_PER_CATEGORY, REGULATORY_TARGET_ITEMS
from summarize import summarize_items, summarize_top_insight
from formatter import format_digest_html, validate_digest_items
from emailer import send_email
from state import already_sent_today, local_now, mark_sent


def log(message: str) -> None:
    timestamp = local_now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{timestamp}] {message}")


def target_count_for_category(category: str) -> int:
    if category == "Regulatory":
        return REGULATORY_TARGET_ITEMS
    return MAX_ITEMS_PER_CATEGORY


def main() -> None:
    log("Fetching real items...")
    items = get_real_items()

    if not items:
        raise RuntimeError("No items fetched. Check feeds, API keys, or network.")

    log(f"Fetched {len(items)} items.")
    log("Summarizing items with OpenAI...")
    enriched_items = summarize_items(items)

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

    log("Generating top insight...")
    top_insight = summarize_top_insight(enriched_items)

    log("Formatting HTML email...")
    html = format_digest_html(enriched_items, top_insight)

    subject_prefix = f"{EMAIL_SUBJECT_PREFIX.strip()} " if EMAIL_SUBJECT_PREFIX.strip() else ""
    subject = f"{subject_prefix}Daily AI Digest - {local_now().strftime('%Y-%m-%d')}"

    log("Digest saved to latest_digest.html")
    with open("latest_digest.html", "w") as f:
        f.write(html)

    if already_sent_today():
        log("Email already sent for the current local day. Skipping duplicate send.")
        return

    log("Sending email...")
    send_email(subject, html)
    mark_sent([item.get("item_key", "") for item in items])

    log("Done. Check your inbox.")

if __name__ == "__main__":
    main()

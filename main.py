from data import get_real_items
from config import EMAIL_SUBJECT_PREFIX
from summarize import summarize_items, summarize_top_insight
from formatter import format_digest_html
from emailer import send_email
from state import already_sent_today, local_now, mark_sent


def log(message: str) -> None:
    timestamp = local_now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{timestamp}] {message}")


def main() -> None:
    log("Fetching real items...")
    items = get_real_items()

    if not items:
        raise RuntimeError("No items fetched. Check feeds, API keys, or network.")

    log(f"Fetched {len(items)} items.")
    log("Summarizing items with OpenAI...")
    enriched_items = summarize_items(items)

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

from datetime import datetime

from data import get_real_items
from summarize import summarize_items, summarize_top_insight
from formatter import format_digest_html
from emailer import send_email


def main() -> None:
    print("Fetching real items...")
    items = get_real_items()

    if not items:
        raise RuntimeError("No items fetched. Check feeds, API keys, or network.")

    print(f"Fetched {len(items)} items.")
    print("Summarizing items with OpenAI...")
    enriched_items = summarize_items(items)

    print("Generating top insight...")
    top_insight = summarize_top_insight(enriched_items)

    print("Formatting HTML email...")
    html = format_digest_html(enriched_items, top_insight)

    subject = f"Daily AI Digest - {datetime.now().strftime('%Y-%m-%d')}"

    print("Digest saved to latest_digest.html")
    with open("latest_digest.html", "w") as f:
        f.write(html)

    print("Sending email...")
    send_email(subject, html)

    print("Done. Check your inbox.")

    with open("latest_digest.html", "w") as f:
        f.write(html)

if __name__ == "__main__":
    main()
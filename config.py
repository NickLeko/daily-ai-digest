import os
from dotenv import load_dotenv


load_dotenv()


def get_env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


OPENAI_API_KEY = get_env("OPENAI_API_KEY")
OPENAI_MODEL = get_env("OPENAI_MODEL", required=False, default="gpt-4.1-mini")

GMAIL_ADDRESS = get_env("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD")
TO_EMAIL = get_env("TO_EMAIL")

GITHUB_TOKEN = get_env("GITHUB_TOKEN", required=False, default="")
NEWS_FEED_URLS = [
    url.strip()
    for url in get_env("NEWS_FEED_URLS", required=False, default="").split(",")
    if url.strip()
]

MAX_ITEMS_PER_CATEGORY = int(
    get_env("MAX_ITEMS_PER_CATEGORY", required=False, default="3")
)
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from dotenv import load_dotenv

from taxonomy import PRIORITY_THEME_RULES, TRACKED_ENTITY_RULES


load_dotenv()


DEFAULT_NEWS_FEED_URLS = (
    "https://www.healthcareitnews.com/home/feed",
    "https://www.mobihealthnews.com/rss.xml",
)


def get_env(
    name: str,
    *,
    env: Mapping[str, str] | None = None,
    required: bool = False,
    default: str | None = None,
) -> str:
    source = env if env is not None else os.environ
    value = source.get(name)
    if value is None or not str(value).strip():
        value = default
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return str(value or "")


def get_env_bool(
    name: str,
    *,
    env: Mapping[str, str] | None = None,
    default: bool = False,
) -> bool:
    raw_value = get_env(
        name,
        env=env,
        required=False,
        default="true" if default else "false",
    )
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def get_env_int(
    name: str,
    *,
    env: Mapping[str, str] | None = None,
    default: int,
) -> int:
    raw_value = get_env(name, env=env, required=False, default=str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw_value!r}.") from exc


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    openai_model: str
    digest_analyst_agent_enabled: bool
    digest_analyst_agent_model: str
    digest_analyst_agent_timeout_seconds: int
    gmail_address: str
    gmail_app_password: str
    to_email: str
    email_subject_prefix: str
    digest_mode: str
    github_token: str
    news_feed_urls: tuple[str, ...]
    max_items_per_category: int
    regulatory_target_items: int
    local_timezone: str
    state_file_path: str
    digest_memory_file_path: str
    source_policy_file_path: str
    theses_file_path: str
    market_map_file_path: str
    github_watchlist_file_path: str
    operator_brief_file_path: str
    operator_cockpit_file_path: str
    history_max_events: int
    history_repeat_window_days: int
    history_context_window_days: int
    brief_history_max_days: int
    operator_story_limit: int
    watchlist_story_limit: int


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    openai_model = get_env(
        "OPENAI_MODEL",
        env=env,
        required=False,
        default="gpt-4.1-mini",
    )
    digest_mode = get_env(
        "DIGEST_MODE",
        env=env,
        required=False,
        default="daily",
    ).strip().lower()
    news_feed_urls = tuple(
        url.strip()
        for url in get_env(
            "NEWS_FEED_URLS",
            env=env,
            required=False,
            default=",".join(DEFAULT_NEWS_FEED_URLS),
        ).split(",")
        if url.strip()
    )

    return AppConfig(
        openai_api_key=get_env("OPENAI_API_KEY", env=env, required=False, default=""),
        openai_model=openai_model,
        digest_analyst_agent_enabled=get_env_bool(
            "DIGEST_ANALYST_AGENT_ENABLED",
            env=env,
            default=True,
        ),
        digest_analyst_agent_model=get_env(
            "DIGEST_ANALYST_AGENT_MODEL",
            env=env,
            required=False,
            default=openai_model,
        ),
        digest_analyst_agent_timeout_seconds=get_env_int(
            "DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS",
            env=env,
            default=20,
        ),
        gmail_address=get_env("GMAIL_ADDRESS", env=env, required=False, default=""),
        gmail_app_password=get_env("GMAIL_APP_PASSWORD", env=env, required=False, default=""),
        to_email=get_env("TO_EMAIL", env=env, required=False, default=""),
        email_subject_prefix=get_env(
            "EMAIL_SUBJECT_PREFIX",
            env=env,
            required=False,
            default="",
        ),
        digest_mode=digest_mode,
        github_token=get_env("GITHUB_TOKEN", env=env, required=False, default=""),
        news_feed_urls=news_feed_urls,
        max_items_per_category=get_env_int(
            "MAX_ITEMS_PER_CATEGORY",
            env=env,
            default=3,
        ),
        regulatory_target_items=get_env_int(
            "REGULATORY_TARGET_ITEMS",
            env=env,
            default=2,
        ),
        local_timezone=get_env(
            "LOCAL_TIMEZONE",
            env=env,
            required=False,
            default="America/Los_Angeles",
        ),
        state_file_path=get_env(
            "STATE_FILE_PATH",
            env=env,
            required=False,
            default="data/state/digest_state.json",
        ),
        digest_memory_file_path=get_env(
            "DIGEST_MEMORY_FILE_PATH",
            env=env,
            required=False,
            default="data/state/digest_memory.json",
        ),
        source_policy_file_path=get_env(
            "SOURCE_POLICY_FILE_PATH",
            env=env,
            required=False,
            default="data/source_policies.json",
        ),
        theses_file_path=get_env(
            "THESES_FILE_PATH",
            env=env,
            required=False,
            default="data/theses.json",
        ),
        market_map_file_path=get_env(
            "MARKET_MAP_FILE_PATH",
            env=env,
            required=False,
            default="data/market_map.json",
        ),
        github_watchlist_file_path=get_env(
            "GITHUB_WATCHLIST_FILE_PATH",
            env=env,
            required=False,
            default="data/github_watchlist.json",
        ),
        operator_brief_file_path=get_env(
            "OPERATOR_BRIEF_FILE_PATH",
            env=env,
            required=False,
            default="latest_operator_brief.json",
        ),
        operator_cockpit_file_path=get_env(
            "OPERATOR_COCKPIT_FILE_PATH",
            env=env,
            required=False,
            default="latest_operator_cockpit.html",
        ),
        history_max_events=get_env_int(
            "HISTORY_MAX_EVENTS",
            env=env,
            default=1500,
        ),
        history_repeat_window_days=get_env_int(
            "HISTORY_REPEAT_WINDOW_DAYS",
            env=env,
            default=14,
        ),
        history_context_window_days=get_env_int(
            "HISTORY_CONTEXT_WINDOW_DAYS",
            env=env,
            default=21,
        ),
        brief_history_max_days=get_env_int(
            "BRIEF_HISTORY_MAX_DAYS",
            env=env,
            default=45,
        ),
        operator_story_limit=get_env_int(
            "OPERATOR_STORY_LIMIT",
            env=env,
            default=6,
        ),
        watchlist_story_limit=get_env_int(
            "WATCHLIST_STORY_LIMIT",
            env=env,
            default=3,
        ),
    )


@lru_cache(maxsize=1)
def current_config() -> AppConfig:
    return load_config()


_DEFAULT_CONFIG = current_config()

OPENAI_API_KEY = _DEFAULT_CONFIG.openai_api_key
OPENAI_MODEL = _DEFAULT_CONFIG.openai_model
DIGEST_ANALYST_AGENT_ENABLED = _DEFAULT_CONFIG.digest_analyst_agent_enabled
DIGEST_ANALYST_AGENT_MODEL = _DEFAULT_CONFIG.digest_analyst_agent_model
DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS = _DEFAULT_CONFIG.digest_analyst_agent_timeout_seconds

GMAIL_ADDRESS = _DEFAULT_CONFIG.gmail_address
GMAIL_APP_PASSWORD = _DEFAULT_CONFIG.gmail_app_password
TO_EMAIL = _DEFAULT_CONFIG.to_email
EMAIL_SUBJECT_PREFIX = _DEFAULT_CONFIG.email_subject_prefix
DIGEST_MODE = _DEFAULT_CONFIG.digest_mode

GITHUB_TOKEN = _DEFAULT_CONFIG.github_token
NEWS_FEED_URLS = list(_DEFAULT_CONFIG.news_feed_urls)
MAX_ITEMS_PER_CATEGORY = _DEFAULT_CONFIG.max_items_per_category
REGULATORY_TARGET_ITEMS = _DEFAULT_CONFIG.regulatory_target_items

LOCAL_TIMEZONE = _DEFAULT_CONFIG.local_timezone
STATE_FILE_PATH = _DEFAULT_CONFIG.state_file_path
DIGEST_MEMORY_FILE_PATH = _DEFAULT_CONFIG.digest_memory_file_path
SOURCE_POLICY_FILE_PATH = _DEFAULT_CONFIG.source_policy_file_path
THESES_FILE_PATH = _DEFAULT_CONFIG.theses_file_path
MARKET_MAP_FILE_PATH = _DEFAULT_CONFIG.market_map_file_path
GITHUB_WATCHLIST_FILE_PATH = _DEFAULT_CONFIG.github_watchlist_file_path
OPERATOR_BRIEF_FILE_PATH = _DEFAULT_CONFIG.operator_brief_file_path
OPERATOR_COCKPIT_FILE_PATH = _DEFAULT_CONFIG.operator_cockpit_file_path
HISTORY_MAX_EVENTS = _DEFAULT_CONFIG.history_max_events
HISTORY_REPEAT_WINDOW_DAYS = _DEFAULT_CONFIG.history_repeat_window_days
HISTORY_CONTEXT_WINDOW_DAYS = _DEFAULT_CONFIG.history_context_window_days
BRIEF_HISTORY_MAX_DAYS = _DEFAULT_CONFIG.brief_history_max_days
OPERATOR_STORY_LIMIT = _DEFAULT_CONFIG.operator_story_limit
WATCHLIST_STORY_LIMIT = _DEFAULT_CONFIG.watchlist_story_limit

# Daily Digest v2 personalization config.
SCORING_WEIGHTS = {
    "career_relevance": 2.7,
    "build_relevance": 2.8,
    "content_potential": 1.1,
    "regulatory_significance": 2.6,
    "side_hustle_relevance": 1.8,
    "timeliness": 1.0,
    "novelty": 0.7,
    "theme_momentum": 0.5,
}

OBJECTIVE_SCORE_WEIGHTS = {
    "career": {
        "career_relevance": 1.0,
        "timeliness": 0.25,
        "novelty": 0.1,
        "regulatory_significance": 0.3,
        "build_relevance": 0.15,
    },
    "build": {
        "build_relevance": 1.0,
        "side_hustle_relevance": 0.25,
        "timeliness": 0.2,
        "novelty": 0.1,
        "regulatory_significance": 0.2,
    },
    "content": {
        "content_potential": 1.0,
        "timeliness": 0.25,
        "novelty": 0.1,
        "career_relevance": 0.2,
        "regulatory_significance": 0.2,
    },
    "regulatory": {
        "regulatory_significance": 1.0,
        "timeliness": 0.3,
        "career_relevance": 0.25,
        "build_relevance": 0.15,
        "theme_momentum": 0.1,
    },
}

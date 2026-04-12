import os
from dotenv import load_dotenv


load_dotenv()


DEFAULT_NEWS_FEED_URLS = [
    "https://www.healthcareitnews.com/home/feed",
    "https://www.mobihealthnews.com/rss.xml",
]


def get_env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        value = default
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def get_env_bool(name: str, default: bool = False) -> bool:
    raw_value = get_env(
        name,
        required=False,
        default="true" if default else "false",
    )
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


OPENAI_API_KEY = get_env("OPENAI_API_KEY")
OPENAI_MODEL = get_env("OPENAI_MODEL", required=False, default="gpt-4.1-mini")
DIGEST_ANALYST_AGENT_ENABLED = get_env_bool(
    "DIGEST_ANALYST_AGENT_ENABLED",
    default=True,
)
DIGEST_ANALYST_AGENT_MODEL = get_env(
    "DIGEST_ANALYST_AGENT_MODEL",
    required=False,
    default=OPENAI_MODEL,
)
DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS = int(
    get_env(
        "DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS",
        required=False,
        default="20",
    )
)

GMAIL_ADDRESS = get_env("GMAIL_ADDRESS", required=False, default="")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD", required=False, default="")
TO_EMAIL = get_env("TO_EMAIL", required=False, default="")
EMAIL_SUBJECT_PREFIX = get_env(
    "EMAIL_SUBJECT_PREFIX", required=False, default=""
)
DIGEST_MODE = get_env(
    "DIGEST_MODE", required=False, default="daily"
).strip().lower()

GITHUB_TOKEN = get_env("GITHUB_TOKEN", required=False, default="")
NEWS_FEED_URLS = [
    url.strip()
    for url in get_env(
        "NEWS_FEED_URLS",
        required=False,
        default=",".join(DEFAULT_NEWS_FEED_URLS),
    ).split(",")
    if url.strip()
]

MAX_ITEMS_PER_CATEGORY = int(
    get_env("MAX_ITEMS_PER_CATEGORY", required=False, default="3")
)
REGULATORY_TARGET_ITEMS = int(
    get_env("REGULATORY_TARGET_ITEMS", required=False, default="2")
)

LOCAL_TIMEZONE = get_env(
    "LOCAL_TIMEZONE", required=False, default="America/Los_Angeles"
)
STATE_FILE_PATH = get_env(
    "STATE_FILE_PATH", required=False, default="data/state/digest_state.json"
)
DIGEST_MEMORY_FILE_PATH = get_env(
    "DIGEST_MEMORY_FILE_PATH",
    required=False,
    default="data/state/digest_memory.json",
)
SOURCE_POLICY_FILE_PATH = get_env(
    "SOURCE_POLICY_FILE_PATH",
    required=False,
    default="data/source_policies.json",
)
THESES_FILE_PATH = get_env(
    "THESES_FILE_PATH",
    required=False,
    default="data/theses.json",
)
MARKET_MAP_FILE_PATH = get_env(
    "MARKET_MAP_FILE_PATH",
    required=False,
    default="data/market_map.json",
)
GITHUB_WATCHLIST_FILE_PATH = get_env(
    "GITHUB_WATCHLIST_FILE_PATH",
    required=False,
    default="data/github_watchlist.json",
)
OPERATOR_BRIEF_FILE_PATH = get_env(
    "OPERATOR_BRIEF_FILE_PATH",
    required=False,
    default="latest_operator_brief.json",
)
OPERATOR_COCKPIT_FILE_PATH = get_env(
    "OPERATOR_COCKPIT_FILE_PATH",
    required=False,
    default="latest_operator_cockpit.html",
)
HISTORY_MAX_EVENTS = int(
    get_env("HISTORY_MAX_EVENTS", required=False, default="1500")
)
HISTORY_REPEAT_WINDOW_DAYS = int(
    get_env("HISTORY_REPEAT_WINDOW_DAYS", required=False, default="14")
)
HISTORY_CONTEXT_WINDOW_DAYS = int(
    get_env("HISTORY_CONTEXT_WINDOW_DAYS", required=False, default="21")
)
BRIEF_HISTORY_MAX_DAYS = int(
    get_env("BRIEF_HISTORY_MAX_DAYS", required=False, default="45")
)
OPERATOR_STORY_LIMIT = int(
    get_env("OPERATOR_STORY_LIMIT", required=False, default="6")
)
WATCHLIST_STORY_LIMIT = int(
    get_env("WATCHLIST_STORY_LIMIT", required=False, default="3")
)

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

PRIORITY_THEME_RULES = {
    "healthcare_ai_pm": {
        "label": "Healthcare AI PM",
        "keywords": [
            "digital health",
            "healthcare ai",
            "health it",
            "clinical workflow",
            "provider workflow",
            "care delivery",
            "clinical decision support",
            "ehr",
            "epic",
            "cerner",
            "interoperability",
            "fhir",
            "tefca",
            "medical device software",
            "product strategy",
        ],
        "dimension_boosts": {
            "career_relevance": 2.0,
            "build_relevance": 1.0,
            "content_potential": 0.6,
            "regulatory_significance": 1.2,
        },
    },
    "healthcare_admin_automation": {
        "label": "Healthcare Admin Automation",
        "keywords": [
            "prior authorization",
            "prior auth",
            "referral",
            "referrals",
            "referral management",
            "patient intake",
            "intake",
            "eligibility",
            "benefits verification",
            "claims",
            "claims attachments",
            "utilization management",
            "utilization review",
            "revenue cycle",
            "rcm",
            "billing",
            "denials",
            "denial management",
            "documentation",
            "ambient",
            "scribe",
            "charting",
            "scheduling",
            "patient access",
            "forms",
            "fax",
            "contact center",
            "workflow automation",
            "appeals",
            "electronic signatures",
            "care coordination",
        ],
        "dimension_boosts": {
            "career_relevance": 1.8,
            "build_relevance": 2.0,
            "content_potential": 0.6,
            "regulatory_significance": 0.4,
            "side_hustle_relevance": 2.0,
        },
    },
    "agents_workflows": {
        "label": "Agents And Workflows",
        "keywords": [
            "agent",
            "agents",
            "agentic",
            "workflow engine",
            "orchestration",
            "multi-agent",
            "copilot",
            "task runner",
            "autonomous",
        ],
        "dimension_boosts": {
            "career_relevance": 0.6,
            "build_relevance": 0.9,
            "content_potential": 0.4,
            "side_hustle_relevance": 0.4,
        },
    },
    "llm_eval_rag_governance_safety": {
        "label": "LLM Evals RAG Governance Safety",
        "keywords": [
            "eval",
            "evaluation",
            "benchmark",
            "guardrail",
            "governance",
            "safety",
            "rag",
            "retrieval",
            "vector",
            "knowledge base",
            "audit",
            "monitoring",
            "hallucination",
            "prompt injection",
            "privacy",
            "security",
        ],
        "dimension_boosts": {
            "career_relevance": 0.9,
            "build_relevance": 1.1,
            "content_potential": 0.6,
            "regulatory_significance": 1.4,
        },
    },
    "low_reg_friction_wedges": {
        "label": "Low Friction Product Wedges",
        "keywords": [
            "documentation",
            "scheduling",
            "patient messaging",
            "call center",
            "patient access",
            "operations",
            "back office",
            "appeals",
            "claims",
            "revenue cycle",
            "quality reporting",
            "ambient",
            "referral",
            "intake",
            "care coordination",
            "workflow support",
        ],
        "dimension_boosts": {
            "build_relevance": 1.3,
            "content_potential": 0.6,
            "side_hustle_relevance": 1.9,
            "career_relevance": 0.9,
        },
    },
    "content_opportunities": {
        "label": "Content Opportunities",
        "keywords": [
            "policy",
            "framework",
            "launch",
            "funding",
            "hiring",
            "roadmap",
            "trend",
            "roi",
            "adoption",
            "case study",
            "benchmark",
            "industry",
        ],
        "dimension_boosts": {
            "content_potential": 1.0,
            "career_relevance": 0.2,
            "build_relevance": 0.1,
        },
    },
    "job_search": {
        "label": "Healthcare AI PM Roles",
        "keywords": [
            "product manager",
            "pm role",
            "hiring",
            "leadership",
            "platform",
            "roadmap",
            "implementation",
            "stakeholder",
            "go to market",
            "enterprise",
            "workflow roi",
        ],
        "dimension_boosts": {
            "career_relevance": 1.9,
            "content_potential": 0.5,
            "regulatory_significance": 0.4,
        },
    },
}

TRACKED_ENTITY_RULES = {
    "openai": ["openai", "gpt", "chatgpt"],
    "anthropic": ["anthropic", "claude"],
    "google": ["google", "gemini", "deepmind"],
    "microsoft": ["microsoft", "azure"],
    "meta": ["meta", "llama"],
    "nvidia": ["nvidia"],
    "fda": ["fda", "food and drug administration"],
    "cms": ["cms", "centers for medicare and medicaid services"],
    "astp_onc": ["astp", "onc", "health it certification"],
    "ftc": ["ftc", "federal trade commission"],
    "hhs": ["hhs", "department of health and human services"],
    "tefca": ["tefca"],
    "fhir": ["fhir"],
    "epic": ["epic"],
}

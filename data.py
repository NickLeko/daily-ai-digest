from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin

import feedparser
import requests

from config import (
    GITHUB_TOKEN,
    MAX_ITEMS_PER_CATEGORY,
    NEWS_FEED_URLS,
    REGULATORY_TARGET_ITEMS,
)
from memory import DigestMemory, load_digest_memory
from scoring import attach_priority_scores
from state import get_sent_item_keys


DigestItem = Dict[str, Any]

REPO_RELEVANT_KEYWORDS = [
    "ai",
    "llm",
    "rag",
    "agent",
    "agents",
    "eval",
    "evaluation",
    "openai",
    "anthropic",
    "embedding",
    "vector",
    "search",
    "retrieval",
    "health",
    "healthcare",
    "medical",
    "clinical",
    "ehr",
    "fhir",
    "workflow",
]

REPO_EXCLUDED_KEYWORDS = [
    "banlist",
    "blockchain",
    "coin",
    "crypto",
    "defi",
    "game",
    "gaming",
    "market",
    "monero",
    "nft",
    "token",
    "trading",
    "wallet",
    "web3",
]

REGULATORY_FRESH_WINDOW = timedelta(hours=72)
REGULATORY_RECENT_WINDOW = timedelta(days=7)
REGULATORY_MIN_SELECTION_SCORE = 65
REGULATORY_RECALL_CAP = 1
REGULATORY_CANDIDATE_LIMIT = max(REGULATORY_TARGET_ITEMS * 8, 12)

REGULATORY_ENDPOINTS = [
    {
        "url": "https://api.fda.gov/device/enforcement.json",
        "label": "FDA Device Enforcement",
        "organization": "FDA",
        "source": "openFDA Device Enforcement",
        "subcategory": "recall",
    },
    {
        "url": "https://api.fda.gov/drug/enforcement.json",
        "label": "FDA Drug Enforcement",
        "organization": "FDA",
        "source": "openFDA Drug Enforcement",
        "subcategory": "recall",
    },
]

REGULATORY_FEED_SOURCES = [
    {
        "name": "FDA Press Releases",
        "feed_url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
        "organization": "FDA",
        "source": "FDA Press Releases",
        "subcategory_hint": "guidance",
        "raw_source_type": "rss",
        "max_age_days": 21,
        "strong_keywords": [
            "artificial intelligence",
            "ai",
            "digital health",
            "machine learning",
            "ml",
            "device software",
            "medical device software",
            "software as a medical device",
            "samd",
            "clinical decision support",
            "decision support",
            "cds",
            "algorithm",
        ],
        "medium_keyword_groups": {
            "software_workflow": [
                "software",
                "automation",
                "workflow",
            ],
            "governance": [
                "guidance",
                "draft guidance",
                "final guidance",
                "transparency",
                "monitoring",
                "audit",
            ],
            "security": [
                "cybersecurity",
                "security",
            ],
            "regulatory": [
                "medical device",
                "software functions",
            ],
        },
        "broad_keywords": [
            "approval",
            "drug",
            "treatment",
            "therapy",
            "patient",
            "voucher",
            "meeting",
            "public meeting",
        ],
    },
    {
        "name": "CMS Newsroom",
        "page_url": "https://www.cms.gov/about-cms/contact/newsroom",
        "organization": "CMS",
        "source": "CMS Newsroom",
        "subcategory_hint": "policy",
        "raw_source_type": "html_page",
        "max_age_days": 30,
        "strong_keywords": [
            "interoperability",
            "fhir",
            "api",
            "apis",
            "application programming interface",
            "data exchange",
            "claims attachments",
            "electronic signatures",
            "prior authorization",
            "prior auth",
            "utilization management",
            "information blocking",
        ],
        "medium_keyword_groups": {
            "health_it": [
                "health it",
                "digital",
                "electronic",
                "automation",
                "workflow",
            ],
            "ops": [
                "reimbursement",
                "payment",
                "claims",
                "billing",
                "attachments",
                "coverage determination",
            ],
            "policy": [
                "final rule",
                "proposed rule",
                "rule",
                "standards",
                "transparency",
            ],
            "governance": [
                "audit",
                "monitoring",
                "program integrity",
            ],
        },
        "broad_keywords": [
            "coverage",
            "enrollment",
            "committee",
            "advisory",
            "summit",
            "meeting",
            "readout",
            "stability",
            "affordability",
            "patient care",
            "modernize",
            "innovation",
        ],
    },
    {
        "name": "ASTP/ONC Blog",
        "page_url": "https://www.healthit.gov/buzz-blog/",
        "organization": "ASTP/ONC",
        "source": "ASTP/ONC Blog",
        "subcategory_hint": "interoperability",
        "raw_source_type": "discovered_rss",
        "max_age_days": 90,
        "strong_keywords": [
            "interoperability",
            "fhir",
            "api",
            "data exchange",
            "information blocking",
            "uscdi",
            "tefca",
            "certified health it",
            "health it certification",
            "artificial intelligence",
            "ai",
            "clinical decision support",
            "decision support",
        ],
        "medium_keyword_groups": {
            "health_it": [
                "health it",
                "digital health",
                "software",
                "algorithm",
                "automation",
            ],
            "governance": [
                "transparency",
                "monitoring",
                "audit",
            ],
            "workflow": [
                "behavioral health",
                "diagnostic images",
                "patient engagement",
                "laboratory data standards",
            ],
        },
        "broad_keywords": [
            "ideas",
            "future",
            "insights",
            "updates",
            "better tomorrow",
        ],
    },
    {
        "name": "HHS Press Room OCR",
        "page_url": "https://www.hhs.gov/press-room/index.html",
        "organization": "OCR",
        "source": "HHS Press Room",
        "subcategory_hint": "privacy",
        "raw_source_type": "disabled_source",
        "disabled_reason": "blocked_by_hhs_403",
        "strong_keywords": [
            "hipaa",
            "privacy",
            "security",
            "breach notification",
            "patient records",
            "confidentiality",
            "part 2",
        ],
        "medium_keyword_groups": {
            "governance": [
                "audit",
                "monitoring",
                "investigation",
                "enforcement",
            ],
            "security": [
                "cybersecurity",
                "ransomware",
                "breach",
            ],
            "privacy": [
                "privacy",
                "access",
                "records",
            ],
        },
        "broad_keywords": [
            "settlement",
            "penalty",
            "announces",
            "program",
        ],
    },
]

FEED_LINK_PATTERNS = [
    re.compile(
        r'<link[^>]+rel=["\'][^"\']*alternate[^"\']*["\'][^>]+type=["\'](?:application/(?:rss|atom)\+xml|application/xml|text/xml)["\'][^>]+href=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<a[^>]+href=["\']([^"\']+(?:rss(?:\.xml)?|feed|atom)(?:[^"\']*)?)["\']',
        re.IGNORECASE,
    ),
]

CMS_NEWSROOM_ROW_PATTERN = re.compile(
    r'<div class="views-row">.*?'
    r'<span class="ds-c-badge[^"]*">(?P<label>.*?)</span>\s*'
    r'<time datetime="(?P<datetime>[^"]+)".*?</time>.*?'
    r'<h3[^>]*>(?P<title>.*?)</h3>.*?'
    r'<span class="newsroom-main-view-body[^"]*">(?P<summary>.*?)</span>.*?'
    r'<a href="(?P<href>[^"]+)" class="ds-c-button newsroom-main-view-link">',
    re.IGNORECASE | re.DOTALL,
)

REGULATORY_SUBCATEGORY_BONUS = {
    "recall": 0,
    "enforcement": 0,
    "guidance": 20,
    "policy": 16,
    "reimbursement": 18,
    "interoperability": 20,
    "privacy": 18,
    "safety_alert": 6,
}


def iso_days_ago(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def truncate(text: str, max_len: int = 1200) -> str:
    text = " ".join((text or "").split())
    return text[:max_len]


def item_key(category: str, title: str, url: str) -> str:
    normalized_title = (title or "").strip().lower()
    normalized_url = (url or "").strip().lower()
    return f"{category.lower()}::{normalized_title}::{normalized_url}"


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def strip_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(value or "")).split())


def parse_feed_datetime(entry: Dict[str, Any]) -> datetime | None:
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        return datetime(*parsed_struct[:6], tzinfo=timezone.utc)

    for field in ("published", "updated"):
        raw_value = entry.get(field)
        if not raw_value:
            continue
        try:
            parsed = parsedate_to_datetime(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


def parse_fda_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_iso_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def title_tokens(title: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (title or "").lower())
        if len(token) > 2
    }


def titles_are_similar(left: str, right: str) -> bool:
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    threshold = max(len(left_tokens), len(right_tokens))
    return overlap / threshold >= 0.8


def format_excluded_reasons(reasons: Counter[str]) -> str:
    if not reasons:
        return "none"
    return ", ".join(
        f"{reason}={count}" for reason, count in sorted(reasons.items())
    )


def format_score_breakdown(item: DigestItem) -> str:
    breakdown = item.get("score_breakdown", {})
    if not breakdown:
        return "no-score"
    parts = [
        f"{name}={value}"
        for name, value in breakdown.items()
        if name != "total"
    ]
    parts.append(f"total={item.get('selection_score', breakdown.get('total', 0))}")
    return ", ".join(parts)


def format_selected_items(items: List[DigestItem]) -> str:
    if not items:
        return "none"

    formatted = []
    for item in items:
        reference = item.get("id") or item.get("unique_id") or item.get("item_key") or item.get("title", "")
        priority_score = item.get("priority_score")
        priority_suffix = ""
        if priority_score is not None:
            priority_suffix = f" | priority={priority_score}"
        if item.get("category") == "Regulatory" and item.get("selection_score") is not None:
            formatted.append(
                f"{reference} | {item.get('title', 'Untitled')} | {format_score_breakdown(item)}{priority_suffix}"
            )
        else:
            formatted.append(f"{reference} | {item.get('title', 'Untitled')}{priority_suffix}")
    return "; ".join(formatted)


def log_section_debug(
    label: str,
    raw_count: int,
    filtered_count: int,
    excluded_reasons: Counter[str],
    selected_items: List[DigestItem],
) -> None:
    print(f"{label} raw fetched: {raw_count}")
    print(f"{label} after filters: {filtered_count}")
    print(f"{label} excluded reasons: {format_excluded_reasons(excluded_reasons)}")
    print(f"{label} selected: {format_selected_items(selected_items)}")
    print(f"{label} fallback triggered: {len(selected_items) == 0}")


def log_regulatory_source_debug(
    source_name: str,
    raw_count: int,
    normalized_count: int,
    excluded_reasons: Counter[str],
) -> None:
    print(f"Regulatory source {source_name} raw fetched: {raw_count}")
    print(f"Regulatory source {source_name} after normalization: {normalized_count}")
    print(
        f"Regulatory source {source_name} excluded reasons: {format_excluded_reasons(excluded_reasons)}"
    )


def empty_source_stats(
    source_name: str,
    excluded_reasons: Counter[str],
) -> Dict[str, Any]:
    return {
        "source": source_name,
        "raw_count": 0,
        "normalized_count": 0,
        "excluded_reasons": excluded_reasons,
    }


def repo_is_relevant(name: str, description: str) -> bool:
    haystack = f"{name} {description}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))

    if any(keyword in tokens for keyword in REPO_EXCLUDED_KEYWORDS):
        return False

    if not description.strip():
        return False

    return any(keyword in tokens for keyword in REPO_RELEVANT_KEYWORDS)


def select_scored_items(
    items: List[DigestItem],
    *,
    sent_item_keys: set[str],
    limit: int,
    memory: DigestMemory | None = None,
    enforce_repo_generic_cap: bool = False,
    excluded_reasons: Counter[str] | None = None,
) -> List[DigestItem]:
    scored = attach_priority_scores(items, memory, sort_items=False)
    ranked = sorted(
        scored,
        key=lambda item: (
            item.get("item_key", "") not in sent_item_keys,
            float(item.get("priority_score", 0.0) or 0.0),
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )

    if not enforce_repo_generic_cap:
        return ranked[:limit]

    selected: List[DigestItem] = []
    generic_repo_count = 0

    for item in ranked:
        counts_toward_cap = bool(item.get("is_generic_devtool")) and not bool(
            item.get("generic_repo_cap_exempt")
        )
        if counts_toward_cap and generic_repo_count >= 1:
            if excluded_reasons is not None:
                excluded_reasons["generic_repo_cap"] += 1
            continue

        selected.append(item)
        if counts_toward_cap:
            generic_repo_count += 1
        if len(selected) >= limit:
            break

    return selected


def fetch_github_repos(memory: DigestMemory | None = None) -> List[DigestItem]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    sent_item_keys = get_sent_item_keys()
    updated_after = iso_days_ago(7)
    query = f"stars:>20 pushed:>{updated_after}"

    resp = requests.get(
        "https://api.github.com/search/repositories",
        headers=headers,
        params={
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": 50,
        },
        timeout=30,
    )
    resp.raise_for_status()

    raw_items = resp.json().get("items", [])
    results: List[DigestItem] = []
    seen_repo_keys = set()
    excluded_reasons: Counter[str] = Counter()

    for repo in raw_items:
        full_name = repo.get("full_name", "Untitled repo")
        description = repo.get("description", "") or ""

        if not repo_is_relevant(full_name, description):
            excluded_reasons["irrelevant_repo"] += 1
            continue

        raw_text = (
            f"{full_name}: {description}. "
            f"Language: {repo.get('language', 'Unknown')}. "
            f"Stars: {repo.get('stargazers_count', 0)}. "
            f"Updated at: {repo.get('updated_at', '')}. "
            f"Topics: {', '.join(repo.get('topics', [])[:6])}."
        )

        repo_url = repo.get("html_url", "")
        key = item_key("Repo", full_name, repo_url)
        if key in seen_repo_keys:
            excluded_reasons["duplicate_repo"] += 1
            continue

        seen_repo_keys.add(key)
        results.append(
            {
                "category": "Repo",
                "title": full_name,
                "url": repo_url,
                "raw_text": truncate(raw_text),
                "item_key": key,
                "published_at": parse_iso_datetime(repo.get("updated_at", "")),
                "source": "GitHub Search",
                "repo_full_name": full_name,
                "repo_owner": full_name.split("/", 1)[0] if "/" in full_name else "",
                "repo_name": full_name.split("/", 1)[1] if "/" in full_name else full_name,
                "repo_topics": repo.get("topics", []) or [],
                "stars": int(repo.get("stargazers_count", 0) or 0),
                "forks": int(repo.get("forks_count", 0) or 0),
                "watchers": int(repo.get("watchers_count", 0) or 0),
            }
        )

    selected = select_scored_items(
        results,
        sent_item_keys=sent_item_keys,
        limit=MAX_ITEMS_PER_CATEGORY,
        memory=memory,
        enforce_repo_generic_cap=True,
        excluded_reasons=excluded_reasons,
    )
    log_section_debug("Repos", len(raw_items), len(results), excluded_reasons, selected)
    return selected


def fetch_news_items(memory: DigestMemory | None = None) -> List[DigestItem]:
    results: List[DigestItem] = []
    sent_item_keys = get_sent_item_keys()
    excluded_reasons: Counter[str] = Counter()
    raw_count = 0

    if not NEWS_FEED_URLS:
        excluded_reasons["no_feed_urls_configured"] += 1

    for feed_url in NEWS_FEED_URLS:
        feed = feedparser.parse(feed_url)
        entries = list(feed.entries[:10])

        if getattr(feed, "bozo", 0) and not entries:
            excluded_reasons["feed_parse_error"] += 1
            continue
        if not entries:
            excluded_reasons["feed_empty"] += 1
            continue

        for entry in entries:
            raw_count += 1
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").strip()
            if not title or not url:
                excluded_reasons["missing_title_or_url"] += 1
                continue

            summary = entry.get("summary", "") or entry.get("description", "")
            results.append(
                {
                    "category": "News",
                    "title": title,
                    "url": url,
                    "raw_text": truncate(f"{title}. {summary}"),
                    "item_key": item_key("News", title, url),
                    "published_at": parse_feed_datetime(entry),
                    "source": feed_url,
                }
            )

    seen_titles = set()
    deduped: List[DigestItem] = []
    for item in sorted(
        results,
        key=lambda entry: entry.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        title_key = normalize_text(item.get("title", ""))
        if title_key and title_key in seen_titles:
            excluded_reasons["duplicate_title"] += 1
            continue
        if title_key:
            seen_titles.add(title_key)
        deduped.append(item)

    selected = select_scored_items(
        deduped,
        sent_item_keys=sent_item_keys,
        limit=MAX_ITEMS_PER_CATEGORY,
        memory=memory,
    )
    log_section_debug("News", raw_count, len(deduped), excluded_reasons, selected)
    return selected


def discover_feed_url(page_url: str) -> str | None:
    try:
        resp = requests.get(
            page_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"Warning: failed feed discovery for {page_url}: {exc}")
        return None

    html = resp.text
    for pattern in FEED_LINK_PATTERNS:
        match = pattern.search(html)
        if match:
            return urljoin(page_url, unescape(match.group(1)))
    return None


def parse_cms_newsroom_html(html: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for match in CMS_NEWSROOM_ROW_PATTERN.finditer(html):
        title = strip_html(match.group("title"))
        summary = strip_html(match.group("summary"))
        href = unescape(match.group("href"))
        published_at = parse_iso_datetime(match.group("datetime"))
        entries.append(
            {
                "label": strip_html(match.group("label")),
                "title": title,
                "summary": summary,
                "url": urljoin("https://www.cms.gov", href),
                "published_at": published_at,
            }
        )
    return entries


def infer_regulatory_subcategory(title: str, summary: str, hint: str = "") -> str:
    haystack = f"{title} {summary} {hint}".lower()
    if any(keyword in haystack for keyword in ["recall", "warning letter", "enforcement", "medwatch"]):
        return "recall"
    if any(keyword in haystack for keyword in ["hipaa", "privacy", "security", "breach", "confidentiality", "part 2"]):
        return "privacy"
    if any(keyword in haystack for keyword in ["interoperability", "fhir", "tefca", "uscdi", "api", "health it", "information blocking", "certification"]):
        return "interoperability"
    if any(keyword in haystack for keyword in ["reimbursement", "payment", "coverage", "medicare", "medicaid", "price transparency", "fee schedule"]):
        return "reimbursement"
    if "guidance" in haystack or "draft" in haystack or "final rule" in haystack or "proposed rule" in haystack:
        return "guidance"
    if "policy" in haystack or "rule" in haystack:
        return "policy"
    return hint or "policy"


def regulatory_bucket(subcategory: str) -> str:
    if subcategory in {"recall", "enforcement", "safety_alert"}:
        return "recall_enforcement"
    if subcategory in {"guidance", "policy"}:
        return "policy_guidance"
    if subcategory in {"reimbursement", "interoperability"}:
        return "reimbursement_interoperability"
    if subcategory == "privacy":
        return "privacy_security"
    return subcategory or "other"


def infer_topic_key(title: str, summary: str, subcategory: str) -> str:
    haystack = f"{title} {summary}".lower()
    if any(keyword in haystack for keyword in ["prior authorization", "prior auth"]):
        return "prior_authorization"
    if any(keyword in haystack for keyword in ["price transparency"]):
        return "price_transparency"
    if any(keyword in haystack for keyword in ["interoperability", "tefca", "fhir", "uscdi", "api", "information blocking"]):
        return "interoperability"
    if any(keyword in haystack for keyword in ["hipaa", "privacy", "security", "breach", "confidentiality"]):
        return "privacy_security"
    if any(keyword in haystack for keyword in ["reimbursement", "payment", "coverage", "fee schedule"]):
        return "reimbursement"
    return regulatory_bucket(subcategory)


def recall_class_level(classification: str) -> int:
    normalized = (classification or "").upper().strip()
    if normalized.startswith("CLASS III"):
        return 3
    if normalized.startswith("CLASS II"):
        return 2
    if normalized.startswith("CLASS I"):
        return 1
    return 0


def keyword_matches_text(keyword: str, text: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    normalized_text = normalize_text(text)
    if not normalized_keyword or not normalized_text:
        return False

    if " " in normalized_keyword:
        return f" {normalized_keyword} " in f" {normalized_text} "

    return normalized_keyword in set(normalized_text.split())


def matched_keywords(keywords: List[str], text: str) -> List[str]:
    return [keyword for keyword in keywords if keyword_matches_text(keyword, text)]


def regulatory_entry_matches_keywords(title: str, summary: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {summary}"
    return any(keyword_matches_text(keyword, haystack) for keyword in keywords)


def regulatory_relevance_result(
    title: str,
    summary: str,
    source_config: Dict[str, Any],
) -> Dict[str, Any]:
    haystack = f"{title} {summary}"
    strong_matches = matched_keywords(source_config.get("strong_keywords", []), haystack)
    medium_group_matches: Dict[str, List[str]] = {}
    for group_name, group_keywords in source_config.get("medium_keyword_groups", {}).items():
        group_matches = matched_keywords(group_keywords, haystack)
        if group_matches:
            medium_group_matches[group_name] = group_matches
    broad_matches = matched_keywords(source_config.get("broad_keywords", []), haystack)

    qualifies = bool(strong_matches) or len(medium_group_matches) >= 2
    if qualifies:
        reason = "strong_match" if strong_matches else "multi_group_match"
    elif broad_matches:
        reason = "broad_only"
    else:
        reason = "insufficient_relevance"

    return {
        "qualifies": qualifies,
        "reason": reason,
        "strong_matches": strong_matches,
        "medium_group_matches": medium_group_matches,
        "broad_matches": broad_matches,
    }


def build_regulatory_item(
    *,
    item_id: str,
    title: str,
    summary: str,
    source: str,
    published_at: datetime | None,
    url: str,
    subcategory: str,
    organization: str,
    raw_source_type: str,
    raw_text: str,
    firm_key: str = "",
    classification: str = "",
    status: str = "",
) -> DigestItem:
    normalized_subcategory = subcategory or "policy"
    normalized_title = title.strip() or "Untitled regulatory item"
    normalized_url = url.strip()
    return {
        "id": item_id.strip() or item_key("Regulatory", normalized_title, normalized_url),
        "title": normalized_title,
        "summary": summary.strip(),
        "source": source,
        "published_at": published_at,
        "url": normalized_url,
        "category": "Regulatory",
        "subcategory": normalized_subcategory,
        "organization": organization,
        "raw_source_type": raw_source_type,
        "raw_text": truncate(raw_text),
        "item_key": item_key("Regulatory", normalized_title, normalized_url),
        "topic_key": infer_topic_key(normalized_title, summary, normalized_subcategory),
        "firm_key": firm_key,
        "classification": classification,
        "status": status,
    }


def fetch_feed_regulatory_items(source_config: Dict[str, Any]) -> Tuple[List[DigestItem], Dict[str, Any]]:
    excluded_reasons: Counter[str] = Counter()
    now = datetime.now(timezone.utc)
    max_age_days = int(source_config.get("max_age_days", 14))

    if source_config.get("disabled_reason"):
        excluded_reasons[f"disabled:{source_config['disabled_reason']}"] += 1
        log_regulatory_source_debug(source_config["name"], 0, 0, excluded_reasons)
        return [], empty_source_stats(source_config["name"], excluded_reasons)

    feed_url = source_config.get("feed_url") or discover_feed_url(source_config["page_url"])

    if not feed_url:
        excluded_reasons["feed_not_found"] += 1
        log_regulatory_source_debug(source_config["name"], 0, 0, excluded_reasons)
        return [], empty_source_stats(source_config["name"], excluded_reasons)

    feed = feedparser.parse(feed_url)
    entries = list(feed.entries[:REGULATORY_CANDIDATE_LIMIT])
    results: List[DigestItem] = []

    if getattr(feed, "bozo", 0) and not entries:
        excluded_reasons["feed_parse_error"] += 1
        log_regulatory_source_debug(source_config["name"], 0, 0, excluded_reasons)
        return [], empty_source_stats(source_config["name"], excluded_reasons)

    for entry in entries:
        title = strip_html(entry.get("title", "")).strip()
        url = (entry.get("link") or "").strip()
        summary = strip_html(entry.get("summary", "") or entry.get("description", "")).strip()
        published_at = parse_feed_datetime(entry)

        if not title or not url:
            excluded_reasons["missing_title_or_url"] += 1
            continue
        if published_at and now - published_at > timedelta(days=max_age_days):
            excluded_reasons[f"older_than_{max_age_days}d"] += 1
            continue
        relevance = regulatory_relevance_result(title, summary, source_config)
        if not relevance["qualifies"]:
            excluded_reasons[f"relevance_{relevance['reason']}"] += 1
            continue

        subcategory = infer_regulatory_subcategory(
            title,
            summary,
            source_config.get("subcategory_hint", ""),
        )
        raw_text = (
            f"{source_config['source']}. "
            f"Title: {title}. "
            f"Summary: {summary}. "
            f"Published at: {published_at.isoformat() if published_at else 'unknown'}."
        )
        entry_id = str(entry.get("id") or entry.get("guid") or url).strip()
        results.append(
            build_regulatory_item(
                item_id=entry_id,
                title=title,
                summary=summary,
                source=source_config["source"],
                published_at=published_at,
                url=url,
                subcategory=subcategory,
                organization=source_config["organization"],
                raw_source_type=source_config["raw_source_type"],
                raw_text=raw_text,
            )
        )

    log_regulatory_source_debug(
        source_config["name"],
        len(entries),
        len(results),
        excluded_reasons,
    )
    return results, {
        "source": source_config["name"],
        "raw_count": len(entries),
        "normalized_count": len(results),
        "excluded_reasons": excluded_reasons,
    }


def fetch_fda_press_release_items() -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(REGULATORY_FEED_SOURCES[0])


def fetch_cms_regulatory_items() -> Tuple[List[DigestItem], Dict[str, Any]]:
    source_config = REGULATORY_FEED_SOURCES[1]
    excluded_reasons: Counter[str] = Counter()
    now = datetime.now(timezone.utc)
    max_age_days = int(source_config.get("max_age_days", 30))

    try:
        resp = requests.get(
            source_config["page_url"],
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except Exception as exc:
        excluded_reasons["page_fetch_error"] += 1
        print(f"Warning: failed CMS newsroom fetch {source_config['page_url']}: {exc}")
        log_regulatory_source_debug(source_config["name"], 0, 0, excluded_reasons)
        return [], empty_source_stats(source_config["name"], excluded_reasons)

    raw_entries = parse_cms_newsroom_html(resp.text)
    results: List[DigestItem] = []

    if not raw_entries:
        excluded_reasons["page_parse_error"] += 1

    for entry in raw_entries[:REGULATORY_CANDIDATE_LIMIT]:
        title = entry["title"]
        summary = entry["summary"]
        published_at = entry["published_at"]
        url = entry["url"]

        if not title or not url:
            excluded_reasons["missing_title_or_url"] += 1
            continue
        if published_at and now - published_at > timedelta(days=max_age_days):
            excluded_reasons[f"older_than_{max_age_days}d"] += 1
            continue
        relevance = regulatory_relevance_result(title, summary, source_config)
        if not relevance["qualifies"]:
            excluded_reasons[f"relevance_{relevance['reason']}"] += 1
            continue

        subcategory = infer_regulatory_subcategory(
            title,
            summary,
            source_config.get("subcategory_hint", ""),
        )
        raw_text = (
            f"{source_config['source']}. "
            f"Label: {entry['label']}. "
            f"Title: {title}. "
            f"Summary: {summary}. "
            f"Published at: {published_at.isoformat() if published_at else 'unknown'}."
        )
        results.append(
            build_regulatory_item(
                item_id=url,
                title=title,
                summary=summary,
                source=source_config["source"],
                published_at=published_at,
                url=url,
                subcategory=subcategory,
                organization=source_config["organization"],
                raw_source_type=source_config["raw_source_type"],
                raw_text=raw_text,
            )
        )

    log_regulatory_source_debug(
        source_config["name"],
        len(raw_entries),
        len(results),
        excluded_reasons,
    )
    return results, {
        "source": source_config["name"],
        "raw_count": len(raw_entries),
        "normalized_count": len(results),
        "excluded_reasons": excluded_reasons,
    }


def fetch_onc_regulatory_items() -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(REGULATORY_FEED_SOURCES[2])


def fetch_ocr_regulatory_items() -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(REGULATORY_FEED_SOURCES[3])


def regulatory_is_fresh(item: DigestItem, now: datetime) -> bool:
    published_at = item.get("published_at")
    if not isinstance(published_at, datetime):
        return False
    return now - published_at <= REGULATORY_FRESH_WINDOW


def regulatory_base_breakdown(
    item: DigestItem,
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> Dict[str, int]:
    published_at = item.get("published_at")
    freshness = -15
    if isinstance(published_at, datetime):
        age = now - published_at
        if age <= timedelta(hours=24):
            freshness = 120
        elif age <= REGULATORY_FRESH_WINDOW:
            freshness = 90
        elif age <= REGULATORY_RECENT_WINDOW:
            freshness = 45
        else:
            freshness = 5

    novelty = 20
    if item.get("item_key", "") in sent_item_keys:
        novelty = -55 if not regulatory_is_fresh(item, now) else -10

    subcategory = item.get("subcategory", "policy")
    subcategory_bonus = REGULATORY_SUBCATEGORY_BONUS.get(subcategory, 10)

    severity = 0
    class_level = recall_class_level(item.get("classification", ""))
    if class_level == 1:
        severity += 15
    elif class_level == 2:
        severity += 8
    elif class_level == 3:
        severity += 3

    if (item.get("status", "") or "").strip().lower() == "ongoing":
        severity -= 5

    total = freshness + novelty + subcategory_bonus + severity
    return {
        "freshness": freshness,
        "novelty": novelty,
        "subcategory": subcategory_bonus,
        "severity": severity,
        "total": total,
    }


def is_unusually_strong_recall(item: DigestItem, base_breakdown: Dict[str, int]) -> bool:
    return (
        regulatory_bucket(item.get("subcategory", "")) == "recall_enforcement"
        and base_breakdown["freshness"] >= 120
        and base_breakdown["novelty"] >= -10
        and recall_class_level(item.get("classification", "")) == 1
    )


def regulatory_selection_breakdown(
    item: DigestItem,
    selected_items: List[DigestItem],
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> Dict[str, int] | None:
    base = regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)
    bucket = regulatory_bucket(item.get("subcategory", ""))
    recall_count = sum(
        1
        for selected_item in selected_items
        if regulatory_bucket(selected_item.get("subcategory", "")) == "recall_enforcement"
    )

    if bucket == "recall_enforcement" and recall_count >= REGULATORY_RECALL_CAP:
        if not is_unusually_strong_recall(item, base):
            return None

    selected_sources = {selected_item.get("source", "") for selected_item in selected_items}
    selected_orgs = {selected_item.get("organization", "") for selected_item in selected_items}
    selected_buckets = {
        regulatory_bucket(selected_item.get("subcategory", ""))
        for selected_item in selected_items
    }
    selected_topics = {selected_item.get("topic_key", "") for selected_item in selected_items}
    selected_subcategories = {
        selected_item.get("subcategory", "")
        for selected_item in selected_items
    }
    selected_firms = {
        selected_item.get("firm_key", "")
        for selected_item in selected_items
        if selected_item.get("firm_key", "")
    }

    organization_penalty = -10 if item.get("organization", "") in selected_orgs else 0
    source_penalty = -8 if item.get("source", "") in selected_sources else 0
    bucket_penalty = -18 if bucket in selected_buckets else 0
    topic_penalty = -12 if item.get("topic_key", "") in selected_topics else 0
    subcategory_penalty = (
        -8 if item.get("subcategory", "") in selected_subcategories else 0
    )
    same_firm_penalty = (
        -25
        if item.get("firm_key", "") and item.get("firm_key", "") in selected_firms
        else 0
    )

    total = (
        base["total"]
        + organization_penalty
        + source_penalty
        + bucket_penalty
        + topic_penalty
        + subcategory_penalty
        + same_firm_penalty
    )
    return {
        "freshness": base["freshness"],
        "novelty": base["novelty"],
        "subcategory": base["subcategory"],
        "severity": base["severity"],
        "organization_diversity": organization_penalty,
        "source_diversity": source_penalty,
        "bucket_diversity": bucket_penalty,
        "topic_diversity": topic_penalty,
        "subcategory_diversity": subcategory_penalty,
        "same_firm": same_firm_penalty,
        "total": total,
    }


def classify_regulatory_skip_reason(
    item: DigestItem,
    selected_items: List[DigestItem],
    *,
    now: datetime,
    sent_item_keys: set[str],
) -> str:
    base = regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)
    bucket = regulatory_bucket(item.get("subcategory", ""))
    recall_count = sum(
        1
        for selected_item in selected_items
        if regulatory_bucket(selected_item.get("subcategory", "")) == "recall_enforcement"
    )
    if bucket == "recall_enforcement" and recall_count >= REGULATORY_RECALL_CAP:
        if not is_unusually_strong_recall(item, base):
            return "recall_cap"
    if item.get("item_key", "") in sent_item_keys and not regulatory_is_fresh(item, now):
        return "already_sent_stale"
    if item.get("firm_key", "") and item.get("firm_key", "") in {
        selected_item.get("firm_key", "")
        for selected_item in selected_items
    }:
        return "same_firm"
    if regulatory_selection_breakdown(
        item,
        selected_items,
        now=now,
        sent_item_keys=sent_item_keys,
    ):
        breakdown = regulatory_selection_breakdown(
            item,
            selected_items,
            now=now,
            sent_item_keys=sent_item_keys,
        )
        if breakdown and breakdown["total"] < REGULATORY_MIN_SELECTION_SCORE:
            return "low_score"
        if breakdown and breakdown["bucket_diversity"] < 0:
            return "bucket_cluster"
        if breakdown and breakdown["topic_diversity"] < 0:
            return "topic_cluster"
        if breakdown and breakdown["source_diversity"] < 0:
            return "source_cluster"
    return "rank_cutoff"


def select_regulatory_items(
    items: List[DigestItem],
    sent_item_keys: set[str],
    *,
    now: datetime | None = None,
    max_items: int = REGULATORY_TARGET_ITEMS,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    dedupe_exclusions: Counter[str] = Counter()

    ranked = sorted(
        items,
        key=lambda item: (
            regulatory_base_breakdown(item, now=now, sent_item_keys=sent_item_keys)["total"],
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )

    seen_ids = set()
    deduped: List[DigestItem] = []
    for item in ranked:
        unique_id = normalize_text(str(item.get("id", "")))
        if unique_id and unique_id in seen_ids:
            dedupe_exclusions["duplicate_id"] += 1
            continue
        if any(titles_are_similar(item.get("title", ""), other.get("title", "")) for other in deduped):
            dedupe_exclusions["similar_title"] += 1
            continue
        if unique_id:
            seen_ids.add(unique_id)
        deduped.append(item)

    selected: List[DigestItem] = []
    remaining = deduped[:]
    fallback_reason = ""
    best_remaining_score: int | None = None

    while len(selected) < max_items and remaining:
        scored_candidates: List[Tuple[int, DigestItem, Dict[str, int]]] = []
        for item in remaining:
            breakdown = regulatory_selection_breakdown(
                item,
                selected,
                now=now,
                sent_item_keys=sent_item_keys,
            )
            if not breakdown:
                continue
            scored_candidates.append((breakdown["total"], item, breakdown))

        if not scored_candidates:
            fallback_reason = "no_candidates_after_recall_cap_and_diversity"
            break

        scored_candidates.sort(
            key=lambda entry: (
                entry[0],
                entry[1].get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
                entry[1].get("title", ""),
            ),
            reverse=True,
        )
        best_score, best_item, best_breakdown = scored_candidates[0]
        best_remaining_score = best_score

        if best_score < REGULATORY_MIN_SELECTION_SCORE:
            fallback_reason = (
                f"best_remaining_score_below_threshold:{best_score}<{REGULATORY_MIN_SELECTION_SCORE}"
            )
            break

        selected.append(
            {
                **best_item,
                "selection_score": best_score,
                "score_breakdown": best_breakdown,
            }
        )
        remaining = [
            item
            for item in remaining
            if item.get("id", "") != best_item.get("id", "")
        ]

    selection_exclusions: Counter[str] = Counter()
    for item in remaining:
        selection_exclusions[
            classify_regulatory_skip_reason(
                item,
                selected,
                now=now,
                sent_item_keys=sent_item_keys,
            )
        ] += 1

    if len(selected) < max_items and not fallback_reason:
        fallback_reason = "insufficient_high_quality_candidates"

    return selected, {
        "filtered_count": len(deduped),
        "excluded_reasons": dedupe_exclusions + selection_exclusions,
        "fallback_reason": fallback_reason or "none",
        "best_remaining_score": best_remaining_score,
    }


def fetch_openfda_regulatory_items() -> Tuple[List[DigestItem], Dict[str, Any]]:
    results: List[DigestItem] = []
    excluded_reasons: Counter[str] = Counter()
    raw_count = 0

    for endpoint in REGULATORY_ENDPOINTS:
        try:
            resp = requests.get(
                endpoint["url"],
                params={
                    "limit": REGULATORY_CANDIDATE_LIMIT,
                    "sort": "report_date:desc",
                },
                timeout=30,
            )
            resp.raise_for_status()

            endpoint_items = resp.json().get("results", [])
            if not endpoint_items:
                excluded_reasons["empty_endpoint"] += 1
                continue

            for entry in endpoint_items:
                raw_count += 1

                title = (
                    entry.get("product_description")
                    or entry.get("reason_for_recall")
                    or entry.get("classification")
                    or "Untitled FDA enforcement item"
                )
                url = endpoint["url"]
                recall_reason = entry.get("reason_for_recall", "")
                firm = entry.get("recalling_firm", "")
                classification = entry.get("classification", "")
                status = entry.get("status", "")
                report_date = entry.get("report_date", "")
                initiation_date = entry.get("recall_initiation_date", "")
                published_at = parse_fda_datetime(report_date) or parse_fda_datetime(initiation_date)
                unique_id = (
                    entry.get("recall_number")
                    or entry.get("event_id")
                    or entry.get("res_event_number")
                    or title[:180]
                )

                raw_text = (
                    f"{endpoint['label']}. "
                    f"Title: {title}. "
                    f"Recall reason: {recall_reason}. "
                    f"Recalling firm: {firm}. "
                    f"Classification: {classification}. "
                    f"Status: {status}. "
                    f"Report date: {report_date}. "
                    f"Recall initiation date: {initiation_date}."
                )
                results.append(
                    build_regulatory_item(
                        item_id=str(unique_id).strip(),
                        title=title[:180],
                        summary=recall_reason,
                        source=endpoint["source"],
                        published_at=published_at,
                        url=url,
                        subcategory=endpoint["subcategory"],
                        organization=endpoint["organization"],
                        raw_source_type="openfda_api",
                        raw_text=raw_text,
                        firm_key=normalize_text(firm),
                        classification=classification,
                        status=status,
                    )
                )

        except Exception as exc:
            excluded_reasons["endpoint_error"] += 1
            print(f"Warning: failed regulatory endpoint {endpoint['url']}: {exc}")

    log_regulatory_source_debug(
        "openFDA Enforcement",
        raw_count,
        len(results),
        excluded_reasons,
    )
    return results, {
        "source": "openFDA Enforcement",
        "raw_count": raw_count,
        "normalized_count": len(results),
        "excluded_reasons": excluded_reasons,
    }


def fetch_regulatory_items(memory: DigestMemory | None = None) -> List[DigestItem]:
    sent_item_keys = get_sent_item_keys()
    source_results = [
        fetch_openfda_regulatory_items(),
        fetch_fda_press_release_items(),
        fetch_cms_regulatory_items(),
        fetch_onc_regulatory_items(),
        fetch_ocr_regulatory_items(),
    ]

    combined: List[DigestItem] = []
    combined_exclusions: Counter[str] = Counter()
    raw_total = 0

    for items, stats in source_results:
        combined.extend(items)
        raw_total += stats["raw_count"]
        combined_exclusions += stats["excluded_reasons"]

    selected, selection_stats = select_regulatory_items(
        combined,
        sent_item_keys,
        max_items=REGULATORY_TARGET_ITEMS,
    )
    combined_exclusions += selection_stats["excluded_reasons"]

    log_section_debug(
        "Regulatory",
        raw_total,
        selection_stats["filtered_count"],
        combined_exclusions,
        selected,
    )
    print(
        "Regulatory fallback reason:",
        selection_stats["fallback_reason"],
    )
    if selection_stats["best_remaining_score"] is not None:
        print(
            "Regulatory best remaining score:",
            selection_stats["best_remaining_score"],
        )
    return attach_priority_scores(selected, memory)


def get_real_items(memory: DigestMemory | None = None) -> List[DigestItem]:
    memory = memory or load_digest_memory()
    repo_items = fetch_github_repos(memory)
    news_items = fetch_news_items(memory)
    regulatory_items = fetch_regulatory_items(memory)

    print(
        "Final section counts:",
        f"Repos={len(repo_items)}",
        f"News={len(news_items)}",
        f"Regulatory={len(regulatory_items)}",
    )

    return repo_items + news_items + regulatory_items

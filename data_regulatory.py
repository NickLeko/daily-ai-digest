from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin

import feedparser
import requests

from app_logging import info, warning
from config import AppConfig, REGULATORY_TARGET_ITEMS, current_config
from memory import DigestMemory
from scoring import attach_priority_scores
from state import get_sent_item_keys

from data_common import (
    DigestItem,
    empty_source_stats,
    item_key,
    log_regulatory_source_debug,
    log_section_debug,
    normalize_text,
    parse_fda_datetime,
    parse_feed_datetime,
    parse_iso_datetime,
    strip_html,
    truncate,
)
from data_regulatory_select import regulatory_bucket, select_regulatory_items


REGULATORY_CANDIDATE_LIMIT = max(REGULATORY_TARGET_ITEMS * 8, 12)

REGULATORY_ENDPOINTS = [{'url': 'https://api.fda.gov/device/enforcement.json', 'label': 'FDA Device Enforcement', 'organization': 'FDA', 'source': 'openFDA Device Enforcement', 'subcategory': 'recall'}, {'url': 'https://api.fda.gov/drug/enforcement.json', 'label': 'FDA Drug Enforcement', 'organization': 'FDA', 'source': 'openFDA Drug Enforcement', 'subcategory': 'recall'}]

REGULATORY_FEED_SOURCES = [{'name': 'FDA Press Releases', 'feed_url': 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml', 'organization': 'FDA', 'source': 'FDA Press Releases', 'subcategory_hint': 'guidance', 'raw_source_type': 'rss', 'max_age_days': 21, 'strong_keywords': ['artificial intelligence', 'ai', 'digital health', 'machine learning', 'ml', 'device software', 'medical device software', 'software as a medical device', 'samd', 'clinical decision support', 'decision support', 'cds', 'algorithm'], 'medium_keyword_groups': {'software_workflow': ['software', 'automation', 'workflow'], 'governance': ['guidance', 'draft guidance', 'final guidance', 'transparency', 'monitoring', 'audit'], 'security': ['cybersecurity', 'security'], 'regulatory': ['medical device', 'software functions']}, 'broad_keywords': ['approval', 'drug', 'treatment', 'therapy', 'patient', 'voucher', 'meeting', 'public meeting']}, {'name': 'CMS Newsroom', 'page_url': 'https://www.cms.gov/about-cms/contact/newsroom', 'organization': 'CMS', 'source': 'CMS Newsroom', 'subcategory_hint': 'policy', 'raw_source_type': 'html_page', 'max_age_days': 30, 'strong_keywords': ['interoperability', 'fhir', 'api', 'apis', 'application programming interface', 'data exchange', 'claims attachments', 'electronic signatures', 'prior authorization', 'prior auth', 'utilization management', 'information blocking'], 'medium_keyword_groups': {'health_it': ['health it', 'digital', 'electronic', 'automation', 'workflow'], 'ops': ['reimbursement', 'payment', 'claims', 'billing', 'attachments', 'coverage determination'], 'policy': ['final rule', 'proposed rule', 'rule', 'standards', 'transparency'], 'governance': ['audit', 'monitoring', 'program integrity']}, 'broad_keywords': ['coverage', 'enrollment', 'committee', 'advisory', 'summit', 'meeting', 'readout', 'stability', 'affordability', 'patient care', 'modernize', 'innovation']}, {'name': 'ASTP/ONC Blog', 'page_url': 'https://www.healthit.gov/buzz-blog/', 'organization': 'ASTP/ONC', 'source': 'ASTP/ONC Blog', 'subcategory_hint': 'interoperability', 'raw_source_type': 'discovered_rss', 'max_age_days': 90, 'strong_keywords': ['interoperability', 'fhir', 'api', 'data exchange', 'information blocking', 'uscdi', 'tefca', 'certified health it', 'health it certification', 'artificial intelligence', 'ai', 'clinical decision support', 'decision support'], 'medium_keyword_groups': {'health_it': ['health it', 'digital health', 'software', 'algorithm', 'automation'], 'governance': ['transparency', 'monitoring', 'audit'], 'workflow': ['behavioral health', 'diagnostic images', 'patient engagement', 'laboratory data standards']}, 'broad_keywords': ['ideas', 'future', 'insights', 'updates', 'better tomorrow']}, {'name': 'HHS Press Room OCR', 'page_url': 'https://www.hhs.gov/press-room/index.html', 'organization': 'OCR', 'source': 'HHS Press Room', 'subcategory_hint': 'privacy', 'raw_source_type': 'disabled_source', 'disabled_reason': 'blocked_by_hhs_403', 'strong_keywords': ['hipaa', 'privacy', 'security', 'breach notification', 'patient records', 'confidentiality', 'part 2'], 'medium_keyword_groups': {'governance': ['audit', 'monitoring', 'investigation', 'enforcement'], 'security': ['cybersecurity', 'ransomware', 'breach'], 'privacy': ['privacy', 'access', 'records']}, 'broad_keywords': ['settlement', 'penalty', 'announces', 'program']}]

FEED_LINK_PATTERNS = [
    re.compile(
        r"<link[^>]+rel=[\"'][^\"']*alternate[^\"']*[\"'][^>]+type=[\"'](?:application/(?:rss|atom)\+xml|application/xml|text/xml)[\"'][^>]+href=[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        r"<a[^>]+href=[\"']([^\"']+(?:rss(?:\.xml)?|feed|atom)(?:[^\"']*)?)[\"']",
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

REGULATORY_SUBCATEGORY_BONUS = {'recall': 0, 'enforcement': 0, 'guidance': 20, 'policy': 16, 'reimbursement': 18, 'interoperability': 20, 'privacy': 18, 'safety_alert': 6}


def regulatory_candidate_limit(target_items: int) -> int:
    return max(int(target_items) * 8, 12)


def discover_feed_url(page_url: str) -> str | None:
    try:
        resp = requests.get(
            page_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except Exception as exc:
        warning("Feed discovery failed", page_url=page_url, error=str(exc))
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

def fetch_feed_regulatory_items(
    source_config: Dict[str, Any],
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
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
    entries = list(feed.entries[:candidate_limit])
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

def fetch_fda_press_release_items(
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(
        REGULATORY_FEED_SOURCES[0],
        candidate_limit=candidate_limit,
    )

def fetch_cms_regulatory_items(
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
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
        warning(
            "CMS newsroom fetch failed",
            page_url=source_config["page_url"],
            error=str(exc),
        )
        log_regulatory_source_debug(source_config["name"], 0, 0, excluded_reasons)
        return [], empty_source_stats(source_config["name"], excluded_reasons)

    raw_entries = parse_cms_newsroom_html(resp.text)
    results: List[DigestItem] = []

    if not raw_entries:
        excluded_reasons["page_parse_error"] += 1

    for entry in raw_entries[:candidate_limit]:
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

def fetch_onc_regulatory_items(
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(
        REGULATORY_FEED_SOURCES[2],
        candidate_limit=candidate_limit,
    )

def fetch_ocr_regulatory_items(
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    return fetch_feed_regulatory_items(
        REGULATORY_FEED_SOURCES[3],
        candidate_limit=candidate_limit,
    )

def fetch_openfda_regulatory_items(
    *,
    candidate_limit: int = REGULATORY_CANDIDATE_LIMIT,
) -> Tuple[List[DigestItem], Dict[str, Any]]:
    results: List[DigestItem] = []
    excluded_reasons: Counter[str] = Counter()
    raw_count = 0

    for endpoint in REGULATORY_ENDPOINTS:
        try:
            resp = requests.get(
                endpoint["url"],
                params={
                    "limit": candidate_limit,
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
            warning(
                "Regulatory endpoint failed",
                url=endpoint["url"],
                error=str(exc),
            )

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

def fetch_regulatory_items(
    memory: DigestMemory | None = None,
    *,
    config: AppConfig | None = None,
) -> List[DigestItem]:
    resolved = config or current_config()
    sent_item_keys = get_sent_item_keys(config=resolved)
    candidate_limit = regulatory_candidate_limit(resolved.regulatory_target_items)
    source_results = [
        fetch_openfda_regulatory_items(candidate_limit=candidate_limit),
        fetch_fda_press_release_items(candidate_limit=candidate_limit),
        fetch_cms_regulatory_items(candidate_limit=candidate_limit),
        fetch_onc_regulatory_items(candidate_limit=candidate_limit),
        fetch_ocr_regulatory_items(candidate_limit=candidate_limit),
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
        max_items=resolved.regulatory_target_items,
    )
    combined_exclusions += selection_stats["excluded_reasons"]

    log_section_debug(
        "Regulatory",
        raw_total,
        selection_stats["filtered_count"],
        combined_exclusions,
        selected,
    )
    info(
        "Regulatory fallback",
        reason=selection_stats["fallback_reason"],
    )
    if selection_stats["best_remaining_score"] is not None:
        info(
            "Regulatory best remaining score",
            score=selection_stats["best_remaining_score"],
        )
    return attach_priority_scores(selected, memory, config=resolved)

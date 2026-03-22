from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

import feedparser
import requests

from config import GITHUB_TOKEN, MAX_ITEMS_PER_CATEGORY, NEWS_FEED_URLS


DigestItem = Dict[str, str]

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


def iso_days_ago(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def truncate(text: str, max_len: int = 1200) -> str:
    text = " ".join((text or "").split())
    return text[:max_len]


def repo_is_relevant(name: str, description: str) -> bool:
    haystack = f"{name} {description}".lower()
    return any(keyword in haystack for keyword in REPO_RELEVANT_KEYWORDS)


def fetch_github_repos() -> List[DigestItem]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    created_after = iso_days_ago(14)
    query = f"created:>{created_after} stars:>20"

    resp = requests.get(
        "https://api.github.com/search/repositories",
        headers=headers,
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 20,
        },
        timeout=30,
    )
    resp.raise_for_status()

    items = resp.json().get("items", [])
    results: List[DigestItem] = []

    for repo in items:
        full_name = repo.get("full_name", "Untitled repo")
        description = repo.get("description", "") or ""

        if not repo_is_relevant(full_name, description):
            continue

        raw_text = (
            f"{full_name}: {description}. "
            f"Language: {repo.get('language', 'Unknown')}. "
            f"Stars: {repo.get('stargazers_count', 0)}. "
            f"Updated at: {repo.get('updated_at', '')}. "
            f"Topics: {', '.join(repo.get('topics', [])[:6])}."
        )

        results.append(
            {
                "category": "Repo",
                "title": full_name,
                "url": repo.get("html_url", ""),
                "raw_text": truncate(raw_text),
            }
        )

        if len(results) >= MAX_ITEMS_PER_CATEGORY:
            break

    return results


def fetch_news_items() -> List[DigestItem]:
    results: List[DigestItem] = []

    for feed_url in NEWS_FEED_URLS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:MAX_ITEMS_PER_CATEGORY]:
            summary = entry.get("summary", "") or entry.get("description", "")
            raw_text = f"{entry.get('title', '')}. {summary}"
            results.append(
                {
                    "category": "News",
                    "title": entry.get("title", "Untitled news item"),
                    "url": entry.get("link", ""),
                    "raw_text": truncate(raw_text),
                }
            )

    seen = set()
    deduped = []
    for item in results:
        key = item["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped[:MAX_ITEMS_PER_CATEGORY]


def fetch_openfda_regulatory_items() -> List[DigestItem]:
    results: List[DigestItem] = []

    endpoints = [
        {
            "url": "https://api.fda.gov/device/enforcement.json",
            "label": "FDA Device Enforcement",
        },
        {
            "url": "https://api.fda.gov/drug/enforcement.json",
            "label": "FDA Drug Enforcement",
        },
    ]

    for endpoint in endpoints:
        try:
            resp = requests.get(
                endpoint["url"],
                params={
                    "limit": MAX_ITEMS_PER_CATEGORY,
                    "sort": "report_date:desc",
                },
                timeout=30,
            )
            resp.raise_for_status()

            items = resp.json().get("results", [])
            for entry in items:
                title = (
                    entry.get("product_description")
                    or entry.get("reason_for_recall")
                    or entry.get("classification")
                    or "Untitled FDA enforcement item"
                )

                recall_reason = entry.get("reason_for_recall", "")
                firm = entry.get("recalling_firm", "")
                classification = entry.get("classification", "")
                status = entry.get("status", "")
                report_date = entry.get("report_date", "")

                raw_text = (
                    f"{endpoint['label']}. "
                    f"Title: {title}. "
                    f"Recall reason: {recall_reason}. "
                    f"Recalling firm: {firm}. "
                    f"Classification: {classification}. "
                    f"Status: {status}. "
                    f"Report date: {report_date}."
                )

                results.append(
                    {
                        "category": "Regulatory",
                        "title": title[:180],
                        "url": endpoint["url"],
                        "raw_text": truncate(raw_text),
                    }
                )

                if len(results) >= MAX_ITEMS_PER_CATEGORY:
                    return results

        except Exception as e:
            print(f"Warning: failed regulatory endpoint {endpoint['url']}: {e}")

    return results[:MAX_ITEMS_PER_CATEGORY]


def get_real_items() -> List[DigestItem]:
    repo_items = fetch_github_repos()
    print("Repos:", len(repo_items))

    news_items = fetch_news_items()
    print("News:", len(news_items))

    regulatory_items = fetch_openfda_regulatory_items()
    print("Regulatory:", len(regulatory_items))

    return (
        repo_items[:MAX_ITEMS_PER_CATEGORY]
        + news_items[:MAX_ITEMS_PER_CATEGORY]
        + regulatory_items[:MAX_ITEMS_PER_CATEGORY]
    )
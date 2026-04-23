from __future__ import annotations

import re
from collections import Counter
from typing import List

import requests

from config import AppConfig, current_config
from memory import DigestMemory
from state import get_sent_item_keys

from data_common import (
    DigestItem,
    iso_days_ago,
    item_key,
    log_section_debug,
    parse_iso_datetime,
    select_scored_items,
    truncate,
)


REPO_RELEVANT_KEYWORDS = ['ai', 'llm', 'rag', 'agent', 'agents', 'eval', 'evaluation', 'openai', 'anthropic', 'embedding', 'vector', 'search', 'retrieval', 'health', 'healthcare', 'medical', 'clinical', 'ehr', 'fhir', 'workflow']

REPO_EXCLUDED_KEYWORDS = ['banlist', 'blockchain', 'coin', 'crypto', 'defi', 'game', 'gaming', 'market', 'monero', 'nft', 'token', 'trading', 'wallet', 'web3']


def repo_is_relevant(name: str, description: str) -> bool:
    haystack = f"{name} {description}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))

    if any(keyword in tokens for keyword in REPO_EXCLUDED_KEYWORDS):
        return False

    if not description.strip():
        return False

    return any(keyword in tokens for keyword in REPO_RELEVANT_KEYWORDS)

def fetch_github_repos(
    memory: DigestMemory | None = None,
    *,
    config: AppConfig | None = None,
) -> List[DigestItem]:
    resolved = config or current_config()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if resolved.github_token:
        headers["Authorization"] = f"Bearer {resolved.github_token}"

    sent_item_keys = get_sent_item_keys(config=resolved)
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
        limit=resolved.max_items_per_category,
        memory=memory,
        enforce_repo_generic_cap=True,
        excluded_reasons=excluded_reasons,
    )
    log_section_debug("Repos", len(raw_items), len(results), excluded_reasons, selected)
    return selected

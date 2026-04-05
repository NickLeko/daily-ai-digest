from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from config import (
    OBJECTIVE_SCORE_WEIGHTS,
    PRIORITY_THEME_RULES,
    SCORING_WEIGHTS,
    TRACKED_ENTITY_RULES,
)
from memory import DigestMemory, build_history_context


DigestItem = Dict[str, Any]

DIMENSION_KEYS = [
    "career_relevance",
    "build_relevance",
    "content_potential",
    "regulatory_significance",
    "side_hustle_relevance",
    "timeliness",
    "novelty",
    "theme_momentum",
]

OBJECTIVE_LABELS = {
    "career": "Top item for career",
    "build": "Top item for build",
    "content": "Top item for content",
    "regulatory": "Top item for regulatory",
}

CATEGORY_BASELINES = {
    "Repo": {
        "build_relevance": 1.2,
        "content_potential": 0.4,
        "side_hustle_relevance": 0.4,
    },
    "News": {
        "career_relevance": 0.7,
        "content_potential": 0.9,
    },
    "Regulatory": {
        "career_relevance": 1.1,
        "content_potential": 0.6,
        "regulatory_significance": 2.2,
    },
}

REGULATORY_KEYWORDS = [
    "rule",
    "guidance",
    "fda",
    "cms",
    "onc",
    "hipaa",
    "privacy",
    "security",
    "compliance",
    "audit",
    "interoperability",
    "prior authorization",
    "prior auth",
    "claims attachments",
    "reimbursement",
    "payment",
    "tefca",
    "uscdi",
]

CONTENT_SIGNAL_KEYWORDS = [
    "launch",
    "policy",
    "benchmark",
    "roadmap",
    "workflow",
    "fhir",
    "interoperability",
    "prior authorization",
    "documentation",
    "ambient",
    "scheduling",
    "referral",
    "denials",
    "reimbursement",
]

WORKFLOW_WEDGE_RULES = {
    "prior_auth": {
        "label": "prior auth",
        "keywords": [
            "prior authorization",
            "prior auth",
            "utilization management",
            "utilization review",
            "payer auth",
        ],
    },
    "referral_intake": {
        "label": "referral/intake",
        "keywords": [
            "referral",
            "referrals",
            "referral management",
            "intake",
            "patient intake",
            "eligibility",
            "benefits verification",
        ],
    },
    "documentation_ambient": {
        "label": "documentation/ambient",
        "keywords": [
            "documentation",
            "ambient",
            "scribe",
            "charting",
            "clinical note",
            "note capture",
        ],
    },
    "scheduling": {
        "label": "scheduling",
        "keywords": [
            "scheduling",
            "appointment",
            "patient access",
            "reschedule",
            "template utilization",
        ],
    },
    "rcm_denials": {
        "label": "RCM/denials",
        "keywords": [
            "revenue cycle",
            "rcm",
            "claims",
            "claims attachments",
            "denials",
            "denial",
            "appeals",
            "billing",
            "reimbursement",
        ],
    },
    "interoperability": {
        "label": "interoperability",
        "keywords": [
            "interoperability",
            "fhir",
            "hl7",
            "tefca",
            "uscdi",
            "api",
            "apis",
            "data exchange",
            "ehr",
            "epic",
            "cerner",
        ],
    },
    "provider_admin_ops": {
        "label": "provider/admin ops",
        "keywords": [
            "contact center",
            "call center",
            "operations",
            "admin",
            "back office",
            "forms",
            "fax",
            "inbox",
            "workflow automation",
        ],
    },
    "care_coordination": {
        "label": "care coordination",
        "keywords": [
            "care coordination",
            "case management",
            "transition of care",
            "discharge",
            "follow-up",
            "care management",
        ],
    },
}

HEALTHCARE_CONTEXT_KEYWORDS = [
    "healthcare",
    "health care",
    "health system",
    "provider",
    "payer",
    "hospital",
    "clinic",
    "clinical",
    "patient",
    "ehr",
    "epic",
    "cerner",
    "fhir",
    "tefca",
    "cms",
    "onc",
    "prior authorization",
    "referral",
    "documentation",
    "scheduling",
    "revenue cycle",
    "interoperability",
]

BUYER_OPERATOR_KEYWORDS = [
    "operations",
    "operator",
    "ops",
    "implementation",
    "deployment",
    "pilot",
    "adoption",
    "roi",
    "throughput",
    "turnaround",
    "handoff",
    "manual work",
    "back office",
    "contact center",
    "patient access",
    "revenue cycle",
    "claims",
    "prior authorization",
    "denials",
    "referral",
    "documentation",
    "care coordination",
]

ACTIONABILITY_KEYWORDS = [
    "final rule",
    "proposed rule",
    "guidance",
    "deadline",
    "launch",
    "announced",
    "open source",
    "implementation",
    "deployment",
    "pilot",
    "standard",
    "standards",
    "integration",
    "api",
    "fhir",
    "reimbursement",
    "prior authorization",
    "claims attachments",
]

INTEROPERABILITY_REIMBURSEMENT_KEYWORDS = [
    "interoperability",
    "fhir",
    "hl7",
    "tefca",
    "uscdi",
    "api",
    "claims attachments",
    "electronic signatures",
    "prior authorization",
    "prior auth",
    "reimbursement",
    "payment",
    "coverage determination",
]

GENERIC_DEVTOOL_KEYWORDS = [
    "sdk",
    "framework",
    "toolkit",
    "library",
    "wrapper",
    "api wrapper",
    "api client",
    "cli",
    "command line",
    "session manager",
    "coding agent",
    "developer tool",
    "devtool",
    "orchestration",
    "multi-agent",
    "agent framework",
    "starter",
    "boilerplate",
    "template",
    "terminal",
    "mcp",
    "model context protocol",
    "task runner",
    "autonomous",
]

CODING_AGENT_TOOLING_KEYWORDS = [
    "coding agent",
    "session manager",
    "code review",
    "developer workflow",
    "terminal ui",
    "shell workflow",
]

SPECULATIVE_LOW_ROI_KEYWORDS = [
    "quantum",
    "agi",
    "artificial general intelligence",
    "future of ai",
    "future of healthcare",
    "vision",
    "moonshot",
    "thought leadership",
    "could someday",
]

HEALTHCARE_REPO_EXEMPTION_KEYWORDS = [
    "prior authorization",
    "prior auth",
    "claims",
    "denials",
    "referral",
    "intake",
    "documentation",
    "ambient",
    "scheduling",
    "care coordination",
    "fhir",
    "interoperability",
    "hipaa",
    "ehr",
    "epic",
    "tefca",
]


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


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


def item_text_blob(item: DigestItem) -> str:
    return " ".join(
        str(part).strip()
        for part in [
            item.get("title", ""),
            item.get("raw_text", ""),
            item.get("summary", ""),
            item.get("why_it_matters", ""),
            item.get("source", ""),
            item.get("organization", ""),
            item.get("subcategory", ""),
            item.get("topic_key", ""),
        ]
        if str(part).strip()
    )


def extract_theme_hits(item: DigestItem) -> Dict[str, List[str]]:
    text = item_text_blob(item)
    hits: Dict[str, List[str]] = {}
    for theme_key, config in PRIORITY_THEME_RULES.items():
        theme_hits = matched_keywords(config.get("keywords", []), text)
        if theme_hits:
            hits[theme_key] = theme_hits
    return hits


def extract_entity_keys(item: DigestItem) -> List[str]:
    text = item_text_blob(item)
    entity_keys = set()

    for entity_key, keywords in TRACKED_ENTITY_RULES.items():
        if matched_keywords(keywords, text):
            entity_keys.add(entity_key)

    organization = normalize_text(str(item.get("organization", "") or ""))
    if organization:
        entity_keys.add(f"org:{organization}")

    source = normalize_text(str(item.get("source", "") or ""))
    if source:
        entity_keys.add(f"source:{source}")

    if item.get("category") == "Repo":
        title = str(item.get("title", "") or "")
        if "/" in title:
            owner = normalize_text(title.split("/", 1)[0])
            if owner:
                entity_keys.add(f"owner:{owner}")

    firm_key = normalize_text(str(item.get("firm_key", "") or ""))
    if firm_key:
        entity_keys.add(f"firm:{firm_key}")

    return sorted(entity_keys)


def extract_workflow_wedge_hits(text: str) -> Dict[str, List[str]]:
    hits: Dict[str, List[str]] = {}
    for wedge_key, rule in WORKFLOW_WEDGE_RULES.items():
        wedge_hits = matched_keywords(rule.get("keywords", []), text)
        if wedge_hits:
            hits[wedge_key] = wedge_hits
    return hits


def workflow_wedge_labels(wedge_hits: Dict[str, List[str]]) -> List[str]:
    return [
        WORKFLOW_WEDGE_RULES.get(wedge_key, {}).get("label", wedge_key)
        for wedge_key in WORKFLOW_WEDGE_RULES
        if wedge_key in wedge_hits
    ]


def has_explicit_healthcare_context(text: str) -> bool:
    return bool(matched_keywords(HEALTHCARE_CONTEXT_KEYWORDS, text))


def operator_relevance_level(
    item: DigestItem,
    *,
    text: str,
    theme_hits: Dict[str, List[str]],
    wedge_hits: Dict[str, List[str]],
) -> str:
    operator_hits = matched_keywords(BUYER_OPERATOR_KEYWORDS, text)
    if wedge_hits and (
        operator_hits
        or item.get("category") == "Regulatory"
        or "healthcare_admin_automation" in theme_hits
    ):
        return "high"
    if wedge_hits or operator_hits or has_explicit_healthcare_context(text):
        return "medium"
    return "low"


def actionability_level(
    item: DigestItem,
    *,
    text: str,
    wedge_hits: Dict[str, List[str]],
) -> str:
    action_hits = matched_keywords(ACTIONABILITY_KEYWORDS, text)
    if item.get("category") == "Regulatory":
        return "high"
    if wedge_hits and action_hits:
        return "high"
    if wedge_hits or action_hits:
        return "medium"
    return "low"


def is_generic_devtool_item(
    item: DigestItem,
    *,
    text: str,
    theme_hits: Dict[str, List[str]],
    wedge_hits: Dict[str, List[str]],
) -> bool:
    generic_hits = matched_keywords(GENERIC_DEVTOOL_KEYWORDS, text)
    if item.get("category") != "Repo":
        return bool(generic_hits) and not wedge_hits and not has_explicit_healthcare_context(text)
    if len(generic_hits) >= 2:
        return True
    return bool(generic_hits) and (
        "agents_workflows" in theme_hits
        or "llm_eval_rag_governance_safety" in theme_hits
    )


def repo_cap_exempt(
    *,
    text: str,
    theme_hits: Dict[str, List[str]],
    wedge_hits: Dict[str, List[str]],
) -> bool:
    governance_hits = matched_keywords(
        ["eval", "evaluation", "benchmark", "audit", "monitoring", "privacy", "security"],
        text,
    )
    return bool(
        wedge_hits
        or matched_keywords(HEALTHCARE_REPO_EXEMPTION_KEYWORDS, text)
        or ("healthcare_admin_automation" in theme_hits)
        or ("healthcare_ai_pm" in theme_hits and governance_hits)
        or (
            governance_hits
            and matched_keywords(INTEROPERABILITY_REIMBURSEMENT_KEYWORDS, text)
        )
    )


def is_speculative_low_roi_item(
    item: DigestItem,
    *,
    text: str,
    wedge_hits: Dict[str, List[str]],
) -> bool:
    if not matched_keywords(SPECULATIVE_LOW_ROI_KEYWORDS, text):
        return False
    if item.get("category") == "Regulatory":
        return False
    if wedge_hits or matched_keywords(INTEROPERABILITY_REIMBURSEMENT_KEYWORDS, text):
        return False
    return not matched_keywords(BUYER_OPERATOR_KEYWORDS, text)


def build_item_profile(
    item: DigestItem,
    *,
    theme_hits: Dict[str, List[str]],
) -> Dict[str, Any]:
    text = item_text_blob(item)
    wedge_hits = extract_workflow_wedge_hits(text)
    workflow_wedges = workflow_wedge_labels(wedge_hits)
    explicit_healthcare_context = has_explicit_healthcare_context(text)
    interoperability_hits = matched_keywords(INTEROPERABILITY_REIMBURSEMENT_KEYWORDS, text)
    generic_devtool = is_generic_devtool_item(
        item,
        text=text,
        theme_hits=theme_hits,
        wedge_hits=wedge_hits,
    )
    generic_repo_cap_exempt = generic_devtool and repo_cap_exempt(
        text=text,
        theme_hits=theme_hits,
        wedge_hits=wedge_hits,
    )

    return {
        "text": text,
        "workflow_wedge_keys": [
            wedge_key for wedge_key in WORKFLOW_WEDGE_RULES if wedge_key in wedge_hits
        ],
        "workflow_wedges": workflow_wedges,
        "explicit_healthcare_context": explicit_healthcare_context,
        "operator_relevance": operator_relevance_level(
            item,
            text=text,
            theme_hits=theme_hits,
            wedge_hits=wedge_hits,
        ),
        "near_term_actionability": actionability_level(
            item,
            text=text,
            wedge_hits=wedge_hits,
        ),
        "explicit_interoperability_reimbursement": bool(interoperability_hits),
        "is_generic_devtool": generic_devtool,
        "generic_repo_cap_exempt": generic_repo_cap_exempt,
        "is_coding_agent_tool": bool(matched_keywords(CODING_AGENT_TOOLING_KEYWORDS, text)),
        "is_speculative_low_roi": is_speculative_low_roi_item(
            item,
            text=text,
            wedge_hits=wedge_hits,
        ),
    }


def clamp_score(value: float) -> float:
    return max(0.0, min(5.0, round(value, 2)))


def timeliness_score(item: DigestItem, *, now: datetime) -> float:
    published_at = item.get("published_at")
    if not isinstance(published_at, datetime):
        return 2.5

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age = now - published_at.astimezone(timezone.utc)
    if age <= timedelta(hours=24):
        return 5.0
    if age <= timedelta(days=3):
        return 4.2
    if age <= timedelta(days=7):
        return 3.4
    if age <= timedelta(days=14):
        return 2.5
    if age <= timedelta(days=30):
        return 1.7
    return 0.8


def novelty_score(history_context: Dict[str, Any]) -> float:
    seen_count = int(history_context.get("item_seen_count", 0) or 0)
    days_since_last_seen = history_context.get("days_since_last_seen")

    if seen_count == 0:
        return 5.0
    if days_since_last_seen is None:
        return 3.5
    if days_since_last_seen >= 30:
        return 3.4
    if days_since_last_seen >= 14:
        return 2.4
    if days_since_last_seen >= 7:
        return 1.4
    return 0.4


def theme_momentum_score(history_context: Dict[str, Any]) -> float:
    recent_theme_hits = int(history_context.get("recent_theme_hits", 0) or 0)
    recent_entity_hits = int(history_context.get("recent_entity_hits", 0) or 0)
    combined = recent_theme_hits + recent_entity_hits
    if combined <= 0:
        return 0.4
    if combined == 1:
        return 1.5
    if combined <= 3:
        return 2.6
    if combined <= 5:
        return 3.6
    return 4.6


def compute_dimension_scores(
    item: DigestItem,
    *,
    item_profile: Dict[str, Any],
    theme_hits: Dict[str, List[str]],
    history_context: Dict[str, Any],
    now: datetime,
) -> Dict[str, float]:
    scores = {dimension: 0.0 for dimension in DIMENSION_KEYS}

    for dimension, baseline in CATEGORY_BASELINES.get(item.get("category", ""), {}).items():
        scores[dimension] += baseline

    for theme_key, hits in theme_hits.items():
        theme_config = PRIORITY_THEME_RULES.get(theme_key, {})
        scale = min(1.35, 0.85 + (0.1 * len(hits)))
        for dimension, boost in theme_config.get("dimension_boosts", {}).items():
            scores[dimension] += boost * scale

    text = item_profile["text"]
    if matched_keywords(REGULATORY_KEYWORDS, text):
        scores["regulatory_significance"] += 0.9
        scores["career_relevance"] += 0.3

    if matched_keywords(CONTENT_SIGNAL_KEYWORDS, text):
        scores["content_potential"] += 0.5

    if item.get("category") == "Repo":
        scores["build_relevance"] += 0.4

    workflow_wedge_keys = item_profile.get("workflow_wedge_keys", [])
    if workflow_wedge_keys:
        scale = min(1.35, 1.0 + (0.1 * (len(workflow_wedge_keys) - 1)))
        scores["career_relevance"] += 1.3 * scale
        scores["build_relevance"] += 1.5 * scale
        scores["side_hustle_relevance"] += 1.0
        scores["content_potential"] += 0.3
        if any(
            wedge_key in {"prior_auth", "rcm_denials", "interoperability"}
            for wedge_key in workflow_wedge_keys
        ):
            scores["regulatory_significance"] += 0.9

    operator_relevance = item_profile.get("operator_relevance")
    if operator_relevance == "high":
        scores["career_relevance"] += 1.0
        scores["build_relevance"] += 0.8
        scores["content_potential"] += 0.2
    elif operator_relevance == "medium":
        scores["career_relevance"] += 0.45
        scores["build_relevance"] += 0.35

    actionability = item_profile.get("near_term_actionability")
    if actionability == "high":
        scores["career_relevance"] += 0.7
        scores["build_relevance"] += 0.9
        scores["regulatory_significance"] += 0.4
        scores["content_potential"] += 0.15
    elif actionability == "medium":
        scores["career_relevance"] += 0.3
        scores["build_relevance"] += 0.45

    if item_profile.get("explicit_interoperability_reimbursement"):
        scores["regulatory_significance"] += 1.0
        scores["career_relevance"] += 0.5
        scores["build_relevance"] += 0.3

    if item_profile.get("is_generic_devtool"):
        penalty = 0.45 if item_profile.get("generic_repo_cap_exempt") else 1.7
        scores["career_relevance"] -= penalty
        scores["build_relevance"] -= penalty + (0.4 if not item_profile.get("generic_repo_cap_exempt") else 0.0)
        scores["content_potential"] -= 0.25 if item_profile.get("generic_repo_cap_exempt") else 1.0
        scores["side_hustle_relevance"] -= 0.35 if item_profile.get("generic_repo_cap_exempt") else 1.1

    if item_profile.get("is_coding_agent_tool"):
        scores["career_relevance"] -= 0.5
        scores["build_relevance"] -= 0.9
        scores["content_potential"] -= 0.2

    if item_profile.get("is_speculative_low_roi"):
        scores["career_relevance"] -= 1.3
        scores["build_relevance"] -= 1.5
        scores["content_potential"] -= 0.7
        scores["side_hustle_relevance"] -= 1.0

    scores["timeliness"] = timeliness_score(item, now=now)
    scores["novelty"] = novelty_score(history_context)
    scores["theme_momentum"] = theme_momentum_score(history_context)

    return {
        dimension: clamp_score(value)
        for dimension, value in scores.items()
    }


def compute_objective_scores(dimension_scores: Dict[str, float]) -> Dict[str, float]:
    return {
        objective: round(
            sum(
                dimension_scores.get(dimension, 0.0) * weight
                for dimension, weight in weights.items()
            ),
            2,
        )
        for objective, weights in OBJECTIVE_SCORE_WEIGHTS.items()
    }


def strongest_dimensions(dimension_scores: Dict[str, float]) -> List[str]:
    ranked = sorted(
        dimension_scores.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    return [name for name, _value in ranked[:3]]


def priority_score(dimension_scores: Dict[str, float]) -> float:
    total = sum(
        dimension_scores.get(dimension, 0.0) * weight
        for dimension, weight in SCORING_WEIGHTS.items()
    )
    return round(total, 2)


def score_item(
    item: DigestItem,
    *,
    memory: DigestMemory,
    now: datetime,
) -> DigestItem:
    theme_hits = extract_theme_hits(item)
    matched_themes = sorted(theme_hits.keys())
    item_profile = build_item_profile(item, theme_hits=theme_hits)
    entity_keys = extract_entity_keys(item)
    history_context = build_history_context(
        item,
        memory,
        themes=matched_themes,
        entities=entity_keys,
        now=now,
    )
    dimension_scores = compute_dimension_scores(
        item,
        item_profile=item_profile,
        theme_hits=theme_hits,
        history_context=history_context,
        now=now,
    )
    objective_scores = compute_objective_scores(dimension_scores)

    return {
        **item,
        "matched_themes": matched_themes,
        "entity_keys": entity_keys,
        "workflow_wedges": item_profile.get("workflow_wedges", []),
        "operator_relevance": item_profile.get("operator_relevance", "low"),
        "near_term_actionability": item_profile.get("near_term_actionability", "low"),
        "explicit_healthcare_context": bool(item_profile.get("explicit_healthcare_context")),
        "explicit_interoperability_reimbursement": bool(
            item_profile.get("explicit_interoperability_reimbursement")
        ),
        "is_generic_devtool": bool(item_profile.get("is_generic_devtool")),
        "generic_repo_cap_exempt": bool(item_profile.get("generic_repo_cap_exempt")),
        "is_speculative_low_roi": bool(item_profile.get("is_speculative_low_roi")),
        "score_dimensions": dimension_scores,
        "objective_scores": objective_scores,
        "priority_score": priority_score(dimension_scores),
        "score_focus": strongest_dimensions(dimension_scores),
        "history_context": history_context,
    }


def attach_priority_scores(
    items: List[DigestItem],
    memory: DigestMemory | None,
    *,
    now: datetime | None = None,
    sort_items: bool = True,
) -> List[DigestItem]:
    now = now or datetime.now(timezone.utc)
    memory = memory or {"version": 1, "events": []}
    scored = [score_item(item, memory=memory, now=now) for item in items]
    if not sort_items:
        return scored
    return sort_items_by_priority(scored)


def sort_items_by_priority(items: List[DigestItem]) -> List[DigestItem]:
    return sorted(
        items,
        key=lambda item: (
            float(item.get("priority_score", 0.0) or 0.0),
            float(max((item.get("objective_scores", {}) or {}).values(), default=0.0)),
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )


def build_top_picks(items: List[DigestItem]) -> List[Dict[str, Any]]:
    picks: List[Dict[str, Any]] = []

    for objective, label in OBJECTIVE_LABELS.items():
        ranked = sorted(
            items,
            key=lambda item: (
                float((item.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
                float(item.get("priority_score", 0.0) or 0.0),
            ),
            reverse=True,
        )

        choice = ranked[0] if ranked else None
        if not choice:
            continue

        picks.append(
            {
                "objective": objective,
                "label": label,
                "item": choice,
                "score": float((choice.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0),
            }
        )

    return picks

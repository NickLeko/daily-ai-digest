from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from config import (
    AppConfig,
    OBJECTIVE_SCORE_WEIGHTS,
    SCORING_WEIGHTS,
)
from memory import DigestMemory, build_history_context
from selection_policy import ITEM_OBJECTIVE_MIN_SCORES
from signal_quality import classify_operator_materiality
from taxonomy import PRIORITY_THEME_RULES, TRACKED_ENTITY_RULES, WORKFLOW_RULES


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

OBJECTIVE_DISPLAY_ORDER = ["career", "build", "content", "regulatory"]

OBJECTIVE_EMPTY_MESSAGES = {
    "career": "No high-signal career fit today.",
    "build": "No high-signal build fit today.",
    "content": "No strong content hook today.",
    "regulatory": "No high-signal regulatory item today.",
}

OBJECTIVE_MIN_SCORE = ITEM_OBJECTIVE_MIN_SCORES

OBJECTIVE_REUSE_MARGIN = {
    "career": 1.9,
    "build": 1.6,
    "content": 1.5,
    "regulatory": 2.1,
}

OBJECTIVE_ORDER_RANK = {
    "career": 0,
    "content": 1,
    "build": 2,
    "regulatory": 3,
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
    workflow_key: {
        "label": str(rule["label"]),
        "keywords": list(rule["keywords"]),
    }
    for workflow_key, rule in WORKFLOW_RULES.items()
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

REPO_STRONG_HEALTHCARE_ANCHOR_KEYWORDS = [
    "healthcare",
    "health care",
    "health system",
    "provider",
    "payer",
    "hospital",
    "clinic",
    "clinical",
    "medical",
    "patient",
    "ehr",
    "epic",
    "cerner",
    "fhir",
    "hl7",
    "tefca",
    "uscdi",
    "cms",
    "onc",
    "hipaa",
    "prior authorization",
    "prior auth",
    "utilization management",
    "utilization review",
    "claims attachments",
    "denials",
    "denial",
    "revenue cycle",
    "rcm",
    "referral",
    "patient intake",
    "benefits verification",
    "ambient",
    "scribe",
    "clinical note",
    "note capture",
    "patient access",
    "care coordination",
]

REPO_CONTEXT_REQUIRED_WEDGE_KEYWORDS = [
    "documentation",
    "scheduling",
    "appointment",
    "operations",
    "admin",
    "forms",
    "workflow automation",
    "api",
    "apis",
    "data exchange",
    "interoperability",
]

REPO_HEALTHCARE_THEME_KEYS = {
    "healthcare_ai_pm",
    "healthcare_admin_automation",
    "low_reg_friction_wedges",
}

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
    "codebase intelligence",
    "code intelligence",
    "codebase",
    "connector",
    "connectors",
    "cli",
    "command line",
    "dead code",
    "developer workflow",
    "developer workflows",
    "git analytics",
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


def repo_has_strong_healthcare_anchor(text: str) -> bool:
    return bool(matched_keywords(REPO_STRONG_HEALTHCARE_ANCHOR_KEYWORDS, text))


def filter_theme_hits_for_item(
    item: DigestItem,
    theme_hits: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    if item.get("category") != "Repo":
        return theme_hits

    text = item_text_blob(item)
    if repo_has_strong_healthcare_anchor(text):
        return theme_hits

    return {
        theme_key: hits
        for theme_key, hits in theme_hits.items()
        if theme_key not in REPO_HEALTHCARE_THEME_KEYS
    }


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


def extract_workflow_wedge_hits(text: str, *, category: str = "") -> Dict[str, List[str]]:
    hits: Dict[str, List[str]] = {}
    for wedge_key, rule in WORKFLOW_WEDGE_RULES.items():
        wedge_hits = matched_keywords(rule.get("keywords", []), text)
        if wedge_hits:
            hits[wedge_key] = wedge_hits
    if category == "Repo" and not repo_has_strong_healthcare_anchor(text):
        context_required = {
            normalize_text(keyword)
            for keyword in REPO_CONTEXT_REQUIRED_WEDGE_KEYWORDS
        }
        hits = {
            wedge_key: [
                keyword
                for keyword in wedge_hits
                if normalize_text(keyword) not in context_required
            ]
            for wedge_key, wedge_hits in hits.items()
        }
        hits = {wedge_key: wedge_hits for wedge_key, wedge_hits in hits.items() if wedge_hits}
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
    materiality: Dict[str, Any],
) -> str:
    if item.get("category") == "Repo" and not wedge_hits and not repo_has_strong_healthcare_anchor(text):
        return "low"

    if materiality.get("low_signal_announcement"):
        return "low"

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
    materiality: Dict[str, Any],
) -> str:
    if materiality.get("low_signal_announcement"):
        return "low"

    action_hits = matched_keywords(ACTIONABILITY_KEYWORDS, text)
    if item.get("category") == "Regulatory":
        return "high"
    if wedge_hits and action_hits and materiality.get("material_operator_signal"):
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
        or repo_has_strong_healthcare_anchor(text)
        or ("healthcare_admin_automation" in theme_hits)
        or ("healthcare_ai_pm" in theme_hits and governance_hits)
        or (
            governance_hits
            and matched_keywords(INTEROPERABILITY_REIMBURSEMENT_KEYWORDS, text)
            and repo_has_strong_healthcare_anchor(text)
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
    wedge_hits = extract_workflow_wedge_hits(
        text,
        category=str(item.get("category", "") or ""),
    )
    workflow_wedges = workflow_wedge_labels(wedge_hits)
    if item.get("category") == "Repo":
        explicit_healthcare_context = repo_has_strong_healthcare_anchor(text)
    else:
        explicit_healthcare_context = has_explicit_healthcare_context(text)
    materiality = classify_operator_materiality(
        text,
        category=str(item.get("category", "") or ""),
    )
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
            materiality=materiality,
        ),
        "near_term_actionability": actionability_level(
            item,
            text=text,
            wedge_hits=wedge_hits,
            materiality=materiality,
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
        "signal_quality": materiality["signal_quality"],
        "low_signal_announcement": bool(materiality["low_signal_announcement"]),
        "soft_funding_or_challenge": bool(materiality["soft_funding_or_challenge"]),
        "material_operator_signal": bool(materiality["material_operator_signal"]),
        "materiality_signals": materiality["materiality_signals"],
        "materiality_reason": materiality["materiality_reason"],
    }


def selection_penalties_for_profile(item_profile: Dict[str, Any]) -> List[str]:
    penalties: List[str] = []
    if item_profile.get("low_signal_announcement"):
        if item_profile.get("soft_funding_or_challenge"):
            penalties.append("soft_funding_challenge_demoted")
        else:
            penalties.append("soft_announcement_demoted")
        penalties.append("weak_materiality_confidence_cap")
    if item_profile.get("is_generic_devtool") and not item_profile.get("generic_repo_cap_exempt"):
        penalties.append("generic_devtool_score_penalty")
    if item_profile.get("is_coding_agent_tool"):
        penalties.append("coding_agent_tooling_score_penalty")
    if item_profile.get("is_speculative_low_roi"):
        penalties.append("speculative_low_roi_score_penalty")
    return penalties


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

    if item_profile.get("low_signal_announcement"):
        penalty = 1.9 if item_profile.get("soft_funding_or_challenge") else 1.4
        scores["career_relevance"] -= penalty
        scores["build_relevance"] -= penalty
        scores["content_potential"] -= 0.9
        scores["regulatory_significance"] -= 0.9
        scores["side_hustle_relevance"] -= 0.8

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
    config: AppConfig | None = None,
) -> DigestItem:
    theme_hits = filter_theme_hits_for_item(item, extract_theme_hits(item))
    matched_themes = sorted(theme_hits.keys())
    item_profile = build_item_profile(item, theme_hits=theme_hits)
    entity_keys = extract_entity_keys(item)
    history_context = build_history_context(
        item,
        memory,
        themes=matched_themes,
        entities=entity_keys,
        now=now,
        config=config,
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
        "signal_quality": str(item_profile.get("signal_quality", "medium") or "medium"),
        "low_signal_announcement": bool(item_profile.get("low_signal_announcement")),
        "soft_funding_or_challenge": bool(item_profile.get("soft_funding_or_challenge")),
        "material_operator_signal": bool(item_profile.get("material_operator_signal")),
        "materiality_signals": item_profile.get("materiality_signals", []),
        "materiality_reason": str(item_profile.get("materiality_reason", "") or ""),
        "selection_penalties": selection_penalties_for_profile(item_profile),
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
    config: AppConfig | None = None,
    now: datetime | None = None,
    sort_items: bool = True,
) -> List[DigestItem]:
    now = now or datetime.now(timezone.utc)
    memory = memory or {"version": 1, "events": []}
    scored = [score_item(item, memory=memory, now=now, config=config) for item in items]
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


def objective_score_value(item: DigestItem, objective: str) -> float:
    return float((item.get("objective_scores", {}) or {}).get(objective, 0.0) or 0.0)


def dimension_score_value(
    item: DigestItem,
    dimension: str,
    *,
    fallback_objective: str | None = None,
) -> float:
    dimensions = item.get("score_dimensions", {}) or {}
    if dimension in dimensions:
        return float(dimensions.get(dimension, 0.0) or 0.0)
    if not fallback_objective:
        return 0.0
    return objective_score_value(item, fallback_objective)


def item_identifier(item: DigestItem) -> str:
    return str(
        item.get("item_key")
        or item.get("url")
        or item.get("id")
        or item.get("title")
        or ""
    )


def has_workflow_signal(item: DigestItem) -> bool:
    return bool(item.get("workflow_wedges")) or bool(
        item.get("explicit_interoperability_reimbursement")
    )


def is_generic_background_item(item: DigestItem) -> bool:
    return bool(item.get("is_generic_devtool")) and not bool(
        item.get("generic_repo_cap_exempt")
    )


def item_is_eligible_for_objective(item: DigestItem, objective: str) -> bool:
    objective_score = objective_score_value(item, objective)
    if objective_score < OBJECTIVE_MIN_SCORE[objective]:
        return False

    category = str(item.get("category", "") or "")
    operator_relevance = str(item.get("operator_relevance", "low") or "low")
    actionability = str(item.get("near_term_actionability", "low") or "low")
    workflow_signal = has_workflow_signal(item)
    build_score = dimension_score_value(item, "build_relevance", fallback_objective="build")
    career_score = dimension_score_value(item, "career_relevance", fallback_objective="career")
    content_score = dimension_score_value(item, "content_potential", fallback_objective="content")
    regulatory_score = dimension_score_value(
        item,
        "regulatory_significance",
        fallback_objective="regulatory",
    )
    generic_background = is_generic_background_item(item)
    explicit_healthcare_context = bool(item.get("explicit_healthcare_context"))

    if objective == "regulatory":
        return category == "Regulatory" and regulatory_score >= 3.0

    if objective == "career":
        if category == "Repo":
            return (
                explicit_healthcare_context
                and operator_relevance == "high"
                and (workflow_signal or actionability == "high")
                and objective_score >= OBJECTIVE_MIN_SCORE["career"] + 0.7
            )
        return (
            category in {"News", "Regulatory"}
            and (
                (
                    career_score >= 2.8
                    and (
                        operator_relevance in {"high", "medium"}
                        or actionability in {"high", "medium"}
                        or workflow_signal
                    )
                )
                or objective_score >= OBJECTIVE_MIN_SCORE["career"] + 1.2
            )
        )

    if objective == "build":
        if generic_background and build_score < 4.0:
            return False
        return build_score >= 3.0 and (
            category == "Repo"
            or operator_relevance in {"high", "medium"}
            or actionability in {"high", "medium"}
            or workflow_signal
            or objective_score >= OBJECTIVE_MIN_SCORE["build"] + 1.0
        )

    if objective == "content":
        if generic_background and content_score < 3.4:
            return False
        return content_score >= 2.3 and (
            category in {"News", "Regulatory"}
            or workflow_signal
            or operator_relevance in {"high", "medium"}
            or actionability in {"high", "medium"}
            or objective_score >= OBJECTIVE_MIN_SCORE["content"] + 1.0
        )

    return False


def objective_fit_bonus(item: DigestItem, objective: str) -> float:
    category = str(item.get("category", "") or "")
    operator_relevance = str(item.get("operator_relevance", "low") or "low")
    actionability = str(item.get("near_term_actionability", "low") or "low")
    workflow_signal = has_workflow_signal(item)
    generic_background = is_generic_background_item(item)

    bonus = 0.0
    if objective == "career":
        if category == "News":
            bonus += 0.7
        elif category == "Regulatory":
            bonus += 0.45
        elif category == "Repo":
            bonus -= 0.55
        if operator_relevance == "high":
            bonus += 0.25
        if actionability == "high":
            bonus += 0.15
    elif objective == "build":
        if category == "Repo":
            bonus += 0.8
        if operator_relevance == "high":
            bonus += 0.35
        if actionability == "high":
            bonus += 0.35
        if workflow_signal:
            bonus += 0.25
    elif objective == "content":
        if category == "News":
            bonus += 0.55
        elif category == "Regulatory":
            bonus += 0.25
        if workflow_signal:
            bonus += 0.25
        if actionability in {"high", "medium"}:
            bonus += 0.15
    elif objective == "regulatory":
        if bool(item.get("explicit_interoperability_reimbursement")):
            bonus += 0.5
        if actionability == "high":
            bonus += 0.3
        if operator_relevance in {"high", "medium"}:
            bonus += 0.2

    if generic_background:
        bonus -= 0.6

    return round(bonus, 2)


def objective_selection_score(item: DigestItem, objective: str) -> float:
    return round(
        objective_score_value(item, objective) + objective_fit_bonus(item, objective),
        2,
    )


def rank_objective_candidates(items: List[DigestItem], objective: str) -> List[DigestItem]:
    eligible = [item for item in items if item_is_eligible_for_objective(item, objective)]
    return sorted(
        eligible,
        key=lambda item: (
            objective_selection_score(item, objective),
            objective_score_value(item, objective),
            float(item.get("priority_score", 0.0) or 0.0),
            item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            item.get("title", ""),
        ),
        reverse=True,
    )


def objective_selection_order(
    candidates_by_objective: Dict[str, List[DigestItem]]
) -> List[str]:
    non_regulatory = sorted(
        [objective for objective in OBJECTIVE_DISPLAY_ORDER if objective != "regulatory"],
        key=lambda objective: (
            len(candidates_by_objective.get(objective, [])),
            OBJECTIVE_ORDER_RANK[objective],
        ),
    )
    return ["regulatory", *non_regulatory]


def choose_candidate_for_objective(
    candidates: List[DigestItem],
    objective: str,
    used_item_keys: set[str],
) -> DigestItem | None:
    if not candidates:
        return None

    best_candidate = candidates[0]
    best_unused = next(
        (
            item
            for item in candidates
            if item_identifier(item) not in used_item_keys
        ),
        None,
    )

    if not best_unused:
        return best_candidate

    if item_identifier(best_candidate) not in used_item_keys:
        return best_candidate

    best_score = objective_selection_score(best_candidate, objective)
    best_unused_score = objective_selection_score(best_unused, objective)
    if best_score - best_unused_score >= OBJECTIVE_REUSE_MARGIN[objective]:
        return best_candidate

    return best_unused


def empty_objective_pick(objective: str) -> Dict[str, Any]:
    return {
        "objective": objective,
        "label": OBJECTIVE_LABELS[objective],
        "item": None,
        "score": 0.0,
        "message": OBJECTIVE_EMPTY_MESSAGES[objective],
        "empty": True,
    }


def build_top_picks(items: List[DigestItem]) -> List[Dict[str, Any]]:
    candidates_by_objective = {
        objective: rank_objective_candidates(items, objective)
        for objective in OBJECTIVE_DISPLAY_ORDER
    }
    picks_by_objective: Dict[str, Dict[str, Any]] = {
        objective: empty_objective_pick(objective)
        for objective in OBJECTIVE_DISPLAY_ORDER
    }
    used_item_keys: set[str] = set()

    for objective in objective_selection_order(candidates_by_objective):
        choice = choose_candidate_for_objective(
            candidates_by_objective.get(objective, []),
            objective,
            used_item_keys,
        )
        if not choice:
            continue

        picks_by_objective[objective] = {
            "objective": objective,
            "label": OBJECTIVE_LABELS[objective],
            "item": choice,
            "score": objective_score_value(choice, objective),
            "message": "",
            "empty": False,
        }
        used_item_keys.add(item_identifier(choice))

    return [picks_by_objective[objective] for objective in OBJECTIVE_DISPLAY_ORDER]

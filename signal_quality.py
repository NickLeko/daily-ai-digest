from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


SOFT_FUNDING_CHALLENGE_KEYWORDS = [
    "challenge",
    "prize",
    "grant",
    "grants",
    "funding",
    "award",
    "awards",
    "competition",
    "request for applications",
    "call for applications",
    "call for proposals",
]

SOFT_PROGRAM_ANNOUNCEMENT_KEYWORDS = [
    "announces",
    "announced",
    "announcement",
    "launches",
    "launched",
    "launch",
    "unveils",
    "initiative",
    "program",
    "cohort",
]

REGULATORY_MATERIAL_KEYWORDS = [
    "final rule",
    "proposed rule",
    "interim final rule",
    "rulemaking",
    "guidance",
    "draft guidance",
    "deadline",
    "compliance date",
    "mandate",
    "required",
    "requirements",
    "enforcement",
    "information blocking",
    "health it certification",
    "hipaa",
    "reimbursement",
    "payment rule",
    "coverage determination",
    "electronic signatures",
    "standard",
    "standards",
]

HARD_REGULATORY_MATERIAL_KEYWORDS = [
    "final rule",
    "proposed rule",
    "interim final rule",
    "rulemaking",
    "guidance",
    "draft guidance",
    "deadline",
    "compliance date",
    "mandate",
    "required",
    "requirements",
    "enforcement",
    "information blocking",
    "health it certification",
    "hipaa",
    "payment rule",
]

DEPLOYMENT_MATERIAL_KEYWORDS = [
    "deployment",
    "deployed",
    "rollout",
    "rolled out",
    "go-live",
    "production",
    "implemented",
    "implementation",
    "partnership",
    "customer",
    "health system",
    "hospital",
    "payer",
    "provider group",
    "enterprise customer",
]

OPERATOR_IMPACT_KEYWORDS = [
    "turnaround",
    "throughput",
    "denial",
    "denials",
    "appeal",
    "appeals",
    "manual work",
    "status visibility",
    "audit trail",
    "compliance",
    "integration burden",
    "workflow automation",
    "roi",
    "reduction",
    "savings",
]

CAPABILITY_MATERIAL_KEYWORDS = [
    "benchmark",
    "evaluation",
    "eval",
    "model",
    "clearance",
    "authorized",
    "authorization",
    "approval",
    "clinical validation",
    "validated",
    "accuracy",
    "safety",
    "monitoring",
]

WORKFLOW_CONTEXT_KEYWORDS = [
    "prior authorization",
    "prior auth",
    "utilization management",
    "referral",
    "intake",
    "eligibility",
    "benefits verification",
    "documentation",
    "ambient",
    "scribe",
    "scheduling",
    "patient access",
    "revenue cycle",
    "rcm",
    "claims",
    "claims attachments",
    "denials",
    "appeals",
    "interoperability",
    "fhir",
    "hl7",
    "tefca",
    "uscdi",
    "api",
    "apis",
    "data exchange",
    "ehr",
    "integration",
    "workflow",
    "provider",
    "admin ops",
    "ops",
    "care coordination",
    "case management",
    "contact center",
    "back office",
    "forms",
    "fax",
]

GENERIC_RESEARCH_CONTEXT_KEYWORDS = [
    "research",
    "innovation",
    "innovations",
    "study",
    "studies",
    "academic",
    "kidney",
    "transplantation",
]

MATERIALITY_TEXT_FIELDS = [
    "cluster_title",
    "title",
    "raw_text",
    "summary",
    "evidence",
    "source",
    "source_name",
    "topic_key",
    "subcategory",
]


def normalize_text(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def keyword_matches_text(keyword: str, text: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    normalized_text = normalize_text(text)
    if not normalized_keyword or not normalized_text:
        return False
    if " " in normalized_keyword:
        return f" {normalized_keyword} " in f" {normalized_text} "
    return normalized_keyword in set(normalized_text.split())


def matched_keywords(keywords: Iterable[str], text: str) -> List[str]:
    return [keyword for keyword in keywords if keyword_matches_text(keyword, text)]


def mapping_materiality_text(value: Dict[str, Any]) -> str:
    parts: List[str] = []
    for field in MATERIALITY_TEXT_FIELDS:
        field_value = value.get(field)
        if str(field_value or "").strip():
            parts.append(str(field_value).strip())
    for field in ("workflow_wedges", "matched_themes", "market_buckets", "tags"):
        raw_values = value.get(field) or []
        if not isinstance(raw_values, list):
            raw_values = [raw_values]
        parts.extend(str(item).strip() for item in raw_values if str(item).strip())
    return " ".join(parts)


def classify_operator_materiality(text: str, *, category: str = "") -> Dict[str, Any]:
    category = str(category or "")
    soft_funding_hits = matched_keywords(SOFT_FUNDING_CHALLENGE_KEYWORDS, text)
    soft_announcement_hits = matched_keywords(
        [*SOFT_FUNDING_CHALLENGE_KEYWORDS, *SOFT_PROGRAM_ANNOUNCEMENT_KEYWORDS],
        text,
    )
    regulatory_hits = matched_keywords(REGULATORY_MATERIAL_KEYWORDS, text)
    hard_regulatory_hits = matched_keywords(HARD_REGULATORY_MATERIAL_KEYWORDS, text)
    deployment_hits = matched_keywords(DEPLOYMENT_MATERIAL_KEYWORDS, text)
    operator_impact_hits = matched_keywords(OPERATOR_IMPACT_KEYWORDS, text)
    capability_hits = matched_keywords(CAPABILITY_MATERIAL_KEYWORDS, text)
    workflow_hits = matched_keywords(WORKFLOW_CONTEXT_KEYWORDS, text)
    generic_research_hits = matched_keywords(GENERIC_RESEARCH_CONTEXT_KEYWORDS, text)

    has_workflow_context = bool(workflow_hits)
    has_regulatory_materiality = bool(regulatory_hits)
    has_deployment_materiality = bool(deployment_hits) and has_workflow_context
    has_operator_impact = bool(operator_impact_hits) and has_workflow_context
    has_capability_materiality = bool(capability_hits) and (
        has_workflow_context or has_regulatory_materiality
    )
    has_material_operator_signal = (
        has_regulatory_materiality
        or has_deployment_materiality
        or has_operator_impact
        or has_capability_materiality
    )

    is_soft_funding_or_challenge = bool(soft_funding_hits)
    if is_soft_funding_or_challenge and not (
        hard_regulatory_hits
        or has_deployment_materiality
        or has_operator_impact
        or has_capability_materiality
    ):
        has_material_operator_signal = False

    is_soft_announcement = bool(soft_announcement_hits)
    low_signal_announcement = is_soft_announcement and not has_material_operator_signal

    if category == "Regulatory" and has_material_operator_signal and has_regulatory_materiality:
        signal_quality = "strong"
    elif has_material_operator_signal:
        signal_quality = "strong"
    elif low_signal_announcement:
        signal_quality = "weak"
    elif has_workflow_context:
        signal_quality = "medium"
    else:
        signal_quality = "weak"

    materiality_signals = [
        *regulatory_hits,
        *deployment_hits,
        *operator_impact_hits,
        *capability_hits,
    ]

    if low_signal_announcement:
        reason = "soft announcement without concrete operator materiality"
    elif has_material_operator_signal:
        reason = "concrete policy, deployment, capability, or workflow consequence"
    elif has_workflow_context:
        reason = "workflow-adjacent but without concrete consequence"
    else:
        reason = "no operator materiality detected"

    return {
        "signal_quality": signal_quality,
        "low_signal_announcement": low_signal_announcement,
        "soft_funding_or_challenge": is_soft_funding_or_challenge,
        "soft_announcement_hits": soft_announcement_hits,
        "material_operator_signal": has_material_operator_signal,
        "materiality_signals": sorted(set(materiality_signals)),
        "workflow_context_hits": workflow_hits,
        "generic_research_hits": generic_research_hits,
        "materiality_reason": reason,
    }


def classify_mapping_materiality(value: Dict[str, Any]) -> Dict[str, Any]:
    return classify_operator_materiality(
        mapping_materiality_text(value),
        category=str(value.get("category", "") or ""),
    )

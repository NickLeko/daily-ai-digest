import json
import re
import sys
from typing import Any, Dict, List

from config import AppConfig, OPENAI_MODEL
from services import get_openai_client
from signal_quality import classify_mapping_materiality
from taxonomy import (
    DEFAULT_WORKFLOW_LABEL,
    WORKFLOW_LABEL_KEYWORDS,
    theme_labels as taxonomy_theme_labels,
    workflow_actions_for_label,
    workflow_guidance_for_label,
)

GENERIC_TOP_INSIGHT_PHRASES = [
    "accelerate automation",
    "ai is converging",
    "are converging",
    "generic ai hype",
    "workflow roi and governance",
    "operational proof",
    "future of ai",
]

GENERIC_WHY_IT_MATTERS_PHRASES = [
    "useful signal",
    "helps teams",
    "enables teams",
    "allows teams",
    "healthcare ai pms should consider",
    "compress manual work and handoff delay",
    "next planning cycle",
    "near-term roadmap impact",
]

ACTION_WORDS = [
    "prioritize",
    "rank",
    "track",
    "test",
    "map",
    "build",
    "deprioritize",
    "tie",
    "plan",
    "audit",
    "review",
    "validate",
    "inventory",
    "decide",
    "check",
]

ACTOR_KEYWORDS = [
    "manager",
    "managers",
    "lead",
    "leads",
    "leader",
    "leaders",
    "owner",
    "owners",
    "director",
    "directors",
    "supervisor",
    "supervisors",
    "builder",
    "builders",
    "integration",
    "integrations",
    "compliance",
    "ops",
    "rcm",
    "denials",
    "payer",
    "provider",
    "access",
    "informatics",
]

TIMEFRAME_KEYWORDS = [
    "next 7",
    "next 30",
    "next month",
    "this month",
    "next sprint",
    "over the next",
    "in the next",
    "before the next",
    "coming weeks",
    "current implementation",
    "billing cycle",
    "roadmap check-in",
]

OPERATING_DETAIL_RULES = [
    ("claims attachment exchange", ["claims attachments", "attachment exchange"]),
    ("electronic signatures", ["electronic signatures", "e-signature", "esignature"]),
    ("payer status checks", ["status visibility", "status checks", "payer status"]),
    ("referral routing", ["referral routing", "referral management", "referral"]),
    ("intake completeness", ["intake", "eligibility", "benefits verification"]),
    ("visit documentation handoffs", ["documentation", "ambient", "scribe", "charting", "clinical note"]),
    ("open-slot recovery", ["scheduling", "appointment", "reschedule", "capacity"]),
    ("denial and appeal prep", ["denials", "denial", "appeals", "appeal"]),
    ("FHIR and API handoffs", ["fhir", "api", "apis", "interoperability", "tefca", "uscdi"]),
    ("fax and forms queues", ["fax", "forms", "snail mail"]),
    ("back-office inbox work", ["inbox", "back office", "contact center", "call center"]),
    ("follow-up closure", ["care coordination", "follow-up", "discharge", "transition of care"]),
]

DETAIL_TOKEN_STOPWORDS = {
    "and",
    "around",
    "for",
    "from",
    "into",
    "the",
    "with",
    "work",
}


class _LegacyResponsesProxy:
    def create(self, *args: Any, **kwargs: Any) -> Any:
        if _running_under_unittest_runner():
            raise RuntimeError("Live OpenAI calls are disabled during unit tests.")
        return get_openai_client().responses.create(*args, **kwargs)


class _LegacyClientProxy:
    def __init__(self) -> None:
        self.responses = _LegacyResponsesProxy()


# Compatibility shim for existing tests and patch targets. This remains lazy:
# the real OpenAI client is only created if the proxy method is actually called.
client = _LegacyClientProxy()


def _running_under_unittest_runner() -> bool:
    main_module = sys.modules.get("__main__")
    main_package = str(getattr(main_module, "__package__", "") or "")
    main_file = str(getattr(main_module, "__file__", "") or "").replace("\\", "/")
    argv0 = str(sys.argv[0] if sys.argv else "").replace("\\", "/")
    return (
        main_package == "unittest"
        or "/unittest/" in main_file
        or "/unittest/" in argv0
    )


def parse_json_payload(text: str) -> Dict[str, str] | None:
    candidate = (text or "").strip()
    if not candidate:
        return None

    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(candidate[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def theme_labels(theme_keys: List[str]) -> List[str]:
    return taxonomy_theme_labels(theme_keys)


def item_text_blob(item: Dict[str, object]) -> str:
    return " ".join(
        str(part).strip()
        for part in [
            item.get("title", ""),
            item.get("raw_text", ""),
            item.get("summary", ""),
            item.get("why_it_matters", ""),
            item.get("source", ""),
            item.get("topic_key", ""),
            " ".join(str(label) for label in item.get("workflow_wedges", []) or []),
        ]
        if str(part).strip()
    )


def infer_workflow_wedges(item: Dict[str, object]) -> List[str]:
    explicit = [
        str(label).strip()
        for label in item.get("workflow_wedges", []) or []
        if str(label).strip()
    ]
    if explicit:
        return explicit

    text = item_text_blob(item).lower()
    matched = []
    for label, keywords in WORKFLOW_LABEL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            matched.append(label)
    return matched


def workflow_guidance_for_item(item: Dict[str, object]) -> Dict[str, str]:
    wedges = infer_workflow_wedges(item)
    return workflow_guidance_for_label(wedges[0] if wedges else DEFAULT_WORKFLOW_LABEL)


def workflow_actions_for_item(item: Dict[str, object]) -> Dict[str, str]:
    wedges = infer_workflow_wedges(item)
    return workflow_actions_for_label(wedges[0] if wedges else DEFAULT_WORKFLOW_LABEL)


def sentence_start(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    return value[0].upper() + value[1:]


def summary_is_usable(text: str) -> bool:
    value = " ".join(str(text or "").split()).strip()
    if not value:
        return False
    if value[-1] in ",;:":
        return False
    if re.search(r"(?<![A-Z]\.)\b[A-Z]\.$", value):
        return False
    if value.count("(") > value.count(")"):
        return False
    if value.count("[") > value.count("]"):
        return False
    return True


def item_detail_phrase(item: Dict[str, object]) -> str:
    text = item_text_blob(item).lower()
    details: List[str] = []
    for label, keywords in OPERATING_DETAIL_RULES:
        if any(keyword in text for keyword in keywords):
            details.append(label)
        if len(details) == 2:
            break

    if not details:
        return ""
    if len(details) == 1:
        return details[0]
    return f"{details[0]} and {details[1]}"


def item_has_policy_signal(item: Dict[str, object]) -> bool:
    text = item_text_blob(item).lower()
    return any(
        keyword in text
        for keyword in [
            "policy",
            "rule",
            "guidance",
            "cms",
            "fda",
            "onc",
            "compliance",
            "reimbursement",
        ]
    )


def item_has_market_signal(item: Dict[str, object]) -> bool:
    text = item_text_blob(item).lower()
    return any(
        keyword in text
        for keyword in [
            "launch",
            "launched",
            "pilot",
            "deployment",
            "deployed",
            "partnership",
            "customer",
            "health system",
            "rollout",
        ]
    )


def quality_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if token not in DETAIL_TOKEN_STOPWORDS
    }


def has_redundant_detail_suffix(text: str) -> bool:
    lowered = str(text or "").lower()
    for detail, _keywords in OPERATING_DETAIL_RULES:
        marker = f" around {detail.lower()}"
        if marker not in lowered:
            continue
        before_marker = lowered.split(marker, 1)[0]
        detail_tokens = quality_tokens(detail)
        if detail_is_already_covered(quality_tokens(before_marker), detail_tokens):
            return True
    return False


def detail_is_already_covered(base_tokens: set[str], detail_tokens: set[str]) -> bool:
    if not detail_tokens:
        return False
    overlap = base_tokens & detail_tokens
    return detail_tokens <= base_tokens or (
        len(overlap) >= 2 and len(overlap) / len(detail_tokens) >= 0.6
    )


def detail_suffix(base_action: str, detail: str) -> str:
    if not detail:
        return ""
    if detail.lower() in base_action.lower():
        return ""
    base_tokens = quality_tokens(base_action)
    detail_tokens = quality_tokens(detail)
    if detail_is_already_covered(base_tokens, detail_tokens):
        return ""
    return f" around {detail}"


def why_it_matters_is_specific(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in GENERIC_WHY_IT_MATTERS_PHRASES):
        return False
    if has_redundant_detail_suffix(lowered):
        return False
    mentions_workflow = any(
        keyword in lowered
        for keyword in [
            "prior auth",
            "prior authorization",
            "referral",
            "intake",
            "documentation",
            "ambient",
            "scheduling",
            "denial",
            "revenue cycle",
            "interoperability",
            "ops",
            "care coordination",
        ]
    )
    mentions_action = any(word in lowered for word in ACTION_WORDS)
    mentions_actor = any(keyword in lowered for keyword in ACTOR_KEYWORDS)
    mentions_timeframe = any(keyword in lowered for keyword in TIMEFRAME_KEYWORDS)
    return mentions_workflow and mentions_action and mentions_actor and mentions_timeframe


def top_insight_is_specific(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in GENERIC_TOP_INSIGHT_PHRASES):
        return False
    mentions_workflow = any(
        keyword in lowered
        for keyword in [
            "prior auth",
            "prior authorization",
            "referral",
            "documentation",
            "ambient",
            "intake",
            "scheduling",
            "denial",
            "denials",
            "rcm",
            "revenue cycle",
            "interoperability",
            "provider",
            "admin ops",
            "admin operations",
            "care coordination",
        ]
    )
    mentions_action = any(word in lowered for word in ACTION_WORDS) or "matters because" in lowered
    return mentions_workflow and mentions_action


def fallback_summary(item: Dict[str, object]) -> str:
    guidance = workflow_guidance_for_item(item)
    title = str(item.get("title", "This item") or "This item")
    materiality = classify_mapping_materiality(item)
    if item.get("low_signal_announcement") or materiality["low_signal_announcement"]:
        return (
            f"{title} is a soft announcement, not an operator-grade workflow signal. "
            f"Treat it as watchlist context until it produces concrete deployment, policy, reimbursement, or measurable workflow evidence."
        )
    if item.get("category") == "Regulatory":
        return (
            f"{title} is a regulatory signal touching {guidance['workflow']}. "
            f"It matters if it changes roadmap, interoperability, reimbursement, or compliance work in the near term."
        )
    if item.get("category") == "Repo":
        return (
            f"{title} is a repo closest to {guidance['workflow']}. "
            f"The useful question is whether it shortens operator work and survives governance review, not whether it is another generic AI stack."
        )
    return (
        f"{title} is a workflow-relevant market signal for {guidance['workflow']}. "
        f"Read it for the operator implication and near-term roadmap impact, not the headline."
    )


def fallback_why_it_matters(item: Dict[str, object]) -> str:
    materiality = classify_mapping_materiality(item)
    if item.get("low_signal_announcement") or materiality["low_signal_announcement"]:
        return (
            "Do not assign roadmap or backlog time from this item alone; revisit only if follow-on evidence shows "
            "a real deployment, policy requirement, reimbursement change, or measurable workflow impact in the next 30 days."
        )

    guidance = workflow_guidance_for_item(item)
    workflow_actions = workflow_actions_for_item(item)
    detail = item_detail_phrase(item)
    detail_tail = detail_suffix(workflow_actions["news_action"], detail)
    if item.get("category") == "Regulatory":
        regulatory_tail = detail_suffix(workflow_actions["regulatory_action"], detail)
        return (
            f"{sentence_start(workflow_actions['actors'])} should use this update to "
            f"{workflow_actions['regulatory_action']}{regulatory_tail} over the next 30 days."
        )
    if item.get("is_generic_devtool") and not item.get("generic_repo_cap_exempt"):
        return (
            f"Only relevant if you can attach it to a live {guidance['workflow']} workflow; "
            f"builders should pressure-test integration burden and governance fit in the next sprint."
        )
    if item.get("category") == "Repo":
        repo_tail = detail_suffix(workflow_actions["repo_action"], detail)
        return (
            f"For builders targeting {guidance['workflow']}, the question is whether this can "
            f"{workflow_actions['repo_action']}{repo_tail} during a real pilot in the next 30 days."
        )
    if item_has_policy_signal(item):
        return (
            f"This changes the operating checklist for {guidance['workflow']}: "
            f"{workflow_actions['actors']} should {workflow_actions['news_action']}{detail_tail} before the next roadmap check-in."
        )
    if item_has_market_signal(item):
        return (
            f"If you own {guidance['workflow']}, treat this as a live market signal and use the next 30 days to "
            f"{workflow_actions['news_action']}{detail_tail}; {workflow_actions['actors']} will feel it first."
        )
    return (
        f"{sentence_start(workflow_actions['actors'])} should treat this as a live signal in {guidance['workflow']} "
        f"and {workflow_actions['news_action']}{detail_tail} over the next month."
    )


def normalize_signal(item: Dict[str, object], signal: str) -> str:
    normalized = (signal or "medium").strip().lower()
    if normalized not in {"high", "medium", "low"}:
        normalized = "medium"
    materiality = classify_mapping_materiality(item)
    if item.get("low_signal_announcement") or materiality["low_signal_announcement"]:
        return "low"
    if item.get("is_speculative_low_roi") and normalized == "high":
        return "medium"
    if item.get("is_generic_devtool") and not item.get("generic_repo_cap_exempt") and normalized == "high":
        return "medium"
    return normalized


def item_prompt_context(item: Dict[str, object]) -> str:
    dimensions = item.get("score_dimensions", {}) or {}
    strongest_dimensions = item.get("score_focus", []) or []
    objective_scores = item.get("objective_scores", {}) or {}
    top_objective = max(
        objective_scores.items(),
        key=lambda entry: entry[1],
        default=("career", 0.0),
    )[0]
    dimension_summary = ", ".join(
        f"{key}={value}"
        for key, value in dimensions.items()
        if key in strongest_dimensions
    ) or "none"
    theme_summary = ", ".join(theme_labels(item.get("matched_themes", []) or [])) or "none"
    workflow_summary = ", ".join(infer_workflow_wedges(item)) or "none"
    operator_relevance = str(item.get("operator_relevance", "low") or "low")
    actionability = str(item.get("near_term_actionability", "low") or "low")
    return (
        f"Matched themes: {theme_summary}. "
        f"Workflow wedges: {workflow_summary}. "
        f"Operator relevance: {operator_relevance}. "
        f"Near-term actionability: {actionability}. "
        f"Strongest scoring dimensions: {dimension_summary}. "
        f"Top objective: {top_objective}."
    )


def model_response_text(
    prompt: str,
    *,
    config: AppConfig | None = None,
    openai_client: Any | None = None,
) -> str:
    model_name = config.openai_model if config is not None else OPENAI_MODEL
    try:
        if openai_client is not None:
            response_client = openai_client
        elif config is not None:
            response_client = get_openai_client(config)
        else:
            response_client = client
        response = response_client.responses.create(
            model=model_name,
            input=prompt,
        )
    except Exception:
        return ""
    return str(getattr(response, "output_text", "") or "").strip()


def summarize_item(
    item: Dict[str, object],
    *,
    config: AppConfig | None = None,
    openai_client: Any | None = None,
) -> Dict[str, str]:
    category_specific_rule = ""
    if item["category"] == "Regulatory":
        category_specific_rule = (
            "For regulatory items, limit the summary to the most decision-relevant information only. "
            "Ignore procedural or clinical detail unless it changes product, compliance, reimbursement, or workflow decisions. "
            "Keep it compact."
        )
    elif item["category"] == "Repo":
        category_specific_rule = (
            "For repo items, focus on the concrete workflow or governance use case. "
            "If healthcare applicability is weak, make that obvious and avoid treating it like a major operator signal."
        )

    prompt = f"""
You are writing a daily digest for a healthcare AI product manager.

Category: {item["category"]}
Title: {item["title"]}
URL: {item["url"]}
Priority context: {item_prompt_context(item)}

Raw text:
{item["raw_text"]}

Return valid JSON only with this exact schema:
{{
  "summary": "Exactly 2 sentences. No numbering. No bullets.",
  "why_it_matters": "Exactly 1 sentence. Specific, practical, and action-oriented.",
  "signal": "high"
}}

Rules:
- No markdown
- No numbering like 1. or 2.
- No bullet points
- No hype
- Be concrete, concise, and practical
- Write for a healthcare AI PM audience
- Avoid generic phrases like "this enables", "this helps", "this allows"
- Write like an operator summarizing for speed and decision-making
- "why_it_matters" must name the workflow affected, who cares, and the action or implication in the next 7 to 30 days
- Name a concrete operator group such as prior-auth managers, integration leads, access-center owners, denials leads, or clinical informatics
- Mention a practical next step such as an audit, pilot decision, backlog review, integration check, or compliance task
- Make repo, news, and regulatory items sound different when the evidence differs
- Do not reuse the same sentence shell across items
- Avoid empty abstractions like "accelerate automation", "unlock value", or "future of AI"
- "signal" must be one of: high, medium, low
- Use "high" only for items with strong practical importance right now
- Use "medium" for useful but not urgent items
- Use "low" for background signal
- EXCLUDE_KEYWORDS = ["game", "education", "chatbot ui"]

Additional category rule:
{category_specific_rule}
""".strip()

    text = model_response_text(prompt, config=config, openai_client=openai_client)

    try:
        parsed = parse_json_payload(text)
        if not parsed:
            raise ValueError("No JSON payload found.")
        summary = str(parsed.get("summary", "") or "").strip()
        why_it_matters = str(parsed.get("why_it_matters", "") or "").strip()
        signal = normalize_signal(item, str(parsed.get("signal", "") or "medium"))
    except Exception:
        summary = fallback_summary(item)
        why_it_matters = fallback_why_it_matters(item)
        signal = normalize_signal(item, "medium")

    materiality_item = {
        **item,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "signal": signal,
    }
    materiality = classify_mapping_materiality(materiality_item)
    if item.get("low_signal_announcement") or materiality["low_signal_announcement"]:
        summary = fallback_summary(materiality_item)
        why_it_matters = fallback_why_it_matters(materiality_item)
        signal = "low"

    if not summary_is_usable(summary):
        summary = fallback_summary(item)
    if not why_it_matters_is_specific(why_it_matters):
        why_it_matters = fallback_why_it_matters(item)

    return {
        **item,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "signal": signal,
    }


def summarize_items(
    items: List[Dict[str, object]],
    *,
    config: AppConfig | None = None,
    openai_client: Any | None = None,
) -> List[Dict[str, str]]:
    return [
        summarize_item(item, config=config, openai_client=openai_client)
        for item in items
    ]


def fallback_digest_strategy(items: List[Dict[str, object]]) -> Dict[str, str]:
    ranked_items = sorted(
        items,
        key=lambda item: float(item.get("priority_score", 0.0) or 0.0),
        reverse=True,
    )
    top_item = ranked_items[0] if ranked_items else {}
    guidance = workflow_guidance_for_item(top_item)
    watch_reference = top_item.get("source") or top_item.get("title") or guidance["workflow"]
    generic_tool_pressure = any(
        bool(item.get("is_generic_devtool")) and not bool(item.get("generic_repo_cap_exempt"))
        for item in ranked_items[:3]
    )

    top_insight = (
        f"For {guidance['workflow']}, the near-term edge is {guidance['focus']}, "
        f"so healthcare AI PMs should {guidance['action']}"
    )
    if generic_tool_pressure:
        top_insight += " instead of generic agent tooling."
    else:
        top_insight += "."

    return {
        "top_insight": top_insight,
        "content_angle": guidance["content_angle"],
        "build_idea": guidance["build_idea"],
        "interview_talking_point": guidance["interview_talking_point"],
        "watch_item": f"Watch {watch_reference} for repeat deployment signal in {guidance['workflow']}.",
    }


def summarize_digest_strategy(
    items: List[Dict[str, object]],
    memory_snapshot: Dict[str, object] | None = None,
    *,
    config: AppConfig | None = None,
    openai_client: Any | None = None,
) -> Dict[str, str]:
    compact_items = []
    for item in items:
        compact_items.append(
            {
                "category": item["category"],
                "title": item["title"],
                "summary": item["summary"],
                "why_it_matters": item["why_it_matters"],
                "signal": item["signal"],
                "priority_score": item.get("priority_score", 0.0),
                "matched_themes": theme_labels(item.get("matched_themes", []) or []),
                "workflow_wedges": infer_workflow_wedges(item),
                "operator_relevance": item.get("operator_relevance", "low"),
                "near_term_actionability": item.get("near_term_actionability", "low"),
                "is_generic_devtool": bool(item.get("is_generic_devtool")),
                "generic_repo_cap_exempt": bool(item.get("generic_repo_cap_exempt")),
                "objective_scores": item.get("objective_scores", {}),
            }
        )

    prompt = f"""
You are writing a daily operator brief for a healthcare AI product manager.

Below is today's digest content:
{json.dumps(compact_items, indent=2)}

Recent memory snapshot:
{json.dumps(memory_snapshot or {}, indent=2)}

Return valid JSON only:
{{
  "top_insight": "One sentence, direct and action-oriented.",
  "content_angle": "One short sentence or phrase.",
  "build_idea": "One short sentence or phrase.",
  "interview_talking_point": "One short sentence or phrase.",
  "watch_item": "One short sentence or phrase."
}}

Rules:
- Top insight must be one sentence only
- Top insight must name one specific workflow wedge from the shortlist
- Top insight must state the concrete operator implication in the next 7 to 30 days
- Prefer forms like "For prior auth, X matters because Y" or "This suggests healthcare AI PMs should prioritize Z over generic agent experimentation"
- No hype
- No generic language
- Ban empty abstractions like "accelerate automation" or "AI is converging"
- Focus on what deserves attention or action next
- Write like an operator, not a newsletter writer
- Keep every field concise and practical
- Empty strings are allowed if evidence is weak, but prefer useful specificity
""".strip()

    text = model_response_text(prompt, config=config, openai_client=openai_client)

    fallback = fallback_digest_strategy(items)

    try:
        parsed = parse_json_payload(text)
        if parsed:
            result = {
                "top_insight": str(parsed.get("top_insight", "") or "").strip(),
                "content_angle": str(parsed.get("content_angle", "") or "").strip(),
                "build_idea": str(parsed.get("build_idea", "") or "").strip(),
                "interview_talking_point": str(
                    parsed.get("interview_talking_point", "") or ""
                ).strip(),
                "watch_item": str(parsed.get("watch_item", "") or "").strip(),
            }
            if not top_insight_is_specific(result["top_insight"]):
                result["top_insight"] = fallback["top_insight"]
            for key in ("content_angle", "build_idea", "interview_talking_point", "watch_item"):
                if not result[key]:
                    result[key] = fallback[key]
            return result
    except Exception:
        pass

    cleaned_text = text.strip().strip("`").strip()
    if cleaned_text and "top_insight" not in cleaned_text.lower() and top_insight_is_specific(cleaned_text):
        fallback["top_insight"] = cleaned_text

    return fallback

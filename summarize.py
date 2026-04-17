import json
import re
from typing import Dict, List

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, PRIORITY_THEME_RULES


client = OpenAI(api_key=OPENAI_API_KEY)

WORKFLOW_KEYWORD_RULES = {
    "prior auth": [
        "prior authorization",
        "prior auth",
        "utilization management",
        "utilization review",
    ],
    "referral/intake": [
        "referral",
        "referrals",
        "intake",
        "eligibility",
        "benefits verification",
    ],
    "documentation/ambient": [
        "documentation",
        "ambient",
        "scribe",
        "charting",
        "clinical note",
    ],
    "scheduling": [
        "scheduling",
        "appointment",
        "patient access",
        "reschedule",
    ],
    "RCM/denials": [
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
    "interoperability": [
        "interoperability",
        "fhir",
        "hl7",
        "tefca",
        "uscdi",
        "api",
        "ehr",
        "epic",
        "cerner",
    ],
    "provider/admin ops": [
        "contact center",
        "call center",
        "operations",
        "back office",
        "forms",
        "fax",
        "workflow automation",
    ],
    "care coordination": [
        "care coordination",
        "case management",
        "transition of care",
        "discharge",
        "follow-up",
    ],
}

WORKFLOW_OPERATOR_GUIDANCE = {
    "prior auth": {
        "workflow": "prior auth and utilization management",
        "audience": "payer and provider ops leaders",
        "focus": "interoperable attachment exchange and audit-ready automation",
        "action": "rank bets by denial reduction, status visibility, and payer handoff quality",
        "build_idea": "Prototype a prior-auth assistant that packages documentation, attachments, and denial-prep into one handoff.",
        "content_angle": "Why prior-auth workflow ROI beats generic agent demos.",
        "interview_talking_point": "Explain how you would prioritize prior-auth automation by denial lift, turnaround time, and auditability.",
    },
    "referral/intake": {
        "workflow": "referral and intake",
        "audience": "access and care-coordination teams",
        "focus": "intake completeness and referral routing",
        "action": "prioritize products that cut manual intake, missing documentation, and referral leakage",
        "build_idea": "Prototype an intake copilot that flags missing documents and routes referrals before staff touch them.",
        "content_angle": "Referral leakage is a better automation wedge than another generic copilot.",
        "interview_talking_point": "Describe how you would measure automation value in intake completeness and referral conversion.",
    },
    "documentation/ambient": {
        "workflow": "documentation and ambient capture",
        "audience": "provider ops leaders",
        "focus": "note capture that survives compliance review",
        "action": "prioritize tools tied to note throughput, auditability, and cleaner downstream handoffs",
        "build_idea": "Prototype an ambient handoff assistant that turns visit context into structured follow-up work.",
        "content_angle": "Ambient AI wins when it improves downstream ops, not just note drafting.",
        "interview_talking_point": "Talk about documentation tools in terms of throughput, compliance risk, and handoff quality.",
    },
    "scheduling": {
        "workflow": "scheduling and patient access",
        "audience": "access-center leaders",
        "focus": "capacity management and fewer reschedules",
        "action": "prioritize tools that improve fill rate, template utilization, and manual reschedule load",
        "build_idea": "Prototype a scheduling copilot that surfaces open capacity and prevents avoidable reschedules.",
        "content_angle": "Scheduling automation is a real buyer wedge because the metrics are immediate.",
        "interview_talking_point": "Frame scheduling AI around fill rate, template utilization, and manual touch reduction.",
    },
    "RCM/denials": {
        "workflow": "revenue cycle and denials",
        "audience": "RCM and denials teams",
        "focus": "denial prevention and appeal prep",
        "action": "prioritize products tied to recoveries, write-offs, and turnaround time instead of abstract autonomy",
        "build_idea": "Prototype a denial-worklist assistant that summarizes evidence, appeal steps, and next actions.",
        "content_angle": "RCM buyers care about recoveries and turnaround, not generic AI orchestration.",
        "interview_talking_point": "Explain how you would rank denials automation by recovery rate, cycle time, and auditability.",
    },
    "interoperability": {
        "workflow": "interoperability and data exchange",
        "audience": "health IT and integration owners",
        "focus": "standards-based exchange instead of custom point integrations",
        "action": "prioritize roadmap work around FHIR, APIs, and auditability before another generic agent experiment",
        "build_idea": "Prototype an interoperability layer that packages the minimum payload and audit trail for a high-friction workflow.",
        "content_angle": "The next wedge is boring on purpose: standards, payload quality, and audit trails.",
        "interview_talking_point": "Discuss interoperability bets in terms of integration burden, auditability, and time-to-deployment.",
    },
    "provider/admin ops": {
        "workflow": "provider and admin operations",
        "audience": "ops leaders",
        "focus": "manual inbox, forms, and contact-center handoffs",
        "action": "prioritize tools that compress manual work and handoff delay in the next planning cycle",
        "build_idea": "Prototype a back-office assistant that triages forms, inbox items, and the next required handoff.",
        "content_angle": "Admin ops is where AI can prove value without pretending to replace whole teams.",
        "interview_talking_point": "Talk about provider-ops AI in terms of touch reduction, handoff quality, and operational lift.",
    },
    "care coordination": {
        "workflow": "care coordination",
        "audience": "care management and referral teams",
        "focus": "referral closure and transition tracking",
        "action": "prioritize systems that reduce leakage, missed follow-ups, and manual outreach gaps",
        "build_idea": "Prototype a care-coordination assistant that tracks missing follow-ups and closes referral loops.",
        "content_angle": "Care coordination automation is valuable when it closes loops, not when it adds another inbox.",
        "interview_talking_point": "Frame care-coordination AI around referral closure, follow-up completion, and fewer dropped transitions.",
    },
}

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

WORKFLOW_SPECIFIC_ACTIONS = {
    "prior auth": {
        "actors": "prior-auth managers, denials leads, and integration owners",
        "repo_action": "reduce documentation assembly, payer rules lookup, and status chasing",
        "news_action": "audit where evidence packets, payer rules, or status updates still break the workflow",
        "regulatory_action": "map attachment, signature, and audit-trail gaps",
    },
    "referral/intake": {
        "actors": "access directors, intake supervisors, and referral owners",
        "repo_action": "cut missing-document rework, manual routing, and referral leakage",
        "news_action": "review intake completeness, routing errors, and time-to-scheduled-visit",
        "regulatory_action": "check intake data capture and referral-routing controls",
    },
    "documentation/ambient": {
        "actors": "clinical informatics leads and provider-ops owners",
        "repo_action": "turn visit context into usable downstream tasks instead of another note layer",
        "news_action": "check whether note capture improves coding, follow-up, or inbox handoffs",
        "regulatory_action": "review clinician review, retention, and downstream audit controls",
    },
    "scheduling": {
        "actors": "access-center managers and patient-access owners",
        "repo_action": "improve fill rate, template utilization, and reschedule recovery",
        "news_action": "review hold times, open capacity, and preventable reschedules",
        "regulatory_action": "check whether scheduling data capture or reporting obligations changed",
    },
    "RCM/denials": {
        "actors": "RCM directors, denials leads, and appeals managers",
        "repo_action": "speed evidence retrieval, denial triage, and appeal prep",
        "news_action": "review avoidable denials, write-offs, and queue turnaround",
        "regulatory_action": "map policy changes to claims, attachments, and appeal workflows",
    },
    "interoperability": {
        "actors": "integration leads and health IT owners",
        "repo_action": "reduce custom interface work while preserving an audit trail",
        "news_action": "inventory FHIR/API dependencies and brittle handoffs on active roadmap work",
        "regulatory_action": "map API, payload, and audit-trail gaps before trading-partner work starts",
    },
    "provider/admin ops": {
        "actors": "ops managers and back-office leads",
        "repo_action": "shrink inbox, forms, or contact-center handoffs on a live queue",
        "news_action": "review which back-office queues still depend on manual triage and status chasing",
        "regulatory_action": "check whether reporting, forms handling, or audit obligations changed",
    },
    "care coordination": {
        "actors": "care-management leads and referral owners",
        "repo_action": "close referral loops and follow-up gaps instead of creating another task list",
        "news_action": "review dropped transitions, missed follow-ups, and outreach backlog",
        "regulatory_action": "map documentation or reporting changes to discharge and follow-up workflows",
    },
}


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
    return [
        PRIORITY_THEME_RULES.get(theme_key, {}).get("label", theme_key)
        for theme_key in theme_keys
    ]


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
    for label, keywords in WORKFLOW_KEYWORD_RULES.items():
        if any(keyword in text for keyword in keywords):
            matched.append(label)
    return matched


def workflow_guidance_for_item(item: Dict[str, object]) -> Dict[str, str]:
    wedges = infer_workflow_wedges(item)
    if wedges:
        return WORKFLOW_OPERATOR_GUIDANCE.get(
            wedges[0],
            WORKFLOW_OPERATOR_GUIDANCE["provider/admin ops"],
        )
    return WORKFLOW_OPERATOR_GUIDANCE["provider/admin ops"]


def workflow_actions_for_item(item: Dict[str, object]) -> Dict[str, str]:
    wedges = infer_workflow_wedges(item)
    if wedges:
        return WORKFLOW_SPECIFIC_ACTIONS.get(
            wedges[0],
            WORKFLOW_SPECIFIC_ACTIONS["provider/admin ops"],
        )
    return WORKFLOW_SPECIFIC_ACTIONS["provider/admin ops"]


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


def summarize_item(item: Dict[str, object]) -> Dict[str, str]:
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

    text = ""
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        text = response.output_text.strip()
    except Exception:
        text = ""

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


def summarize_items(items: List[Dict[str, object]]) -> List[Dict[str, str]]:
    return [summarize_item(item) for item in items]


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

    text = ""
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        text = response.output_text.strip()
    except Exception:
        text = ""

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

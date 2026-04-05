import json
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
]


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


def why_it_matters_is_specific(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in GENERIC_WHY_IT_MATTERS_PHRASES):
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
    return mentions_workflow and mentions_action


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
    if item.get("category") == "Regulatory":
        return (
            f"Affects {guidance['workflow']}; {guidance['audience']} should map this to roadmap, integration, or compliance work in the next planning cycle."
        )
    if item.get("is_generic_devtool") and not item.get("generic_repo_cap_exempt"):
        return (
            f"Background infra for {guidance['workflow']}; only track it if you can tie it to a real operator workflow in the next 7 to 30 days."
        )
    return (
        f"Affects {guidance['workflow']}; {guidance['audience']} should {guidance['action']} in the next 7 to 30 days."
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
- Prefer forms like "Affects X; Y should Z"
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

    if not summary:
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

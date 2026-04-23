from __future__ import annotations

from typing import Any, Dict, Iterable, List


PRIORITY_THEME_RULES = {
    "healthcare_ai_pm": {
        "label": "Healthcare AI PM",
        "keywords": [
            "digital health",
            "healthcare ai",
            "health it",
            "clinical workflow",
            "provider workflow",
            "care delivery",
            "clinical decision support",
            "ehr",
            "epic",
            "cerner",
            "interoperability",
            "fhir",
            "tefca",
            "medical device software",
            "product strategy",
        ],
        "dimension_boosts": {
            "career_relevance": 2.0,
            "build_relevance": 1.0,
            "content_potential": 0.6,
            "regulatory_significance": 1.2,
        },
    },
    "healthcare_admin_automation": {
        "label": "Healthcare Admin Automation",
        "keywords": [
            "prior authorization",
            "prior auth",
            "referral",
            "referrals",
            "referral management",
            "patient intake",
            "intake",
            "eligibility",
            "benefits verification",
            "claims",
            "claims attachments",
            "utilization management",
            "utilization review",
            "revenue cycle",
            "rcm",
            "billing",
            "denials",
            "denial management",
            "documentation",
            "ambient",
            "scribe",
            "charting",
            "scheduling",
            "patient access",
            "forms",
            "fax",
            "contact center",
            "workflow automation",
            "appeals",
            "electronic signatures",
            "care coordination",
        ],
        "dimension_boosts": {
            "career_relevance": 1.8,
            "build_relevance": 2.0,
            "content_potential": 0.6,
            "regulatory_significance": 0.4,
            "side_hustle_relevance": 2.0,
        },
    },
    "agents_workflows": {
        "label": "Agents And Workflows",
        "keywords": [
            "agent",
            "agents",
            "agentic",
            "workflow engine",
            "orchestration",
            "multi-agent",
            "copilot",
            "task runner",
            "autonomous",
        ],
        "dimension_boosts": {
            "career_relevance": 0.6,
            "build_relevance": 0.9,
            "content_potential": 0.4,
            "side_hustle_relevance": 0.4,
        },
    },
    "llm_eval_rag_governance_safety": {
        "label": "LLM Evals RAG Governance Safety",
        "keywords": [
            "eval",
            "evaluation",
            "benchmark",
            "guardrail",
            "governance",
            "safety",
            "rag",
            "retrieval",
            "vector",
            "knowledge base",
            "audit",
            "monitoring",
            "hallucination",
            "prompt injection",
            "privacy",
            "security",
        ],
        "dimension_boosts": {
            "career_relevance": 0.9,
            "build_relevance": 1.1,
            "content_potential": 0.6,
            "regulatory_significance": 1.4,
        },
    },
    "low_reg_friction_wedges": {
        "label": "Low Friction Product Wedges",
        "keywords": [
            "documentation",
            "scheduling",
            "patient messaging",
            "call center",
            "patient access",
            "operations",
            "back office",
            "appeals",
            "claims",
            "revenue cycle",
            "quality reporting",
            "ambient",
            "referral",
            "intake",
            "care coordination",
            "workflow support",
        ],
        "dimension_boosts": {
            "build_relevance": 1.3,
            "content_potential": 0.6,
            "side_hustle_relevance": 1.9,
            "career_relevance": 0.9,
        },
    },
    "content_opportunities": {
        "label": "Content Opportunities",
        "keywords": [
            "policy",
            "framework",
            "launch",
            "funding",
            "hiring",
            "roadmap",
            "trend",
            "roi",
            "adoption",
            "case study",
            "benchmark",
            "industry",
        ],
        "dimension_boosts": {
            "content_potential": 1.0,
            "career_relevance": 0.2,
            "build_relevance": 0.1,
        },
    },
    "job_search": {
        "label": "Healthcare AI PM Roles",
        "keywords": [
            "product manager",
            "pm role",
            "hiring",
            "leadership",
            "platform",
            "roadmap",
            "implementation",
            "stakeholder",
            "go to market",
            "enterprise",
            "workflow roi",
        ],
        "dimension_boosts": {
            "career_relevance": 1.9,
            "content_potential": 0.5,
            "regulatory_significance": 0.4,
        },
    },
}

TRACKED_ENTITY_RULES = {
    "openai": ["openai", "gpt", "chatgpt"],
    "anthropic": ["anthropic", "claude"],
    "google": ["google", "gemini", "deepmind"],
    "microsoft": ["microsoft", "azure"],
    "meta": ["meta", "llama"],
    "nvidia": ["nvidia"],
    "fda": ["fda", "food and drug administration"],
    "cms": ["cms", "centers for medicare and medicaid services"],
    "astp_onc": ["astp", "onc", "health it certification"],
    "ftc": ["ftc", "federal trade commission"],
    "hhs": ["hhs", "department of health and human services"],
    "tefca": ["tefca"],
    "fhir": ["fhir"],
    "epic": ["epic"],
}

WORKFLOW_RULES = {
    "prior_auth": {
        "label": "prior auth",
        "keywords": [
            "prior authorization",
            "prior auth",
            "utilization management",
            "utilization review",
            "payer auth",
        ],
        "workflow": "prior auth and utilization management",
        "audience": "payer and provider ops leaders",
        "focus": "interoperable attachment exchange and audit-ready automation",
        "action": "rank bets by denial reduction, status visibility, and payer handoff quality",
        "build_idea": "Prototype a prior-auth assistant that packages documentation, attachments, and denial-prep into one handoff.",
        "content_angle": "Why prior-auth workflow ROI beats generic agent demos.",
        "interview_talking_point": "Explain how you would prioritize prior-auth automation by denial lift, turnaround time, and auditability.",
        "actors": "prior-auth managers, denials leads, and integration owners",
        "repo_action": "reduce documentation assembly, payer rules lookup, and status chasing",
        "news_action": "audit where evidence packets, payer rules, or status updates still break the workflow",
        "regulatory_action": "map attachment, signature, and audit-trail gaps",
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
        "workflow": "referral and intake",
        "audience": "access and care-coordination teams",
        "focus": "intake completeness and referral routing",
        "action": "prioritize products that cut manual intake, missing documentation, and referral leakage",
        "build_idea": "Prototype an intake copilot that flags missing documents and routes referrals before staff touch them.",
        "content_angle": "Referral leakage is a better automation wedge than another generic copilot.",
        "interview_talking_point": "Describe how you would measure automation value in intake completeness and referral conversion.",
        "actors": "access directors, intake supervisors, and referral owners",
        "repo_action": "cut missing-document rework, manual routing, and referral leakage",
        "news_action": "review intake completeness, routing errors, and time-to-scheduled-visit",
        "regulatory_action": "check intake data capture and referral-routing controls",
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
        "workflow": "documentation and ambient capture",
        "audience": "provider ops leaders",
        "focus": "note capture that survives compliance review",
        "action": "prioritize tools tied to note throughput, auditability, and cleaner downstream handoffs",
        "build_idea": "Prototype an ambient handoff assistant that turns visit context into structured follow-up work.",
        "content_angle": "Ambient AI wins when it improves downstream ops, not just note drafting.",
        "interview_talking_point": "Talk about documentation tools in terms of throughput, compliance risk, and handoff quality.",
        "actors": "clinical informatics leads and provider-ops owners",
        "repo_action": "turn visit context into usable downstream tasks instead of another note layer",
        "news_action": "check whether note capture improves coding, follow-up, or inbox handoffs",
        "regulatory_action": "review clinician review, retention, and downstream audit controls",
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
        "workflow": "scheduling and patient access",
        "audience": "access-center leaders",
        "focus": "capacity management and fewer reschedules",
        "action": "prioritize tools that improve fill rate, template utilization, and manual reschedule load",
        "build_idea": "Prototype a scheduling copilot that surfaces open capacity and prevents avoidable reschedules.",
        "content_angle": "Scheduling automation is a real buyer wedge because the metrics are immediate.",
        "interview_talking_point": "Frame scheduling AI around fill rate, template utilization, and manual touch reduction.",
        "actors": "access-center managers and patient-access owners",
        "repo_action": "improve fill rate, template utilization, and reschedule recovery",
        "news_action": "review hold times, open capacity, and preventable reschedules",
        "regulatory_action": "check whether scheduling data capture or reporting obligations changed",
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
        "workflow": "revenue cycle and denials",
        "audience": "RCM and denials teams",
        "focus": "denial prevention and appeal prep",
        "action": "prioritize products tied to recoveries, write-offs, and turnaround time instead of abstract autonomy",
        "build_idea": "Prototype a denial-worklist assistant that summarizes evidence, appeal steps, and next actions.",
        "content_angle": "RCM buyers care about recoveries and turnaround, not generic AI orchestration.",
        "interview_talking_point": "Explain how you would rank denials automation by recovery rate, cycle time, and auditability.",
        "actors": "RCM directors, denials leads, and appeals managers",
        "repo_action": "speed evidence retrieval, denial triage, and appeal prep",
        "news_action": "review avoidable denials, write-offs, and queue turnaround",
        "regulatory_action": "map policy changes to claims, attachments, and appeal workflows",
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
        "workflow": "interoperability and data exchange",
        "audience": "health IT and integration owners",
        "focus": "standards-based exchange instead of custom point integrations",
        "action": "prioritize roadmap work around FHIR, APIs, and auditability before another generic agent experiment",
        "build_idea": "Prototype an interoperability layer that packages the minimum payload and audit trail for a high-friction workflow.",
        "content_angle": "The next wedge is boring on purpose: standards, payload quality, and audit trails.",
        "interview_talking_point": "Discuss interoperability bets in terms of integration burden, auditability, and time-to-deployment.",
        "actors": "integration leads and health IT owners",
        "repo_action": "reduce custom interface work while preserving an audit trail",
        "news_action": "inventory FHIR/API dependencies and brittle handoffs on active roadmap work",
        "regulatory_action": "map API, payload, and audit-trail gaps before trading-partner work starts",
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
        "workflow": "provider and admin operations",
        "audience": "ops leaders",
        "focus": "manual inbox, forms, and contact-center handoffs",
        "action": "prioritize tools that compress manual work and handoff delay in the next planning cycle",
        "build_idea": "Prototype a back-office assistant that triages forms, inbox items, and the next required handoff.",
        "content_angle": "Admin ops is where AI can prove value without pretending to replace whole teams.",
        "interview_talking_point": "Talk about provider-ops AI in terms of touch reduction, handoff quality, and operational lift.",
        "actors": "ops managers and back-office leads",
        "repo_action": "shrink inbox, forms, or contact-center handoffs on a live queue",
        "news_action": "review which back-office queues still depend on manual triage and status chasing",
        "regulatory_action": "check whether reporting, forms handling, or audit obligations changed",
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
        "workflow": "care coordination",
        "audience": "care management and referral teams",
        "focus": "referral closure and transition tracking",
        "action": "prioritize systems that reduce leakage, missed follow-ups, and manual outreach gaps",
        "build_idea": "Prototype a care-coordination assistant that tracks missing follow-ups and closes referral loops.",
        "content_angle": "Care coordination automation is valuable when it closes loops, not when it adds another inbox.",
        "interview_talking_point": "Frame care-coordination AI around referral closure, follow-up completion, and fewer dropped transitions.",
        "actors": "care-management leads and referral owners",
        "repo_action": "close referral loops and follow-up gaps instead of creating another task list",
        "news_action": "review dropped transitions, missed follow-ups, and outreach backlog",
        "regulatory_action": "map documentation or reporting changes to discharge and follow-up workflows",
    },
}

DEFAULT_WORKFLOW_RULE_KEY = "provider_admin_ops"
DEFAULT_WORKFLOW_LABEL = WORKFLOW_RULES[DEFAULT_WORKFLOW_RULE_KEY]["label"]
WORKFLOW_LABEL_KEYWORDS = {
    rule["label"]: list(rule["keywords"])
    for rule in WORKFLOW_RULES.values()
}

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

WORKFLOW_CONTEXT_KEYWORDS = sorted(
    {
        keyword
        for keywords in WORKFLOW_LABEL_KEYWORDS.values()
        for keyword in keywords
    }
    | {
        "integration",
        "workflow",
        "provider",
        "admin ops",
        "ops",
        "contact center",
        "back office",
    }
)


def theme_label(theme_key: str) -> str:
    return PRIORITY_THEME_RULES.get(theme_key, {}).get("label", theme_key)


def theme_labels(theme_keys: Iterable[str]) -> List[str]:
    return [theme_label(str(theme_key)) for theme_key in theme_keys]


def workflow_rule_for_key(workflow_key: str | None) -> Dict[str, Any]:
    if workflow_key and workflow_key in WORKFLOW_RULES:
        return WORKFLOW_RULES[workflow_key]
    return WORKFLOW_RULES[DEFAULT_WORKFLOW_RULE_KEY]


def workflow_rule_for_label(workflow_label: str | None) -> Dict[str, Any]:
    label = str(workflow_label or "").strip()
    for rule in WORKFLOW_RULES.values():
        if rule["label"] == label:
            return rule
    return WORKFLOW_RULES[DEFAULT_WORKFLOW_RULE_KEY]


def workflow_guidance_for_label(workflow_label: str | None) -> Dict[str, str]:
    rule = workflow_rule_for_label(workflow_label)
    return {
        "workflow": str(rule["workflow"]),
        "audience": str(rule["audience"]),
        "focus": str(rule["focus"]),
        "action": str(rule["action"]),
        "build_idea": str(rule["build_idea"]),
        "content_angle": str(rule["content_angle"]),
        "interview_talking_point": str(rule["interview_talking_point"]),
    }


def workflow_actions_for_label(workflow_label: str | None) -> Dict[str, str]:
    rule = workflow_rule_for_label(workflow_label)
    return {
        "actors": str(rule["actors"]),
        "repo_action": str(rule["repo_action"]),
        "news_action": str(rule["news_action"]),
        "regulatory_action": str(rule["regulatory_action"]),
    }

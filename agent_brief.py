from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from config import (
    DIGEST_ANALYST_AGENT_ENABLED,
    DIGEST_ANALYST_AGENT_MODEL,
    DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS,
    PRIORITY_THEME_RULES,
)
from summarize import summarize_digest_strategy, top_insight_is_specific


PRIORITIES = [
    "AI Product Management in healthcare",
    "Healthcare admin automation",
    "Agents and agent workflows",
    "LLM evals, RAG, governance, and safety",
    "Side hustle and low-regulatory-friction wedges",
    "Content opportunities for LinkedIn and X",
    "Healthcare AI PM job-search relevance",
]

AGENT_INSTRUCTIONS = """
You are the Digest Analyst Agent for Daily AI Digest v2.

You analyze a pre-filtered, pre-scored shortlist. Do not re-rank globally, do not invent facts, and do not restate every item.
Your job is judgment and synthesis only.

Return concise operator-facing output:
- top_insight: the single most decision-useful takeaway for today
- content_angle: a public-facing angle for LinkedIn or X
- build_idea: one narrow workflow or product idea worth prototyping
- interview_talking_point: one PM interview-ready framing
- watch_item: one company, policy, or theme to keep tracking

Rules:
- Be specific to the provided shortlist and priorities
- Keep sections distinct from each other
- Avoid repeating the same thesis in multiple fields
- No hype, no fluff, no generic AI summary language
- Top insight must name one workflow wedge from the shortlist and the concrete operator implication
- Prefer forms like "For prior auth, X matters because Y" or "PMs should prioritize Z over generic agent tooling"
- Ban empty abstractions like "accelerate automation" or "AI is converging"
- Prefer short sentences or sharp phrases
- Keep top_insight to one sentence and roughly 15-30 words
- Keep the other fields to one short sentence or phrase each
- If evidence is weak, return empty strings for optional fields rather than filler
""".strip()


@dataclass
class DigestOperatorBrief:
    top_insight: str
    content_angle: str = ""
    build_idea: str = ""
    interview_talking_point: str = ""
    watch_item: str = ""

    def normalized(self) -> "DigestOperatorBrief":
        return DigestOperatorBrief(
            top_insight=self.top_insight.strip(),
            content_angle=self.content_angle.strip(),
            build_idea=self.build_idea.strip(),
            interview_talking_point=self.interview_talking_point.strip(),
            watch_item=self.watch_item.strip(),
        )

    def is_valid(self) -> bool:
        normalized = self.normalized()
        return bool(normalized.top_insight) and top_insight_is_specific(
            normalized.top_insight
        )

    def to_dict(self) -> Dict[str, str]:
        return asdict(self.normalized())


def theme_labels(theme_keys: List[str]) -> List[str]:
    return [
        PRIORITY_THEME_RULES.get(theme_key, {}).get("label", theme_key)
        for theme_key in theme_keys
    ]


def compact_digest_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact_items: List[Dict[str, Any]] = []
    for item in items:
        compact_items.append(
            {
                "category": str(item.get("category", "") or ""),
                "title": str(item.get("title", "") or ""),
                "source": str(item.get("source", "") or ""),
                "topic_key": str(item.get("topic_key", "") or ""),
                "summary": str(item.get("summary", "") or ""),
                "why_it_matters": str(item.get("why_it_matters", "") or ""),
                "signal": str(item.get("signal", "") or ""),
                "workflow_wedges": [
                    str(label).strip()
                    for label in item.get("workflow_wedges", [])
                    if str(label).strip()
                ],
                "operator_relevance": str(item.get("operator_relevance", "") or ""),
                "near_term_actionability": str(
                    item.get("near_term_actionability", "") or ""
                ),
                "is_generic_devtool": bool(item.get("is_generic_devtool")),
                "generic_repo_cap_exempt": bool(item.get("generic_repo_cap_exempt")),
                "priority_score": round(float(item.get("priority_score", 0.0) or 0.0), 2),
                "objective_scores": {
                    str(key): round(float(value or 0.0), 2)
                    for key, value in (item.get("objective_scores", {}) or {}).items()
                },
                "score_focus": [
                    str(label).strip()
                    for label in item.get("score_focus", [])
                    if str(label).strip()
                ][:3],
                "matched_themes": theme_labels(item.get("matched_themes", []) or []),
            }
        )
    return compact_items


def build_agent_input(
    items: List[Dict[str, Any]],
    memory_snapshot: Dict[str, Any] | None = None,
) -> str:
    payload = {
        "priorities": PRIORITIES,
        "today_items": compact_digest_items(items),
        "memory_snapshot": memory_snapshot or {},
    }
    return json.dumps(payload, indent=2)


def coerce_brief_output(output: Any) -> DigestOperatorBrief | None:
    if isinstance(output, DigestOperatorBrief):
        brief = output.normalized()
        return brief if brief.is_valid() else None

    if isinstance(output, dict):
        try:
            brief = DigestOperatorBrief(
                top_insight=str(output.get("top_insight", "") or ""),
                content_angle=str(output.get("content_angle", "") or ""),
                build_idea=str(output.get("build_idea", "") or ""),
                interview_talking_point=str(
                    output.get("interview_talking_point", "") or ""
                ),
                watch_item=str(output.get("watch_item", "") or ""),
            ).normalized()
        except Exception:
            return None
        return brief if brief.is_valid() else None

    return None


def _import_agents_sdk() -> tuple[Any, Any, Any] | None:
    try:
        from agents import Agent, ModelSettings, Runner
    except ImportError:
        return None
    return Agent, ModelSettings, Runner


async def _run_digest_analyst_agent(
    items: List[Dict[str, Any]],
    memory_snapshot: Dict[str, Any] | None = None,
) -> DigestOperatorBrief | None:
    sdk = _import_agents_sdk()
    if not sdk:
        return None

    Agent, ModelSettings, Runner = sdk
    agent = Agent(
        name="Digest Analyst Agent",
        instructions=AGENT_INSTRUCTIONS,
        model=DIGEST_ANALYST_AGENT_MODEL,
        model_settings=ModelSettings(
            temperature=0.2,
            max_tokens=250,
        ),
        output_type=DigestOperatorBrief,
    )
    result = await asyncio.wait_for(
        Runner.run(
            agent,
            build_agent_input(items, memory_snapshot),
        ),
        timeout=DIGEST_ANALYST_AGENT_TIMEOUT_SECONDS,
    )
    return coerce_brief_output(getattr(result, "final_output", None))


def _run_digest_analyst_agent_sync(
    items: List[Dict[str, Any]],
    memory_snapshot: Dict[str, Any] | None = None,
) -> DigestOperatorBrief | None:
    return asyncio.run(_run_digest_analyst_agent(items, memory_snapshot))


def build_agent_brief(
    items: List[Dict[str, Any]],
    memory_snapshot: Dict[str, Any] | None = None,
) -> DigestOperatorBrief | None:
    if not DIGEST_ANALYST_AGENT_ENABLED:
        return None

    try:
        brief = _run_digest_analyst_agent_sync(items, memory_snapshot)
        if not brief:
            print("Warning: Digest Analyst Agent returned no valid output, falling back.")
        return brief
    except Exception as exc:
        print(f"Warning: Digest Analyst Agent unavailable, falling back: {exc}")
        return None


def build_operator_brief(
    items: List[Dict[str, Any]],
    memory_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    agent_brief = build_agent_brief(items, memory_snapshot)
    if agent_brief:
        return agent_brief.to_dict()
    return summarize_digest_strategy(items, memory_snapshot)

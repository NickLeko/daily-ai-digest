import json
from typing import Dict, List

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, PRIORITY_THEME_RULES


client = OpenAI(api_key=OPENAI_API_KEY)


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


def item_prompt_context(item: Dict[str, str]) -> str:
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
    return (
        f"Matched themes: {theme_summary}. "
        f"Strongest scoring dimensions: {dimension_summary}. "
        f"Top objective: {top_objective}."
    )


def summarize_item(item: Dict[str, str]) -> Dict[str, str]:
    category_specific_rule = ""
    if item["category"] == "Regulatory":
        category_specific_rule = (
            "For regulatory items, limit the summary to the most decision-relevant information only. "
            "Ignore detailed study methodology, procedural nuance, and clinical background unless it directly changes product, compliance, or workflow decisions. "
            "Keep it compact."
        )
    elif item["category"] == "Repo":
        category_specific_rule = (
            "For repo items, focus on what the tool enables in practice, not a generic definition of what it is."
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
- The "why_it_matters" line should answer: what should a healthcare AI PM do differently because of this?
- "signal" must be one of: high, medium, low
- Use "high" only for items with strong practical importance right now
- Use "medium" for useful but not urgent items
- Use "low" for background signal
- EXCLUDE_KEYWORDS = ["game", "education", "chatbot ui"]

Additional category rule:
{category_specific_rule}
""".strip()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    text = response.output_text.strip()

    try:
        parsed = parse_json_payload(text)
        if not parsed:
            raise ValueError("No JSON payload found.")
        summary = parsed["summary"].strip()
        why_it_matters = parsed["why_it_matters"].strip()
        signal = parsed["signal"].strip().lower()
        if signal not in {"high", "medium", "low"}:
            signal = "medium"
    except Exception:
        summary = text
        why_it_matters = "Useful signal for tracking practical developments in healthcare AI and workflow automation."
        signal = "medium"

    return {
        **item,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "signal": signal,
    }


def summarize_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [summarize_item(item) for item in items]


def fallback_digest_strategy(items: List[Dict[str, str]]) -> Dict[str, str]:
    ranked_items = sorted(
        items,
        key=lambda item: float(item.get("priority_score", 0.0) or 0.0),
        reverse=True,
    )
    top_item = ranked_items[0] if ranked_items else {}
    top_theme = theme_labels(top_item.get("matched_themes", []) or [])[:1]
    theme_phrase = top_theme[0] if top_theme else "workflow ROI and governance"
    watch_reference = top_item.get("source") or top_item.get("title") or "healthcare admin automation"

    return {
        "top_insight": (
            f"Prioritize {theme_phrase.lower()} work that shows immediate workflow ROI and can survive governance scrutiny."
        ),
        "content_angle": (
            f"The wedge is narrower than generic AI hype: {theme_phrase} with operational proof."
        ),
        "build_idea": (
            "Prototype a single workflow assistant around prior auth, claims, or documentation handoffs."
        ),
        "interview_talking_point": (
            "Talk about ranking healthcare AI bets by workflow pain, compliance surface area, and measurable operator lift."
        ),
        "watch_item": f"Watch {watch_reference} for repeat signal and operator relevance.",
    }


def summarize_digest_strategy(
    items: List[Dict[str, str]],
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
- No hype
- No generic language
- Focus on what deserves attention or action next
- Write like an operator, not a newsletter writer
- Keep every field concise and practical
- Empty strings are allowed if evidence is weak, but prefer useful specificity
""".strip()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    text = response.output_text.strip()

    try:
        parsed = parse_json_payload(text)
        if parsed and parsed.get("top_insight"):
            return {
                "top_insight": str(parsed.get("top_insight", "") or "").strip(),
                "content_angle": str(parsed.get("content_angle", "") or "").strip(),
                "build_idea": str(parsed.get("build_idea", "") or "").strip(),
                "interview_talking_point": str(
                    parsed.get("interview_talking_point", "") or ""
                ).strip(),
                "watch_item": str(parsed.get("watch_item", "") or "").strip(),
            }
    except Exception:
        pass

    fallback = fallback_digest_strategy(items)
    cleaned_text = text.strip().strip("`").strip()
    if cleaned_text and "top_insight" not in cleaned_text.lower():
        fallback["top_insight"] = cleaned_text

    return fallback

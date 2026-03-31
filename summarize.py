import json
from typing import Dict, List

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL


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


def summarize_top_insight(items: List[Dict[str, str]]) -> str:
    compact_items = []
    for item in items:
        compact_items.append(
            {
                "category": item["category"],
                "title": item["title"],
                "summary": item["summary"],
                "why_it_matters": item["why_it_matters"],
                "signal": item["signal"],
            }
        )

    prompt = f"""
You are writing a single top-line insight for a healthcare AI product manager.

Below is today's digest content:
{json.dumps(compact_items, indent=2)}

Return valid JSON only:
{{
  "top_insight": "One sentence, sharp and synthesis-heavy."
}}

Rules:
- One sentence only
- No hype
- No generic language
- Focus on the most important cross-cutting pattern
- Write like an operator, not a newsletter writer
""".strip()
    

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    text = response.output_text.strip()

    try:
        parsed = parse_json_payload(text)
        if parsed and parsed.get("top_insight"):
            return str(parsed["top_insight"]).strip()
    except Exception:
        pass

    cleaned_text = text.strip().strip("`").strip()
    if cleaned_text and "top_insight" not in cleaned_text.lower():
        return cleaned_text

    return "Operational reliability, workflow ROI, and governance are becoming more important than raw model novelty in healthcare AI adoption."

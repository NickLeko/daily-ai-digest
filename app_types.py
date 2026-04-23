from __future__ import annotations

from typing import Any, Dict, List, TypedDict


ScoreMap = Dict[str, float]


class DigestItem(TypedDict, total=False):
    category: str
    title: str
    url: str
    summary: str
    why_it_matters: str
    signal: str
    source: str
    item_key: str
    published_at: object
    priority_score: float
    story_score: float
    objective_scores: ScoreMap
    score_dimensions: ScoreMap
    matched_themes: List[str]
    workflow_wedges: List[str]
    operator_relevance: str
    near_term_actionability: str
    confidence: str
    confidence_display: str
    confidence_override_reason: str
    signal_quality: str
    low_signal_announcement: bool
    material_operator_signal: bool
    market_bucket_ids: List[str]
    market_buckets: List[str]
    thesis_links: List[Dict[str, Any]]
    watchlist_matches: List[Dict[str, Any]]


class Story(TypedDict, total=False):
    story_id: str
    cluster_id: str
    duplicate_group_id: str
    cluster_title: str
    title: str
    category: str
    item_type: str
    canonical_url: str
    url: str
    source: str
    source_names: List[str]
    source_domains: List[str]
    supporting_item_ids: List[str]
    supporting_item_count: int
    summary: str
    evidence: str
    why_it_matters: str
    action_suggestion: str
    objective_scores: ScoreMap
    reliability_score: int
    reliability_label: str
    confidence: str
    confidence_display: str
    confidence_override_reason: str
    story_score: float
    priority_score: float
    signal: str
    matched_themes: List[str]
    workflow_wedges: List[str]
    operator_relevance: str
    near_term_actionability: str
    watchlist_matches: List[Dict[str, Any]]
    change_status: str
    signal_quality: str
    low_signal_announcement: bool
    material_operator_signal: bool
    materiality_reason: str


class OperatorBrief(TypedDict, total=False):
    version: int
    date: str
    generated_at: str
    summary: Dict[str, Any]
    operator_moves: Dict[str, str]
    what_changed: List[Dict[str, Any]]
    thesis_tracker: List[Dict[str, Any]]
    market_map: Dict[str, Any]
    watchlist_hits: List[Dict[str, Any]]
    quality_eval: Dict[str, Any]
    top_picks: Dict[str, Any]
    near_miss_items: List[Dict[str, Any]]
    skipped_news_items: List[Dict[str, Any]]
    stories: List[Story]
    story_cards: List[Story]
    items: List[DigestItem]
    selection_diagnostics: Dict[str, Any]
    memory_snapshot: Dict[str, Any]


class SelectionDiagnostic(TypedDict, total=False):
    version: int
    mode: str
    generated_at: str
    daily_selection: Dict[str, Any]
    selected_stories: List[Dict[str, Any]]
    no_signal_fallback: Dict[str, Any]


class WeeklyMemoInput(TypedDict, total=False):
    memory: Dict[str, Any]
    latest_brief: OperatorBrief
    selection_audit: Dict[str, Any]

# Operator Cockpit Notes

## Why this design

The repo already had a clean fetch -> summarize -> score -> render pipeline plus lightweight JSON memory. The least fragile path was to preserve that shape and add a canonical story layer between scoring and rendering.

That gives the project:

- a structured artifact that can power email and local UI from the same data
- duplicate suppression without rewriting fetchers
- daily delta analysis using file-based history instead of a database
- editable policy/config files for reliability, theses, market buckets, and watchlists

## Current flow

1. `data.py` fetches and locally scores repo, news, and regulatory items.
2. `summarize.py` produces item summaries and item-level why-it-matters text.
3. `operator_brief.py` normalizes items, assigns reliability/thesis/market metadata, clusters related stories, compares against the previous brief, computes quality evals, and builds the canonical operator brief artifact.
4. `formatter.py` renders the email and local cockpit from that artifact.
5. `memory.py` persists both item history and daily brief history in JSON.

## Practical tradeoffs

- Clustering is intentionally lightweight and explainable. It uses token overlap plus workflow, thesis, source, and market signals rather than embeddings or extra infrastructure.
- Source reliability is config-driven. Overrides live in `data/source_policies.json`.
- Thesis tracking is heuristic and keyword-based for now. The goal is editability and determinism first.
- The GitHub watcher is intentionally lightweight. It uses watchlist matches against the current repo signal surface and stored history rather than a separate always-on polling subsystem.

## What shipped as P0

- canonical operator brief artifact
- story clustering and duplicate suppression
- source reliability scoring
- what-changed delta layer
- thesis tracking
- market map pulse
- digest quality evals
- better objective separation through story-level picks
- more specific story-level why-it-matters and action suggestions
- richer JSON memory across days

## Still intentionally lightweight

- thesis classification is heuristic, not model-judged
- watchlist support is useful but not a full GitHub polling engine yet
- the local cockpit is HTML generated from the same brief, not a heavier standalone app

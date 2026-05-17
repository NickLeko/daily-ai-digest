# Operator Review

Review date: 2026-05-17

This review covers the current repository as a healthcare AI/workflow intelligence engine. It focuses on small, reviewable improvements to quality, reliability, usefulness, and diagnostics rather than a product rewrite.

## System Map

- Ingestion and source normalization live in `data.py`, `data_news.py`, `data_repo.py`, `data_regulatory.py`, and `data_regulatory_select.py`.
- Personalization and item scoring live in `scoring.py`, with shared thresholds centralized in `selection_policy.py`.
- Healthcare workflow taxonomy, thesis language, and keyword rules live in `taxonomy.py` plus editable JSON files in `data/`.
- Story clustering, reliability, thesis/watchlist metadata, story card admission, and operator artifacts live in `operator_brief.py` and `operator_brief_selection.py`.
- Daily rendering lives in `formatter_daily.py`; weekly/cockpit rendering lives in `formatter_weekly.py`; shared HTML helpers live in `formatter_shared.py`.
- Selection diagnostics live in `selection_audit.py`.
- Regression coverage lives in `tests/`, with semantic HTML snapshots in `tests/snapshots/`.
- Local artifacts are `latest_digest.html`, `latest_operator_brief.json`, `latest_operator_cockpit.html`, `latest_selection_audit.json`, `latest_selection_audit.md`, and `latest_weekly_operator_memo.md`.

## Current Strengths

- The system is story-led, not item-led. `operator_brief.py` clusters related raw items, carries source/reliability metadata, and prevents a single noisy feed item from dominating without passing story gates.
- Selection policy is layered. Item scoring, materiality classification, story surface worthiness, daily render quality, single-story strictness, and controlled backfill each catch different failure modes.
- The healthcare workflow focus is explicit. `taxonomy.py` encodes prior auth, RCM/denials, referral/intake, ambient documentation, scheduling, interoperability, provider/admin ops, and care coordination.
- Low-signal defenses are no longer just score penalties. Weak or soft-announcement stories are confidence-capped, demoted, excluded from story cards, and visible in diagnostics.
- Renderer tests are semantic instead of brittle style snapshots. `tests/test_digest_render_snapshots.py` strips most inline style noise but preserves rendered structure and links.
- Selection diagnostics are useful for operator review. `latest_selection_audit.md` and `selection_audit.py` explain target-fit failures, daily-limit effects, duplicate suppression, backfill, rejection buckets, and no-signal collapse reasons.
- Daily and weekly modes serve different jobs. Daily is scan-first; weekly/cockpit keeps thesis tracker, market map, top picks, quality eval, and operator moves.

## Current Weaknesses

- The policy still relies heavily on keyword materiality. It can mistake language about a workflow category for proof of workflow impact unless negation and hard-evidence gates stay tight.
- Some evidence categories are broad. Terms like workflow automation, partnership, customer, model, or deployment need surrounding proof context; otherwise vendor/news launch language can look stronger than it is.
- Current local `latest_*` artifacts are stale relative to the current code path. For example, `latest_digest.html` reflects an older daily renderer label and should be regenerated before using it as the canonical UI reference.
- Artifact freshness is not self-evident in rendered HTML. JSON has dates, but local HTML review can still be misleading if files were generated before recent policy changes.
- Story-card admission depends on several inferred fields. If an external caller bypasses `attach_priority_scores`, missing `hard_signal_evidence` can change behavior unless normalization infers it.
- Source reliability rules are editable, but unclassified credible-looking domains default to medium directional evidence. That is pragmatic, but it can make independent coverage of vendor announcements look stronger than intended.

## Selection-Policy Edge Cases

- PR-only AI workflow announcements: credible-source coverage of a vendor partnership can include prior auth, payer, AI agents, and workflow automation while explicitly saying there is no deployment, customer, metric, or production rollout. This is now covered by a regression and demoted by deployment-proof negation.
- Prior authorization wording: the generic capability keyword `authorization` was too broad because it collided with prior authorization. Removing it reduces false materiality without hurting final-rule or deployment stories.
- Empty hard-evidence lists: `hard_signal_evidence: []` should mean no hard evidence, not "infer workflow impact anyway." Backward-compatible inference should apply only when the field is absent.
- Recall/enforcement items: official FDA/openFDA items can be high reliability and high regulatory score but low operator usefulness. The recall gate correctly requires workflow, reimbursement, implementation, watchlist, or support-count signal before primary placement.
- Broad policy/watch items: regulatory stories deserve watchlist treatment even when not operator-grade, but should only take top slots when there is a near-term operational change, compliance requirement, reimbursement effect, or workflow consequence.
- Generic repos: agent frameworks, SDKs, boilerplates, and developer tools should not surface unless they have a healthcare/workflow anchor, watchlist match, or governance/eval relevance strong enough to matter.
- Strong workflow stories that should not be demoted: named provider/payer deployments, production rollouts, regulatory requirements, operational metrics, reimbursement effects, and concrete integration/interoperability changes should continue to beat generic AI news even if source confidence is only medium.

## Renderer Readability Issues

- Daily cards are now compact and useful, but the "Hard signal detected" line can read mechanical when evidence labels are generic. It is useful for auditability, less polished as prose.
- "Why this fits the healthcare AI/workflow wedge" is clear but long. On mobile or in email clients, it may compete with the summary and why-it-matters lines.
- Daily mode intentionally hides weekly context. That is good for scanning, but it means thesis/market context is only available in cockpit/weekly artifacts.
- Near-miss and selection-audit sections are helpful on quiet days, but could feel dense if they grow. The current limit of three near misses is reasonable.
- The stale `latest_digest.html` artifact should not be used to judge current renderer wording until regenerated.

## Test Gaps

- Existing coverage is strong for rendering snapshots, quiet-day behavior, generic repo filtering, real bad-output fixtures, recall gates, confidence overrides, and selection diagnostics.
- The new regressions cover PR-only AI workflow partnership false positives and named-provider workflow metric preservation.
- Remaining gaps:
  - More table-driven materiality tests for negated proof phrases.
  - Fresh artifact-generation smoke test that asserts `latest_*` files use the current renderer names and audit schema.
  - Cross-source clustering tests where a weak PR item is paired with a strong independent deployment item.
  - Source policy tests for unclassified medium-reliability domains that repeatedly publish vendor launch coverage.
  - Renderer tests for empty/missing URL, very long recall titles, and dense near-miss text.

## Recommended Improvements

### Now

- Regenerate local artifacts after the current policy hardening and compare `latest_digest.html`, `latest_operator_brief.json`, and `latest_selection_audit.md` against expectations.
- Add a tiny freshness note to local HTML artifacts or audit markdown so reviewers can tell when they were generated.
- Expand materiality tests for common negation phrases: no named customer, no production rollout, announced only, previewed only, not yet deployed.
- Keep source policy tuned so vendor press releases and lightly rewritten launch posts do not inherit too much trust.

### Later

- Split hard evidence into claim type and proof strength, for example `claimed_workflow`, `named_deployment`, `reported_metric`, `official_requirement`.
- Add a small fixture corpus of historically bad and historically good stories with expected tier, confidence, and rejection bucket.
- Add artifact schema version checks for `latest_operator_brief.json` and `latest_selection_audit.json`.
- Add optional reviewer notes in `selection_audit.md` for "why this almost slipped" and "why this strong story passed."

### Not Worth It

- A new app or UI rewrite. The current engine needs tighter diagnostics and fixtures more than another surface.
- Large ML/NLP dependencies for classification. The current rules are transparent and testable; the main need is better examples and narrower proof semantics.
- Over-optimizing the daily email layout before artifact freshness and story-quality gates are stable.
- Trying to surface a fixed number of stories every day. Quiet-day behavior is a feature for this product.

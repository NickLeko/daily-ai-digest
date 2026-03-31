# Digest Debug Report

## Symptoms Observed
- News could disappear while the header still claimed `3 news items`.
- Regulatory was initially dominated by stale recall items.
- After Phase 2 sourcing, broad CMS/FDA policy items could still qualify even when they lacked a real health IT, AI, workflow, or governance angle.

## Root Cause
- The original renderer used fixed section counts and no empty-section fallback.
- Regulatory originally relied too heavily on recall-heavy openFDA enforcement data.
- The source relevance gate was too permissive: a single broad term such as `guidance`, `rule`, `payment`, or `digital` could qualify an item.
- CMS relied on a malformed RSS feed, OCR was blocked by a live `403`, and ONC’s earlier age window was too tight for its publishing cadence.

## Fixes Shipped
- Added default news feeds, dynamic header counts, empty-section fallback copy, and pre-render validation.
- Added regulatory freshness, repeat penalties, recall cap logic, and diversity-aware selection.
- Added multi-source regulatory sourcing beyond openFDA:
  - FDA press releases
  - CMS newsroom
  - ASTP/ONC blog
  - OCR path explicitly disabled because the current source returns `403`
- Replaced raw substring keyword matching with token-aware matching so `ai` no longer matches inside words like `manifestations` or `animal`.
- Split regulatory source relevance into:
  - strong keywords
  - medium keyword groups
  - broad/noisy keywords
- Regulatory feed items now require either:
  - one strong product-relevant signal, or
  - two medium signals from distinct groups
- Broad coverage, enrollment, summit, committee, and readout items are now filtered unless paired with stronger health IT / workflow / governance terms.
- Replaced broken CMS RSS ingestion with direct parsing of the official CMS newsroom HTML.
- Loosened ONC age filtering to `90` days so sparse but still useful health IT posts are not dropped prematurely.
- Tightened release-candidate robustness:
  - digest body date now uses the configured local timezone instead of the runner's system clock
  - top insight JSON parsing now tolerates fenced or wrapped model output before falling back

## Remaining Risks
- openFDA endpoint health is inconsistent; the device endpoint returned a `500` during the latest live check.
- OCR is still unavailable because the live HHS press-room source is blocked by `403`.
- FDA press releases are now intentionally strict and may often yield zero items unless there is a clear AI, digital health, CDS, software, or governance angle.
- ONC can now contribute candidates again, but many posts are still older than the scoring freshness window and may lose later at ranking time.
- In the latest live RC dry run, Regulatory still rendered `0` selected items because the best remaining candidate scored `45`, below the current selection floor of `65`. This is not a silent failure because fallback copy rendered correctly, but it is the main behavior to watch over the next few days.

## What Changed In Source Coverage, Filtering, Scoring, Or Rendering
- Source coverage changed:
  - CMS now parses from HTML instead of malformed RSS.
  - ONC uses a wider source-age window.
  - OCR is explicitly disabled with logged reason.
- Filtering changed:
  - source-specific relevance buckets now gate candidates before scoring
  - new exclusion reasons include `relevance_broad_only` and `relevance_insufficient_relevance`
- Scoring did not change in the latest verification pass.
- Rendering changed slightly in the latest verification pass:
  - the displayed digest date now follows `LOCAL_TIMEZONE`
- Summarization handling changed slightly in the latest verification pass:
  - top insight parsing is more tolerant of fenced/wrapped JSON responses

## Tests Added Or Updated
- Added token-aware keyword tests proving `ai` does not match inside unrelated words.
- Added relevance-gating tests for:
  - broad CMS coverage/enrollment item filtered
  - claims attachments / interoperability rule passes
  - real FDA AI/digital-health/guidance item passes
  - generic advisory committee item filtered unless paired with stronger terms
- Added CMS newsroom HTML parser test.
- Added JSON parsing tests for wrapped/fenced top-insight payloads.
- Current local status: `17` tests passing.

## Before/After Behavior If Relevant
- Before:
  - `Exchange Coverage Remains Near Record High...` could survive as a CMS candidate.
  - `FDA Releases Draft Guidance on Alternatives to Animal Testing...` could survive because `guidance` matched.
- After the latest live source check:
  - CMS raw `6` -> normalized `2`
  - ONC raw `10` -> normalized `1`
  - FDA raw `16` -> normalized `0`
  - OCR raw `0` -> normalized `0`, explicitly disabled
- After the latest live RC dry run:
  - final rendered counts were `Repos=3`, `News=3`, `Regulatory=0`
  - the header was truthful
  - regulatory fallback text rendered explicitly
  - top insight rendered from a live synthesized response instead of the generic fallback line
- The surviving CMS candidates in the live sample were product/workflow-relevant:
  - `Administrative Simplification; Adoption of Standards for Health Care Claims Attachments Transactions and Electronic Signatures Final Rule CMS-0053-F`
  - `CMS Rule Phases Out Fax Machines, Snail Mail to Save Taxpayers $781.98 Million a Year`

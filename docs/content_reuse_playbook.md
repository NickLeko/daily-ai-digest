# Content Reuse Playbook

Use this when a selected digest story is strong enough to become external or saved material. Start from one story card in `latest_operator_brief.json` or the daily email.

## Source Fields To Pull

- `cluster_title`: headline or note title.
- `summary`: what happened.
- `why_it_matters`: operator implication.
- `hard_signal_evidence`: why it is more than noise.
- `workflow_wedges`: the practical healthcare workflow angle.
- `source_names` and `canonical_url`: attribution and link.
- `tier_reason`, `confidence`, and `confidence_display`: how strongly to phrase it.

## LinkedIn Post

Goal: turn the story into a concise operator POV.

Template:

```text
Healthcare AI signal worth watching: [story headline].

What changed: [one-sentence summary].

Why it matters: [workflow implication tied to prior auth, RCM, intake, ambient, scheduling, interoperability, or admin ops].

The practical question is not "is this AI interesting?" It is: [operator/product question about deployment, metric, integration, compliance, or workflow ownership].

My takeaway: [one concrete POV].

Source: [source/link]
```

Rules:

- Use confident language only for high-confidence stories with hard evidence.
- For medium confidence, say "worth watching" or "early signal," not "proof."
- Name the workflow wedge; do not write a generic AI post.
- Avoid turning near misses into claims. Use them only as "watch this if proof appears."

## Outreach Opener

Goal: use the story to start a relevant conversation with an operator, PM, founder, or hiring manager.

Template:

```text
Saw [story/source] on [workflow wedge]. The part that stood out was [hard signal: deployment, requirement, metric, reimbursement effect, integration change].

Curious how your team is thinking about [specific workflow problem]. Are you seeing this show up as [manual work, backlog, denial risk, implementation burden, compliance prep] yet?
```

Rules:

- Keep it under five sentences.
- Ask about their workflow, not your take.
- Use "curious" for medium-confidence stories and stronger language only when official or corroborated.

## Interview Talking Point

Goal: convert the story into a product/operator example.

Structure:

```text
Example: [story headline].
Signal: [hard evidence].
Workflow: [workflow wedge and user/owner].
Product implication: [what should be prioritized or measured].
How I would evaluate it: [metric, deployment proof, integration burden, safety/compliance concern].
```

Good angles:

- Prior auth: denial rate, turnaround time, evidence packet completeness, payer status visibility.
- RCM/denials: recoveries, write-offs, appeal cycle time, queue throughput.
- Referral/intake: missing documentation, routing accuracy, referral leakage, time to scheduled visit.
- Ambient/documentation: note throughput, downstream coding, handoff quality, review burden.
- Interoperability: FHIR/API dependency, payload quality, trading-partner readiness, audit trail.

## Obsidian Note

Goal: save the story as reusable intelligence.

Template:

```markdown
---
type: digest-story
date: YYYY-MM-DD
source: [source]
confidence: [High/Medium/Low]
workflow: [workflow wedge]
tags:
  - healthcare-ai
  - workflow-intel
  - [workflow-tag]
---

# [Story Title]

Source: [link]

## What Happened
[one-sentence summary]

## Why It Matters
[operator implication]

## Hard Signal
[deployment, regulatory change, metric, reimbursement effect, integration change, or "none yet"]

## Reuse
- LinkedIn angle: [one POV]
- Outreach opener: [one question]
- Interview point: [one product/operator lesson]

## Follow-Up
- [what proof would upgrade/downgrade this story]
```

Rules:

- Store low-confidence or watchlist-only stories with `Hard Signal: none yet`.
- Link the note to an existing thesis if the story supports, weakens, or complicates it.
- Add a follow-up trigger so stale hype does not become durable belief.

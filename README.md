# Daily AI Digest

Daily AI Digest v2 is now a compact operator cockpit for tracking healthcare AI signal, not just a better newsletter.

It still runs on the existing once-per-day pipeline, but the output is now driven by a structured story layer that clusters related items, suppresses duplicates, scores source reliability, compares against yesterday, tracks saved theses, and saves a reusable operator brief artifact alongside the email.

---

## What it does

### Ingestion
- **GitHub trending repositories:** (AI / agents / RAG / healthcare-relevant)
- **Healthcare news:** via RSS feeds
- **FDA enforcement + recall data:** via openFDA

### Processing
- **LLM-based summarization:** (2-sentence summaries)
- **Canonical normalized item layer:** item metadata, tags, buckets, reliability, thesis links, and watchlist matches
- **Topic clustering + duplicate suppression:** one story card can hold multiple supporting items/sources
- **Action-oriented "Why it matters" insights:** more workflow-specific and less templated
- **Weighted personalization scoring:** career, build, content, regulatory, side-hustle, timeliness, novelty
- **Cross-day memory:** prior stories, thesis evidence, market-map pulse, watchlist hits, top picks, and quality history
- **What changed since yesterday:** new, escalating, repeated-but-stronger, and fading stories
- **Source reliability scoring:** explicit High / Medium / Low with editable policy rules
- **Saved thesis tracking:** standing theses mapped to daily supporting / weakening / complicating evidence
- **Market map pulse:** bucketed heat across durable market categories
- **Digest quality evals:** novelty, source quality, duplication, objective separation, thesis coverage, signal-to-noise
- **Digest Analyst Agent layer:** optional in-process OpenAI Agents SDK judgment pass with safe fallback
- **Cross-source synthesis:** top picks, Top Insight, and compact operator moves

### Output
- Clean HTML digest
- Structured `latest_operator_brief.json`
- Local `latest_operator_cockpit.html`
- Email delivery
- Daily automated run via **GitHub Actions**
- Local artifacts saved (`latest_digest.html`, `latest_operator_brief.json`, `latest_operator_cockpit.html`)
- Duplicate-send protection for same-day reruns
- File-based digest memory in `data/state/` to avoid recycling the same stories and track recurring themes without adding infrastructure

---

## Operator Brief sections

The email and local cockpit are now built from the same structured brief and aim to answer:

- What actually changed since yesterday?
- Which themes are strengthening or weakening?
- Which saved theses got evidence today?
- Which watched repos or market areas moved?
- Which items are real signal vs duplicated noise?
- What deserves attention for career, build, content, and market positioning?

Key rendered sections:

- `What changed since yesterday`
- `Top picks by objective`
- `Thesis tracker`
- `Market map pulse`
- `Watched repos`
- `Operator story board`
- `Operator moves`
- `Digest quality`

---

## Editable config files

These are plain JSON so you can tune the system without code changes:

- `data/source_policies.json`: source/domain reliability rules
- `data/theses.json`: saved theses and matching keywords
- `data/market_map.json`: market taxonomy / bucket rules
- `data/github_watchlist.json`: repos, orgs, and topics to watch

---

## Memory and artifacts

Runtime state still lives in `data/state/` and now stores:

- per-item history for novelty / repeat scoring
- daily brief history for story-level delta comparison
- thesis evidence history
- market intensity history
- watchlist hits
- quality eval history
- prior top picks

Generated artifacts:

- `latest_digest.html`: email-ready digest
- `latest_operator_brief.json`: canonical operator brief artifact
- `latest_operator_cockpit.html`: minimal local cockpit view

---

## Example output

Includes:
- Top Insight (cross-source synthesis)
- Signal prioritization
- Actionable summaries for each item

![Example Output](./assets/example.png)

---

## How to run

### 1. Set environment variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_key_here
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
TO_EMAIL=recipient@email.com
GITHUB_TOKEN=your_token_here (optional)
LOCAL_TIMEZONE=America/Los_Angeles
DIGEST_ANALYST_AGENT_ENABLED=true
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the pipeline

```bash
python main.py
```

Safe local dry run:

```bash
./.venv/bin/python main.py --dry-run
```

`--dry-run` still fetches and renders, but it does not send email and it does not update send/memory state. It writes:

- `latest_operator_brief.json`
- `latest_operator_cockpit.html`
- `latest_digest.html`

State is stored in `data/state/digest_state.json` so the app can:
- skip a second send if the job runs again on the same local day
- prefer items that were not already sent in recent digests

Digest memory is stored in `data/state/digest_memory.json` so the app can:
- track recurring themes and entities
- compare today against yesterday at the story level
- preserve thesis evidence, market pulse, watchlist hits, and quality history
- accumulate lightweight historical context without adding a database

---

## Verify

Run the test suite:

```bash
./.venv/bin/python -m unittest discover -s tests
```

Syntax check the pipeline modules:

```bash
./.venv/bin/python -m py_compile main.py operator_brief.py formatter.py memory.py data.py config.py agent_brief.py scoring.py summarize.py state.py emailer.py
```

---

## Purpose

Built as a personal intelligence system to:
- Track high-signal developments in healthcare AI.
- Prioritize what actually matters for product decisions.
- Reduce noise from generic AI/news feeds.
- Maintain cross-day memory so the digest behaves like an operator console.

---

## Key Features

- Multi-source data ingestion
- Personalized scoring layer with centralized weights in `config.py`
- Story clustering and duplicate suppression
- Explicit source reliability scoring
- Saved thesis tracker
- Market map pulse
- What-changed delta layer
- Watchlist-aware repo surfacing
- Internal digest quality evals
- LLM-based summarization + synthesis
- Lightweight JSON memory for repeat detection and theme tracking
- Fully automated daily delivery via GitHub Actions

---

## Why this matters

Healthcare AI is moving from experimentation into real workflows. This project is meant to help surface signal over noise, with an emphasis on product relevance, operational utility, and regulatory awareness.

---

## Tech Stack

- **Python**
- **OpenAI API:** (LLM summarization + synthesis)
- **GitHub REST API**
- **RSS feeds:** (healthcare news)
- **openFDA API:** (regulatory data)
- **GitHub Actions:** (daily scheduling)

---

## Notes

- `.env` is excluded from version control.
- Logs are saved locally in `log.txt` and `error.txt`.
- `data/state/` is intentionally gitignored and cached by the workflow so runtime state can persist without adding new infrastructure.
- The Digest Analyst Agent uses the same `OPENAI_API_KEY`; disable it with `DIGEST_ANALYST_AGENT_ENABLED=false` if needed.
- Designed for extensibility (add new sources, filters, story rules, or scoring logic easily).

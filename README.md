# Daily AI Digest

Personal healthcare AI intelligence automation for signal monitoring and prioritization.

It pulls signals from GitHub, healthcare news, and FDA/CMS/ONC regulatory data, then uses LLMs plus lightweight local memory to turn them into a concise daily briefing with summaries, personalized scoring, and an operator-focused top insight.

---

## 🚀 What it does

### Ingestion
- **GitHub trending repositories:** (AI / agents / RAG / healthcare-relevant)
- **Healthcare news:** via RSS feeds
- **FDA enforcement + recall data:** via openFDA

### Processing
- **LLM-based summarization:** (2-sentence summaries)
- **Action-oriented "Why it matters" insights**
- **Weighted personalization scoring:** career, build, content, regulatory, side-hustle, timeliness, novelty
- **Repeat/theme awareness:** lightweight memory influences ranking over time
- **Cross-source synthesis:** top picks, Top Insight, and compact operator moves

### Output
- Clean HTML digest
- Email delivery
- Daily automated run via **GitHub Actions**
- Local artifact saved (`latest_digest.html`)
- Duplicate-send protection for same-day reruns
- File-based digest memory in `data/state/` to avoid recycling the same stories and track recurring themes

---

## 🧠 Example Output

Includes:
- Top Insight (cross-source synthesis)
- Signal prioritization
- Actionable summaries for each item

![Example Output](./assets/example.png)

---

## 🛠️ How to run

### 1. Set environment variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_key_here
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
TO_EMAIL=recipient@email.com
GITHUB_TOKEN=your_token_here (optional)
LOCAL_TIMEZONE=America/Los_Angeles
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

State is stored in `data/state/digest_state.json` so the app can:
- skip a second send if the job runs again on the same local day
- prefer items that were not already sent in recent digests

Digest memory is stored in `data/state/digest_memory.json` so the app can:
- track recurring themes and entities
- score novelty and repeat signal
- accumulate lightweight historical context without adding a database

---

## 🎯 Purpose

Built as a personal intelligence system to:
- Track high-signal developments in healthcare AI.
- Prioritize what actually matters for product decisions.
- Reduce noise from generic AI/news feeds.

---

## 📌 Key Features

- Multi-source data ingestion
- Personalized scoring layer with centralized weights in `config.py`
- LLM-based summarization + synthesis
- Lightweight JSON memory for repeat detection and theme tracking
- Fully automated daily delivery via GitHub Actions

---

## 🧭 Why this matters

Healthcare AI is moving from experimentation into real workflows. This project is meant to help surface signal over noise, with an emphasis on product relevance, operational utility, and regulatory awareness.

---

## ⚙️ Tech Stack

- **Python**
- **OpenAI API:** (LLM summarization + synthesis)
- **GitHub REST API**
- **RSS feeds:** (healthcare news)
- **openFDA API:** (regulatory data)
- **launchd:** (macOS scheduling)

---

## 📎 Notes

- `.env` is excluded from version control.
- Logs are saved locally in `log.txt` and `error.txt`.
- `data/state/` is intentionally gitignored and cached by the workflow so runtime state can persist without adding new infrastructure.
- Designed for extensibility (add new sources, filters, or scoring logic easily).

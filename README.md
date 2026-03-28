# Daily AI Digest

Personal healthcare AI intelligence automation for signal monitoring and prioritization.

It pulls signals from GitHub, healthcare news, and FDA regulatory data, then uses LLMs to turn them into a concise daily briefing with summaries, priority scoring, and a synthesized top insight.

---

## 🚀 What it does

### Ingestion
- **GitHub trending repositories:** (AI / agents / RAG / healthcare-relevant)
- **Healthcare news:** via RSS feeds
- **FDA enforcement + recall data:** via openFDA

### Processing
- **LLM-based summarization:** (2-sentence summaries)
- **Action-oriented "Why it matters" insights**
- **Signal scoring:** (HIGH / MEDIUM / LOW)
- **Cross-source synthesis:** → Top Insight

### Output
- Clean HTML digest
- Email delivery
- Daily automated run (7:00 AM via `launchd`)
- Local artifact saved (`latest_digest.html`)
- Duplicate-send protection for same-day reruns
- Item history to avoid recycling the same stories and repos

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

---

## 🎯 Purpose

Built as a personal intelligence system to:
- Track high-signal developments in healthcare AI.
- Prioritize what actually matters for product decisions.
- Reduce noise from generic AI/news feeds.

---

## 📌 Key Features

- Multi-source data ingestion
- LLM-based summarization + synthesis
- Signal prioritization layer
- Fully automated daily delivery
- Local scheduling with `launchd`

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
- If you use `launchd`, disable the scheduled GitHub Action or vice versa so you only have one scheduler.
- Designed for extensibility (add new sources, filters, or scoring logic easily).

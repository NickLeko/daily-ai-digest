# Daily AI Digest

Automated daily intelligence system for healthcare AI product managers.

Ingests real-world signals from GitHub, healthcare news, and FDA regulatory data, then uses LLMs to generate a prioritized, actionable daily briefing with signal scoring and a synthesized top insight.

---

## 🚀 What it does

### Ingestion
- GitHub trending repositories (AI / agents / RAG / healthcare-relevant)
- Healthcare news via RSS feeds
- FDA enforcement + recall data via openFDA

### Processing
- LLM-based summarization (2-sentence summaries)
- Action-oriented "Why it matters" insights
- Signal scoring (HIGH / MEDIUM / LOW)
- Cross-source synthesis → Top Insight

### Output
- Clean HTML digest
- Email delivery
- Daily automated run (7:00 AM via `launchd`)
- Local artifact saved (`latest_digest.html`)

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

    OPENAI_API_KEY=
    GMAIL_ADDRESS=
    GMAIL_APP_PASSWORD=
    TO_EMAIL=
    GITHUB_TOKEN= (optional)

---

### 2. Install dependencies

```bash
pip install -r requirements.txt

### 3. Run the pipeline

```bash
python main.py

## ⚙️ Tech Stack

- Python
- OpenAI API (LLM summarization + synthesis)
- GitHub REST API
- RSS feeds (healthcare news)
- openFDA API (regulatory data)
- launchd (MacOS scheduling)

## 🎯 Purpose

Built as a personal intelligence system to:
- Track high-signal developments in healthcare AI
- Prioritize what actually matters for product decisions
- Reduce noise from generic AI/news feeds

## 📌 Key Features

- Multi-source data ingestion
- LLM-based summarization + synthesis
- Signal prioritization layer
- Fully automated daily delivery
- Production-style scheduling (`launchd`)

---

## 🧭 Why this matters

Healthcare AI is shifting from experimentation to operational deployment.

This system focuses on:
- reliability
- workflow ROI
- regulatory awareness

Not just model capability.

---

## 📎 Notes

- `.env` is excluded from version control
- Logs saved locally (`log.txt`, `error.txt`)
- Designed for extensibility (new sources, filters, scoring)

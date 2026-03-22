# Daily AI Digest

Automated daily intelligence system for healthcare AI product managers.

Pulls real-time signals from GitHub, healthcare news RSS feeds, and openFDA enforcement data, then uses LLMs to summarize, prioritize, and email a daily briefing with a top insight and signal scoring.

## How to run

1. Create a `.env` file with:
   - `OPENAI_API_KEY`
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `TO_EMAIL`
   - `GITHUB_TOKEN` (optional)
2. Install dependencies
3. Run:

```bash

python main.py
## What it does

- Pulls real data from:
  - GitHub (repos)
  - Healthcare news (RSS)
  - FDA regulatory data (openFDA)

- Uses LLMs to:
  - Summarize
  - Prioritize signal
  - Generate top insight

- Outputs:
  - HTML digest
  - Email delivery
  - Daily scheduled run (7:00 AM)

## Stack

- Python
- OpenAI API
- GitHub API
- RSS feeds
- openFDA API
- launchd (Mac scheduling)

## Example Output

Includes:
- Top insight
- Signal scoring (HIGH / MEDIUM / LOW)
- Action-oriented summaries

## Purpose

Built as a personal intelligence system for healthcare AI product management.

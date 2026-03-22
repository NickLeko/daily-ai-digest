# Daily AI Digest

Automated daily intelligence system for healthcare AI.

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

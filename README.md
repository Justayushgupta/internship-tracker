# Internship Tracker Bot

Automatically checks 30+ top companies' career pages every 6 hours and
notifies you (Telegram + Email) the moment a **new** internship listing
appears. Runs for free on GitHub Actions — no laptop needed.

## How it works

- `companies.json` — the list of companies to track (edit this to add/remove)
- `scraper.py` — checks each company, compares against `state.json` (last known listings), finds what's new
- `notifier.py` — sends Telegram + Email alerts for new listings
- `.github/workflows/track.yml` — the cron job that runs everything every 6 hours on GitHub's free servers

Companies on **Greenhouse** (Razorpay, Postman, Databricks, Robinhood, Notion)
and **Lever** (Netflix, Cohere) use official public JSON APIs — these are
100% reliable.

Companies marked `"type": "generic"` (Google, Microsoft, TCS, Infosys, Deloitte, etc.)
are scraped from their career page HTML by looking for links containing
"intern"/"trainee". This works well for many sites but **some career portals
are JavaScript-rendered** (React/Angular SPAs) and won't return results with
simple scraping — you'll need to check those specific companies manually at
first and tell me which ones return nothing, so I can adjust the approach
(e.g. switch that one company to a headless-browser fetch).

## Setup (one-time, ~15 minutes)

### 1. Create a GitHub repo
Push this folder to a **public** GitHub repo (public = unlimited free
GitHub Actions minutes). Private repos also work but have a monthly minute cap.

```bash
cd internship-tracker
git init
git add .
git commit -m "Initial internship tracker"
git remote add origin https://github.com/Justayushgupta/internship-tracker.git
git branch -M main
git push -u origin main
```

### 2. Create a Telegram bot (2 minutes)
1. Open Telegram, search for **@BotFather**
2. Send `/newbot`, follow prompts, name it anything (e.g. `InternshipAlertsBot`)
3. BotFather gives you a **token** like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxx` — save it
4. Send any message to your new bot (e.g. "hi") so it can message you back
5. Get your chat ID: open this URL in browser (replace TOKEN):
   `https://api.telegram.org/botTOKEN/getUpdates`
   Look for `"chat":{"id": 123456789 ...}` — that number is your `TELEGRAM_CHAT_ID`

### 3. Create a Gmail App Password (2 minutes)
1. Go to https://myaccount.google.com/apppasswords
2. Generate an app password for "Mail"
3. Save the 16-character password

### 4. Add secrets to your GitHub repo
Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add these 5 secrets:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char app password |
| `TO_EMAIL` | email address to receive alerts (can be same Gmail) |

### 5. Enable Actions
Go to the **Actions** tab in your repo → enable workflows if prompted.
You can also click **Run workflow** manually to test it immediately instead
of waiting 6 hours.

## Important: first run

On the very first run, `state.json` is empty, so **every** existing listing
will look "new" and you'll get one big notification — that's expected
(it's building the baseline). After that, you'll only get pinged for
genuinely new postings.

## Adding more companies

Edit `companies.json`. For a company on Greenhouse, find its board token
from its careers URL (e.g. `job-boards.greenhouse.io/COMPANYNAME` → token is
`COMPANYNAME`). For Lever, it's `jobs.lever.co/COMPANYNAME`. For anything
else, use `"type": "generic"` with the direct careers/jobs-search URL.

## Limitations to be upfront about

- Some big-company portals (Workday, custom SPAs) render jobs via JavaScript
  after page load — plain `requests` won't see them. If a "generic" company
  keeps returning zero new listings even when you know something was posted,
  tell me and I'll switch it to a Playwright-based fetch (works for any site,
  just needs a slightly heavier setup).
- This tracks new postings on the specific URLs configured — if a company
  changes its career page structure/URL, that entry will need updating.

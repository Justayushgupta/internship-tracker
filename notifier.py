"""
Sends notifications for new listings found by scraper.py (reads new_listings.json).

Requires these environment variables (set as GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  GMAIL_ADDRESS
  GMAIL_APP_PASSWORD
  TO_EMAIL

IMPORTANT: this script always exits with code 0 (success), even if sending
a notification fails. That way a bad/expired Gmail password or a Telegram
hiccup can never block the "Commit updated state" step that follows - if it
did, state.json would never get saved and the same listings would be
reported as "new" forever on every run.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import requests

NEW_LISTINGS_FILE = Path("new_listings.json")


def format_message(listings):
    lines = [f"🎯 {len(listings)} New Internship Listing(s) Found!\n"]
    for item in listings:
        lines.append(f"🏢 {item['company']}")
        lines.append(f"   {item['title']}")
        if item.get("location"):
            lines.append(f"   📍 {item['location']}")
        if item.get("url"):
            lines.append(f"   🔗 {item['url']}")
        lines.append("")
    return "\n".join(lines)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing, skipping Telegram notification.")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for i in range(0, len(message), 4000):
            chunk = message[i:i + 4000]
            r = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=20)
            if r.status_code != 200:
                print(f"[warn] Telegram send failed: {r.text}")
    except Exception as e:
        print(f"[warn] Telegram notification failed, continuing anyway: {e}")


def send_email(subject, body):
    gmail_addr = os.environ.get("GMAIL_ADDRESS")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    to_email = os.environ.get("TO_EMAIL")
    if not gmail_addr or not gmail_pass or not to_email:
        print("Email credentials missing, skipping email notification.")
        return

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = gmail_addr
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(gmail_addr, gmail_pass)
            server.sendmail(gmail_addr, [to_email], msg.as_string())
        print("Email sent successfully.")
    except Exception as e:
        # Never let an email failure (e.g. expired app password) crash the
        # workflow - that would block the state.json commit step and cause
        # the same listings to be re-reported as "new" on every future run.
        print(f"[warn] Email notification failed, continuing anyway: {e}")
        print("[warn] Check that GMAIL_APP_PASSWORD secret is still valid "
              "(regenerate at myaccount.google.com/apppasswords if needed).")


def main():
    if not NEW_LISTINGS_FILE.exists():
        print("No new_listings.json found, nothing to notify.")
        return

    listings = json.loads(NEW_LISTINGS_FILE.read_text(encoding="utf-8"))
    if not listings:
        print("No new listings, skipping notifications.")
        return

    message = format_message(listings)
    print(message)

    send_telegram(message)
    send_email(f"🎯 {len(listings)} New Internship Listing(s)", message)


if __name__ == "__main__":
    main()
    # Always exit 0 - notification failures should never block the
    # downstream "Commit updated state" step.

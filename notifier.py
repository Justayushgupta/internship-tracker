"""
Sends notifications for new listings found by scraper.py (reads new_listings.json).

Requires these environment variables (set as GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  GMAIL_ADDRESS
  GMAIL_APP_PASSWORD
  TO_EMAIL
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
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram messages max ~4096 chars; split if needed
    for i in range(0, len(message), 4000):
        chunk = message[i:i + 4000]
        r = requests.post(url, data={"chat_id": chat_id, "text": chunk})
        if r.status_code != 200:
            print(f"Telegram send failed: {r.text}")


def send_email(subject, body):
    gmail_addr = os.environ.get("GMAIL_ADDRESS")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    to_email = os.environ.get("TO_EMAIL")
    if not gmail_addr or not gmail_pass or not to_email:
        print("Email credentials missing, skipping email notification.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_addr
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_addr, gmail_pass)
        server.sendmail(gmail_addr, [to_email], msg.as_string())


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

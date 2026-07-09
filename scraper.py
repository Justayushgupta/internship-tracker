"""
Internship Tracker - core scraper.

Checks each company in companies.json for NEW internship listings
by comparing against the last saved state (state.json).

Three company "types":
  - greenhouse : uses the public Greenhouse Job Board API (very reliable, JSON)
  - lever      : uses the public Lever Postings API (very reliable, JSON)
  - generic    : fetches the career page HTML and looks for links whose
                 text matches internship keywords (best-effort, may need
                 tuning per-site since many career portals are JS-rendered)

Run: python scraper.py
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

COMPANIES_FILE = Path("companies.json")
STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

INTERN_PATTERN = re.compile(r"intern|internship|trainee", re.IGNORECASE)


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_greenhouse(company):
    token = company["board_token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    listings = {}
    for job in jobs:
        title = job.get("title", "")
        if INTERN_PATTERN.search(title):
            listings[str(job["id"])] = {
                "title": title,
                "url": job.get("absolute_url", ""),
                "location": (job.get("location") or {}).get("name", ""),
            }
    return listings


def fetch_lever(company):
    token = company["board_token"]
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    jobs = r.json()
    listings = {}
    for job in jobs:
        title = job.get("text", "")
        if INTERN_PATTERN.search(title):
            job_id = job.get("id", title)
            listings[job_id] = {
                "title": title,
                "url": job.get("hostedUrl", ""),
                "location": (job.get("categories") or {}).get("location", ""),
            }
    return listings


def fetch_generic(company):
    url = company["url"]
    keywords = company.get("keywords", ["intern"])
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    listings = {}
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if not text:
            continue
        if any(kw.lower() in text.lower() for kw in keywords):
            href = a.get("href", "")
            if href.startswith("/"):
                # make relative links absolute
                from urllib.parse import urljoin
                href = urljoin(url, href)
            key = href or text
            listings[key] = {"title": text, "url": href, "location": ""}
    return listings


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "generic": fetch_generic,
}


def check_company(company, old_state):
    ctype = company["type"]
    name = company["name"]
    fetcher = FETCHERS.get(ctype)
    if not fetcher:
        print(f"[skip] {name}: unknown type {ctype}")
        return {}, []

    try:
        current = fetcher(company)
    except Exception as e:
        print(f"[error] {name}: {e}")
        # keep old state untouched on failure, no new listings reported
        return old_state.get(name, {}), []

    previous = old_state.get(name, {})
    new_keys = set(current.keys()) - set(previous.keys())
    new_listings = [current[k] for k in new_keys]

    return current, [{"company": name, **listing} for listing in new_listings]


def main():
    companies = load_json(COMPANIES_FILE, [])
    state = load_json(STATE_FILE, {})

    all_new = []
    new_state = {}

    for company in companies:
        current, new_listings = check_company(company, state)
        new_state[company["name"]] = current
        all_new.extend(new_listings)
        time.sleep(1)  # be polite to servers

    save_json(STATE_FILE, new_state)

    if all_new:
        print(f"Found {len(all_new)} new listing(s).")
        Path("new_listings.json").write_text(
            json.dumps(all_new, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    else:
        print("No new listings this run.")
        Path("new_listings.json").write_text("[]", encoding="utf-8")

    return all_new


if __name__ == "__main__":
    main()

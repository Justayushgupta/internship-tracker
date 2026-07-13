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

INTERN_PATTERN = re.compile(r"\b(intern|internship|interns|trainee)\b", re.IGNORECASE)

# Titles containing these are NOT suitable for a 3rd-year undergrad B.Tech
# student (they require a PhD, Master's, or years of prior work experience).
# Location does NOT matter here - international roles are fine.
DISQUALIFYING_TERMS = re.compile(
    r"\bphd\b|\bph\.d\b|doctoral|\bpostdoc\b|"
    r"\bmaster'?s\b|\bmba\b|"
    r"\bsenior\b|\bstaff\b|\bprincipal\b|\blead\b|\barchitect\b|"
    r"\b\d+\+?\s*years?\b",  # e.g. "5+ years", "3 years experience"
    re.IGNORECASE,
)


def looks_like_internship(title: str) -> bool:
    """True only if title contains a real internship keyword. The \\b word
    boundaries already correctly skip 'Internals' and 'International' since
    'intern' isn't a whole word inside those - no extra exclusion needed."""
    return bool(INTERN_PATTERN.search(title))


def is_eligible_for_undergrad(title: str) -> bool:
    """Filters out roles that need a PhD/Master's/senior-level experience -
    not a fit for a 3rd-year B.Tech student. Location doesn't matter
    (international is fine); only the seniority/degree requirement does."""
    return not DISQUALIFYING_TERMS.search(title)


# Only these fields count as relevant - Software/Tech/DevOps/Cloud/Data/etc.
# Titles with none of these words (e.g. "Marketing Associate Intern",
# "HR Intern", "Sales Intern") are filtered out even though they ARE
# genuine internships, because they don't match a CS/DevOps/Cloud profile.
TECH_ROLE_PATTERN = re.compile(
    r"\bsoftware\b|\bdeveloper\b|\bengineer(ing)?\b|\bdevops\b|\bcloud\b|"
    r"\bback[\s-]?end\b|\bfront[\s-]?end\b|\bfull[\s-]?stack\b|"
    r"\bdata\s*(science|scientist|engineer|analyst|analytics)?\b|"
    r"\bmachine\s*learning\b|\bml\b|\bai\b|\bartificial\s*intelligence\b|"
    r"\bcyber\s*security\b|\bsecurity\s*engineer\b|"
    r"\bsre\b|\bsite\s*reliability\b|\binfrastructure\b|\bsystems?\s*engineer\b|"
    r"\bnetwork\s*engineer\b|\bqa\b|\bquality\s*assurance\b|\btest(ing)?\s*engineer\b|"
    r"\bsde\b|\bprogrammer\b|\bcomputer\s*science\b|\btechnical\b|"
    r"\bproduct\s*engineering\b|\bit\s*(support|engineer|analyst)\b|"
    r"\bkubernetes\b|\bdocker\b|\blinux\b|\bpython\b|\bjava\b|\baws\b|\bgcp\b|\bazure\b",
    re.IGNORECASE,
)


def is_tech_role(title: str) -> bool:
    """True only if the title is a Software/Tech/DevOps/Cloud/Data-type role.
    Filters out genuine but non-technical internships (Marketing, Sales, HR,
    Finance, Business roles) that would otherwise pass the level check."""
    return bool(TECH_ROLE_PATTERN.search(title))


def is_relevant(title: str) -> bool:
    return (
        looks_like_internship(title)
        and is_eligible_for_undergrad(title)
        and is_tech_role(title)
    )


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
        if is_relevant(title):
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
        if is_relevant(title):
            job_id = job.get("id", title)
            listings[job_id] = {
                "title": title,
                "url": job.get("hostedUrl", ""),
                "location": (job.get("categories") or {}).get("location", ""),
            }
    return listings


def fetch_ashby(company):
    """Ashby (used by Notion, Linear, Vercel, and many modern startups) has a
    public read-only Job Board API - no auth, no headless browser needed."""
    token = company["board_token"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()
    jobs = data.get("jobs", [])
    listings = {}
    for job in jobs:
        title = job.get("title", "")
        if is_relevant(title):
            job_id = job.get("id", title)
            listings[job_id] = {
                "title": title,
                "url": job.get("jobUrl", ""),
                "location": job.get("locationName", ""),
            }
    return listings


def fetch_workday(company):
    """Many large enterprises (NVIDIA, Qualcomm, Oracle, IBM, Cisco, etc.) use
    Workday. The public careers page is JS-rendered, but the underlying data
    comes from a JSON API (/wday/cxs/{tenant}/{site}/jobs) that we can call
    directly with a POST request - no headless browser needed."""
    tenant = company["tenant"]
    site = company["site"]
    hostname = company.get("hostname")  # e.g. "nvidia.wd5.myworkdayjobs.com"
    if not hostname:
        hostname = f"{tenant}.myworkdayjobs.com"
    api_url = f"https://{hostname}/wday/cxs/{tenant}/{site}/jobs"

    listings = {}
    offset = 0
    limit = 20
    for _ in range(5):  # cap pages to stay fast/safe
        body = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "",
        }
        r = requests.post(api_url, headers={**HEADERS, "Content-Type": "application/json"},
                           json=body, timeout=20)
        r.raise_for_status()
        data = r.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for job in postings:
            title = job.get("title", "")
            if is_relevant(title):
                path = job.get("externalPath", "")
                job_key = path or title
                listings[job_key] = {
                    "title": title,
                    "url": f"https://{hostname}{path}" if path else "",
                    "location": job.get("locationsText", ""),
                }
        offset += limit
        if offset >= data.get("total", 0):
            break
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
        extra_keyword_match = any(
            kw.lower() in text.lower() for kw in keywords if kw.lower() not in ("intern",)
        )
        if (is_relevant(text)) or (extra_keyword_match and is_eligible_for_undergrad(text)):
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
    "ashby": fetch_ashby,
    "workday": fetch_workday,
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

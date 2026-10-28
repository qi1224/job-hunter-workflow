#!/usr/bin/env python3
"""
JSearch Job Scraper - Searches jobs via JSearch API on RapidAPI.

JSearch aggregates Google Jobs data, which includes postings from LinkedIn,
Indeed, Glassdoor, and hundreds of company career pages — all in one call.

Optional provider. Check your own RapidAPI plan for current prices and quotas.

Usage:
    python jsearch_scraper.py --config ~/.config/job-hunter/config.json
    python jsearch_scraper.py --keywords "data scientist" --location "Boston"
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from common.config import load_config
from common.dedup import deduplicate_jobs, filter_seen_jobs, generate_job_id

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"

# Map config time_range to JSearch date_posted parameter
TIME_RANGE_TO_DATE_POSTED = {
    "day": "today",
    "week": "week",
    "month": "month",
    "year": "all",
}


def _format_salary(job: dict) -> str:
    """Build a salary string from JSearch job fields."""
    try:
        min_s = job.get("job_min_salary")
        max_s = job.get("job_max_salary")
        period = (job.get("job_salary_period") or "").lower()
        currency = job.get("job_salary_currency") or "USD"

        period_label = {"year": "yr", "hour": "hr", "month": "mo"}.get(period, period)

        if min_s and max_s:
            return f"${int(min_s):,}–${int(max_s):,} {period_label}".strip()
        elif min_s:
            return f"${int(min_s):,}+ {period_label}".strip()
        elif max_s:
            return f"up to ${int(max_s):,} {period_label}".strip()
    except Exception:
        pass
    return ""


def _location(job: dict) -> str:
    """Build location string from city/state/country fields."""
    parts = [
        job.get("job_city") or "",
        job.get("job_state") or "",
    ]
    loc = ", ".join(p for p in parts if p)
    if not loc:
        loc = job.get("job_country") or ""
    return loc


def normalize_jsearch_result(job: dict) -> dict:
    """Normalize a JSearch API result to the common job dict format."""
    title = job.get("job_title") or ""
    company = job.get("employer_name") or ""
    description = job.get("job_description") or ""
    url = job.get("job_apply_link") or job.get("job_google_link") or ""
    posted_date = job.get("job_posted_at_datetime_utc") or ""
    remote = bool(job.get("job_is_remote")) or "remote" in (title + " " + description).lower()
    employment_type = (job.get("job_employment_type") or "").lower().replace("_", " ")

    # Publisher tells us where it came from (e.g. "LinkedIn", "Indeed")
    source = (job.get("job_publisher") or "jsearch").lower()

    result = {
        "title": title,
        "company": company,
        "location": _location(job),
        "description": description,
        "url": url,
        "posted_date": posted_date,
        "salary": _format_salary(job),
        "employment_type": employment_type,
        "experience_level": "",
        "remote": remote,
        "source": source,
        "scraped_at": datetime.now().isoformat(),
    }
    result["id"] = generate_job_id(result)
    return result


class QuotaExceeded(Exception):
    """JSearch monthly quota used up; every further call would also fail."""


def search_jobs(
    api_key: str,
    query: str,
    num_results: int = 10,
    date_posted: str = "week",
    remote_only: bool = False,
) -> list[dict]:
    """Call JSearch API for a single query; returns raw job dicts."""
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }
    params = {
        "query": query,
        "page": "1",
        "num_pages": "1",
        "date_posted": date_posted,
    }
    if remote_only:
        params["remote_jobs_only"] = "true"

    # JSearch returns 10 results per page; request extra pages if more needed
    all_data: list[dict] = []
    pages_needed = max(1, (num_results + 9) // 10)

    with httpx.Client(timeout=30) as client:
        for page in range(1, pages_needed + 1):
            params["page"] = str(page)
            try:
                resp = client.get(JSEARCH_URL, headers=headers, params=params)
                if resp.status_code == 429 and "quota" in resp.text.lower():
                    raise QuotaExceeded(resp.text[:200])
                if resp.status_code != 200:
                    raise RuntimeError(f'JSearch HTTP {resp.status_code}')
                data = resp.json().get("data") or []
                all_data.extend(data)
                if len(data) < 10:
                    break  # no more results
            except QuotaExceeded:
                raise
            except Exception as e:
                raise RuntimeError('JSearch request failed; successful-run state unchanged') from e

    return all_data[:num_results]


def scrape_jobs(
    config: dict,
    keywords: list[str] | None = None,
    location: str | None = None,
    skip_seen: bool = True,
) -> list[dict]:
    """Search jobs using JSearch for each keyword, aggregate and deduplicate."""
    api_key = config.get("jsearch_api_key", "")
    if not api_key:
        print("Error: jsearch_api_key not configured", file=sys.stderr)
        print("Add it to ~/.config/job-hunter/config.json or run setup_config.py",
              file=sys.stderr)
        sys.exit(1)

    search_config = config.get("search", {})
    # Separate, shorter keyword list for JSearch: every keyword costs one API call per country
    keywords_list = keywords or search_config.get("jsearch_keywords") or search_config.get("keywords", [])
    loc = location or search_config.get("location", "")
    time_range = search_config.get("time_range", "week")
    date_posted = TIME_RANGE_TO_DATE_POSTED.get(time_range, "week")
    num_results = search_config.get("max_results_per_query", 10)
    remote = bool(search_config.get("remote"))

    # Countries to search: explicit --location override > preferred_countries config > no filter
    if location:
        countries = [location]
    else:
        countries = config.get("preferred_countries", [])

    print(f"Date posted filter: {date_posted} | Results/keyword: {num_results} | Countries: {len(countries) or 'global'}")

    all_jobs = []
    for kw in keywords_list:
        search_targets = countries if countries else [None]
        for country in search_targets:
            query = f"{kw} {country}".strip() if country else kw
            if remote and "remote" not in query.lower():
                query = f"{query} remote"
            print(f"Searching: {query}")
            try:
                raw = search_jobs(api_key, query, num_results, date_posted, remote_only=remote)
            except QuotaExceeded as e:
                # Exit non-zero so the pipeline doesn't record this as a completed JSearch run
                print(f"  JSearch quota exhausted, stopping: {e}", file=sys.stderr)
                sys.exit(2)
            normalized = [normalize_jsearch_result(r) for r in raw]
            all_jobs.extend(normalized)
            print(f"  Found {len(normalized)} postings")

    # Deduplicate across keywords
    all_jobs = deduplicate_jobs(all_jobs)

    # Filter previously seen jobs (HTML tracker takes priority over legacy Obsidian vault)
    if skip_seen:
        html_tracker = config.get("html_tracker")
        obsidian_vault = config.get("obsidian_vault") if not html_tracker else None
        all_jobs = filter_seen_jobs(all_jobs, obsidian_vault, html_tracker)

    # Sort by posted date (newest first)
    all_jobs.sort(key=lambda j: j.get("posted_date", ""), reverse=True)

    print(f"Total: {len(all_jobs)} new jobs after dedup")
    return all_jobs


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Search jobs via JSearch (RapidAPI)")
    parser.add_argument("--config", default="~/.config/job-hunter/config.json")
    parser.add_argument("--keywords", nargs="+")
    parser.add_argument("--location")
    parser.add_argument("--output", "-o")
    parser.add_argument("--include-seen", action="store_true")

    args = parser.parse_args()
    config = load_config(args.config)

    jobs = scrape_jobs(
        config,
        keywords=args.keywords,
        location=args.location,
        skip_seen=not args.include_seen,
    )

    output = json.dumps(jobs, indent=2, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved {len(jobs)} jobs to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""GDiDM Events Scraper — Stage 1: Fetch and clean source pages.

Fetches HTML from configured source URLs, converts to readable text,
and saves per-source text files for Claude Code extraction.

Usage:
    python scraper/scrape.py                  # Fetch all Tier 1 sources
    python scraper/scrape.py --sources CDM    # Fetch specific org(s)
    python scraper/scrape.py --tier 1         # Fetch by tier
    python scraper/scrape.py --dry-run        # Show what would be fetched
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

from extract import html_to_text, save_page_text

SCRAPER_DIR = Path(__file__).parent
SOURCES_FILE = SCRAPER_DIR / "sources.yaml"
PAGES_DIR = SCRAPER_DIR / "pages"
LOG_FILE = SCRAPER_DIR / "scrape_log.json"

USER_AGENT = (
    "DigitalMindsEventsScraper/1.0 "
    "(+https://github.com/Mitchel-Alexander/getting-started-digital-minds)"
)
REQUEST_TIMEOUT = 30
RATE_LIMIT_SECONDS = 1.5


def load_sources(
    path: Path = SOURCES_FILE,
    filter_abbrevs: list[str] | None = None,
    filter_tier: int | None = None,
) -> list[dict]:
    """Load and optionally filter sources from YAML config."""
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])

    if filter_abbrevs:
        abbrevs_upper = {a.upper() for a in filter_abbrevs}
        sources = [s for s in sources if s["abbreviation"].upper() in abbrevs_upper]

    if filter_tier is not None:
        sources = [s for s in sources if s.get("tier") == filter_tier]

    return sources


def fetch_static(url: str) -> str:
    """Fetch a static page via requests."""
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def fetch_dynamic(url: str) -> str:
    """Fetch a JS-rendered page via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            f"Playwright not installed — cannot fetch dynamic page: {url}\n"
            "Install with: pip install playwright && playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, timeout=REQUEST_TIMEOUT * 1000)
        page.wait_for_load_state("networkidle", timeout=REQUEST_TIMEOUT * 1000)
        html = page.content()
        browser.close()
    return html


def fetch_page(url: str, page_type: str) -> str:
    """Fetch a page, dispatching to the appropriate method."""
    if page_type == "dynamic":
        return fetch_dynamic(url)
    return fetch_static(url)


def process_source(source: dict) -> dict:
    """Fetch and clean all URLs for a single source.

    Returns a log entry dict with results.
    """
    name = source["name"]
    abbreviation = source["abbreviation"]
    urls = source.get("urls", [])

    log_entry = {
        "source": name,
        "abbreviation": abbreviation,
        "urls_attempted": len(urls),
        "urls_succeeded": 0,
        "pages_saved": [],
        "errors": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for i, url_config in enumerate(urls):
        url = url_config["url"]
        page_type = url_config.get("page_type", "static")

        # Rate limit between requests (skip before the first)
        if i > 0:
            time.sleep(RATE_LIMIT_SECONDS)

        try:
            print(f"  Fetching: {url} ({page_type})")
            html = fetch_page(url, page_type)
            text = html_to_text(html)
            filepath = save_page_text(text, name, abbreviation, url, str(PAGES_DIR))
            log_entry["urls_succeeded"] += 1
            log_entry["pages_saved"].append(str(filepath))
            print(f"    Saved: {filepath.name} ({len(text)} chars)")
        except Exception as e:
            error_msg = f"{url}: {type(e).__name__}: {e}"
            log_entry["errors"].append(error_msg)
            print(f"    ERROR: {error_msg}", file=sys.stderr)

    return log_entry


def main():
    parser = argparse.ArgumentParser(
        description="GDiDM Events Scraper — fetch and clean source pages"
    )
    parser.add_argument(
        "--sources",
        type=str,
        help="Comma-separated list of source abbreviations to fetch (e.g. CDM,PRISM)",
    )
    parser.add_argument(
        "--tier",
        type=int,
        help="Filter sources by tier (1, 2, or 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without actually fetching",
    )
    args = parser.parse_args()

    filter_abbrevs = None
    if args.sources:
        filter_abbrevs = [s.strip() for s in args.sources.split(",")]

    sources = load_sources(
        filter_abbrevs=filter_abbrevs,
        filter_tier=args.tier,
    )

    if not sources:
        print("No sources matched the given filters.", file=sys.stderr)
        sys.exit(1)

    total_urls = sum(len(s.get("urls", [])) for s in sources)
    print(f"Sources: {len(sources)} orgs, {total_urls} URLs")

    if args.dry_run:
        print("\n[DRY RUN] Would fetch:")
        for source in sources:
            print(f"\n  {source['name']} ({source['abbreviation']})")
            for url_config in source.get("urls", []):
                print(f"    {url_config['url']} ({url_config.get('page_type', 'static')})")
        sys.exit(0)

    # Ensure pages directory exists
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    log_entries = []
    for source in sources:
        print(f"\n[{source['abbreviation']}] {source['name']}")

        # Rate limit between sources
        if log_entries:
            time.sleep(RATE_LIMIT_SECONDS)

        log_entry = process_source(source)
        log_entries.append(log_entry)

    # Write scrape log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2)
    print(f"\nLog written to {LOG_FILE}")

    # Summary
    total_succeeded = sum(e["urls_succeeded"] for e in log_entries)
    total_errors = sum(len(e["errors"]) for e in log_entries)
    print(f"\nDone: {total_succeeded}/{total_urls} URLs fetched, {total_errors} errors")

    if total_errors > 0:
        print("\nErrors:")
        for entry in log_entries:
            for error in entry["errors"]:
                print(f"  [{entry['abbreviation']}] {error}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""GDiDM Events Scraper — Stage 3: Merge scraped events into _data/events.yml.

Reads scraped_events.json, deduplicates against existing events,
maps field names to the site schema, and appends new events.

Usage:
    python scraper/merge.py
    python scraper/merge.py --scraped scraper/scraped_events.json
    python scraper/merge.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from deduplicate import composite_key, deduplicate, normalise_title

SCRAPER_DIR = Path(__file__).parent
REPO_ROOT = SCRAPER_DIR.parent
EVENTS_YAML = REPO_ROOT / "_data" / "events.yml"
SCRAPED_JSON = SCRAPER_DIR / "scraped_events.json"

# Fields in the internal scraper schema that map to different names in the site YAML
FIELD_MAP = {
    "title": "name",
    "start_date": "date_start",
    "end_date": "date_end",
}

# Fields to drop when writing to site YAML
DROP_FIELDS = {"confidence"}


def load_existing_events(path: Path = EVENTS_YAML) -> tuple[list[str], list[dict]]:
    """Load existing events from YAML. Returns (header_lines, events)."""
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extract comment header
    header_lines = []
    for line in lines:
        if line.startswith("#") or line.strip() == "":
            header_lines.append(line)
        else:
            break

    events = yaml.safe_load(content) or []
    return header_lines, events


def load_scraped_events(path: Path = SCRAPED_JSON) -> list[dict]:
    """Load scraped events from JSON."""
    with open(path, encoding="utf-8") as f:
        events = json.load(f)
    return events


def map_to_site_schema(event: dict) -> dict:
    """Map internal scraper field names to site YAML field names."""
    mapped = {}
    for key, value in event.items():
        if key in DROP_FIELDS:
            continue
        new_key = FIELD_MAP.get(key, key)
        mapped[new_key] = value

    # Ensure status is set
    if "status" not in mapped:
        mapped["status"] = "upcoming"

    return mapped


def events_match(new_event: dict, existing_event: dict) -> bool:
    """Check if a scraped event matches an existing event (cross-schema)."""
    # Normalise titles from both schemas
    new_title = normalise_title(
        new_event.get("title") or new_event.get("name") or ""
    )
    existing_title = normalise_title(existing_event.get("name") or "")

    new_org = (new_event.get("organiser") or "").lower().strip()
    existing_org = (existing_event.get("organiser") or "").lower().strip()

    new_date = str(new_event.get("start_date") or new_event.get("date_start") or "")
    existing_date = str(existing_event.get("date_start") or "")

    return (new_title, new_org, new_date) == (existing_title, existing_org, existing_date)


def deduplicate_against_existing(
    new_events: list[dict], existing_events: list[dict]
) -> list[dict]:
    """Remove scraped events that already exist in the site YAML."""
    truly_new = []
    for new_event in new_events:
        if not any(events_match(new_event, existing) for existing in existing_events):
            truly_new.append(new_event)
    return truly_new


def write_events_yaml(
    header_lines: list[str], events: list[dict], path: Path = EVENTS_YAML
) -> None:
    """Write events to YAML, preserving the original comment header."""
    # Define field order for consistent output
    field_order = [
        "name", "url", "organiser", "date_start", "date_end",
        "type", "format", "location", "deadline", "description", "status",
    ]

    lines = list(header_lines)

    for event in events:
        # Write fields in consistent order
        first = True
        for field in field_order:
            if field not in event:
                continue
            value = event[field]
            prefix = "- " if first else "  "
            first = False

            if value is None or value == "":
                lines.append(f"{prefix}{field}:")
            elif isinstance(value, str) and (
                ":" in value or '"' in value or "'" in value or value != value.strip()
            ):
                # Quote strings that contain special YAML characters
                escaped = value.replace('"', '\\"')
                lines.append(f'{prefix}{field}: "{escaped}"')
            elif isinstance(value, str):
                lines.append(f"{prefix}{field}: {value}")
            else:
                lines.append(f"{prefix}{field}: {value}")

        # Write any extra fields not in field_order
        for field, value in event.items():
            if field in field_order:
                continue
            prefix = "  "
            if value is None or value == "":
                lines.append(f"{prefix}{field}:")
            else:
                lines.append(f"{prefix}{field}: {value}")

        lines.append("")  # blank line between events

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Merge scraped events into _data/events.yml"
    )
    parser.add_argument(
        "--scraped",
        type=Path,
        default=SCRAPED_JSON,
        help="Path to scraped_events.json",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=EVENTS_YAML,
        help="Path to _data/events.yml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be added without modifying events.yml",
    )
    args = parser.parse_args()

    if not args.scraped.exists():
        print(f"Error: {args.scraped} not found. Run the extraction step first.", file=sys.stderr)
        sys.exit(1)

    if not args.events.exists():
        print(f"Error: {args.events} not found.", file=sys.stderr)
        sys.exit(1)

    # Load data
    header_lines, existing_events = load_existing_events(args.events)
    scraped_events = load_scraped_events(args.scraped)

    print(f"Existing events: {len(existing_events)}")
    print(f"Scraped events: {len(scraped_events)}")

    # Deduplicate within scraped set
    scraped_events = deduplicate(scraped_events)
    print(f"After internal dedup: {len(scraped_events)}")

    # Deduplicate against existing
    new_events = deduplicate_against_existing(scraped_events, existing_events)
    print(f"Truly new events: {len(new_events)}")

    if not new_events:
        print("\nNo new events to add.")
        return

    # Map to site schema
    mapped_events = [map_to_site_schema(event) for event in new_events]

    # Print summary
    print("\n--- New events ---")
    for event in mapped_events:
        name = event.get("name", "Unknown")
        org = event.get("organiser", "Unknown")
        date = event.get("date_start", "TBD")
        conf = next(
            (e.get("confidence", "?") for e in new_events
             if normalise_title(e.get("title", "")) == normalise_title(name)),
            "?"
        )
        print(f"  [{conf}] {name} — {org} ({date})")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    # Merge and write
    combined = existing_events + mapped_events
    write_events_yaml(header_lines, combined, args.events)
    print(f"\nWritten {len(combined)} events to {args.events}")


if __name__ == "__main__":
    main()

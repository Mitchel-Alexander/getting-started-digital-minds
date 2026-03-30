"""Deduplication logic for the GDiDM events scraper.

Deduplicates events by composite key (normalised title + organiser + start_date),
with a fuzzy matching pass for near-duplicate titles.
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.75

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def composite_key(event: dict) -> tuple:
    """Create a dedup key from (normalised_title, organiser_lower, start_date)."""
    title = normalise_title(event.get("title") or event.get("name") or "")
    organiser = (event.get("organiser") or "").lower().strip()
    start = event.get("start_date") or event.get("date_start") or ""
    return (title, organiser, str(start))


def count_populated(event: dict) -> int:
    """Count non-None, non-empty fields."""
    return sum(1 for v in event.values() if v is not None and v != "")


def better_event(a: dict, b: dict) -> dict:
    """Choose the better of two duplicate events.

    Prefers higher confidence, then more populated fields, then first encountered.
    """
    conf_a = CONFIDENCE_RANK.get(a.get("confidence", ""), 0)
    conf_b = CONFIDENCE_RANK.get(b.get("confidence", ""), 0)

    if conf_a != conf_b:
        return a if conf_a > conf_b else b

    pop_a = count_populated(a)
    pop_b = count_populated(b)

    if pop_a != pop_b:
        return a if pop_a > pop_b else b

    return a  # first encountered


def deduplicate(events: list[dict]) -> list[dict]:
    """Remove duplicate events.

    Pass 1: Exact composite key match.
    Pass 2: Fuzzy title match within same (organiser, start_date) group.
    """
    if not events:
        return []

    # Pass 1: Exact key dedup
    seen: dict[tuple, dict] = {}
    for event in events:
        key = composite_key(event)
        if key in seen:
            seen[key] = better_event(seen[key], event)
        else:
            seen[key] = event

    unique = list(seen.values())

    # Pass 2: Fuzzy title match within same (organiser, start_date) groups
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, event in enumerate(unique):
        organiser = (event.get("organiser") or "").lower().strip()
        start = event.get("start_date") or event.get("date_start") or ""
        groups[(organiser, str(start))].append(i)

    to_remove: set[int] = set()

    for indices in groups.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            if indices[i] in to_remove:
                continue
            for j in range(i + 1, len(indices)):
                if indices[j] in to_remove:
                    continue
                title_a = normalise_title(
                    unique[indices[i]].get("title")
                    or unique[indices[i]].get("name")
                    or ""
                )
                title_b = normalise_title(
                    unique[indices[j]].get("title")
                    or unique[indices[j]].get("name")
                    or ""
                )
                ratio = SequenceMatcher(None, title_a, title_b).ratio()
                if ratio >= FUZZY_THRESHOLD:
                    keep = better_event(unique[indices[i]], unique[indices[j]])
                    drop_idx = indices[j] if keep is unique[indices[i]] else indices[i]
                    to_remove.add(drop_idx)

    return [event for i, event in enumerate(unique) if i not in to_remove]

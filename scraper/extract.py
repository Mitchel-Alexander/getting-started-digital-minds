"""HTML-to-text cleaning utilities for the GDiDM events scraper.

This module handles converting raw HTML into readable text files that can
be processed by Claude Code for event extraction. No API calls are made here.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    """Convert raw HTML to readable plain text.

    Removes non-content elements (scripts, styles, nav, footer), preserves
    heading structure with markdown-style markers, and collapses whitespace.
    Truncates to ~15k characters.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag_name in ["script", "style", "nav", "footer", "header", "noscript", "svg"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Preserve heading structure by prepending markdown-style markers
    for level in range(1, 7):
        for heading in soup.find_all(f"h{level}"):
            prefix = "#" * level + " "
            heading.insert_before(f"\n{prefix}")
            heading.insert_after("\n")

    # Preserve link URLs inline
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if href and text and href.startswith("http"):
            link.replace_with(f"{text} ({href})")

    # Extract text
    text = soup.get_text(separator="\n", strip=True)

    # Collapse runs of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of whitespace within lines
    lines = []
    for line in text.split("\n"):
        lines.append(re.sub(r"[ \t]+", " ", line).strip())
    text = "\n".join(lines)

    # Truncate to ~15k characters
    if len(text) > 15000:
        text = text[:15000] + "\n\n[... truncated at 15,000 characters ...]"

    return text


def url_to_slug(url: str) -> str:
    """Convert a URL to a filesystem-safe slug."""
    parsed = urlparse(url)
    # Use domain + path, replace non-alphanumeric with underscores
    raw = parsed.netloc + parsed.path
    slug = re.sub(r"[^a-zA-Z0-9]", "_", raw)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:80]  # cap length


def save_page_text(
    text: str,
    source_name: str,
    abbreviation: str,
    url: str,
    output_dir: str = "scraper/pages",
) -> Path:
    """Save cleaned page text to a file with metadata header.

    Returns the path to the saved file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    slug = url_to_slug(url)
    filename = f"{abbreviation}_{slug}.txt"
    filepath = output_path / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = (
        f"Source: {source_name} ({abbreviation})\n"
        f"URL: {url}\n"
        f"Fetched: {timestamp}\n"
        f"{'=' * 60}\n\n"
    )

    filepath.write_text(header + text, encoding="utf-8")
    return filepath

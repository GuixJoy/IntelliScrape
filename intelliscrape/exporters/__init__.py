"""Export modules for scraped content."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional


def export_txt(
    content: str,
    output_path: str,
    *,
    url: Optional[str] = None,
) -> str:
    """Export content to plain text file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        if url:
            f.write(f"Source: {url}\n")
            f.write("=" * 80 + "\n\n")
        f.write(content)

    return str(path)


def export_json(
    data: Any,
    output_path: str,
    *,
    pretty: bool = True,
) -> str:
    """Export data to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2 if pretty else None, ensure_ascii=False)

    return str(path)


def export_csv(
    rows: List[Dict[str, Any]],
    output_path: str,
    *,
    columns: Optional[List[str]] = None,
) -> str:
    """Export data to CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return str(path)

    # Use provided columns or auto-detect
    if columns is None:
        columns = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return str(path)


def export_markdown(
    pages: List[Dict[str, str]],
    output_path: str,
) -> str:
    """Export scraped pages to Markdown file.

    Parameters
    ----------
    pages : list of dict
        Each dict should have 'url', 'title' (optional), and 'content'.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Scraped Content\n\n")
        f.write(f"Total pages: {len(pages)}\n\n")
        f.write("---\n\n")

        for i, page in enumerate(pages, 1):
            url = page.get("url", "Unknown")
            title = page.get("title", url)
            content = page.get("content", "")

            f.write(f"## {i}. {title}\n\n")
            f.write(f"**URL:** {url}\n\n")
            f.write(content)
            f.write("\n\n---\n\n")

    return str(path)


# Auto-detect format from extension
def export(
    content: Any,
    output_path: str,
    **kwargs,
) -> str:
    """Auto-detect format and export.

    Supported formats: .txt, .json, .csv, .md
    """
    path = Path(output_path)
    ext = path.suffix.lower()

    if ext == ".json":
        return export_json(content, output_path, **kwargs)
    elif ext == ".csv":
        return export_csv(content, output_path, **kwargs)
    elif ext in (".md", ".markdown"):
        return export_markdown(content, output_path, **kwargs)
    else:
        # Default to txt
        if isinstance(content, str):
            return export_txt(content, output_path, **kwargs)
        else:
            return export_json(content, output_path, **kwargs)

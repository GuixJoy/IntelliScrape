"""Command-line interface for IntelliScrape.

The simplest way to scrape any website.
Just: intelliscrape <url>
"""

from __future__ import annotations

import argparse
import json
import sys
import io

from .core import IntelliScrape, scrape
from .crawler import crawl
from .exceptions import IntelliScrapeError


# Fix Windows console encoding for Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intelliscrape",
        description="Scrape any website in one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  intelliscrape https://example.com                    # Scrape and print
  intelliscrape https://example.com -o output.txt     # Save to file
  intelliscrape https://example.com --json             # Get JSON with metadata
  intelliscrape https://example.com --json -o data.json  # Save JSON
  intelliscrape https://docs.python.org --crawl        # Crawl entire site
        """,
    )

    parser.add_argument(
        "url",
        help="URL to scrape",
    )

    parser.add_argument(
        "-o", "--output",
        help="Save output to file",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON with metadata",
    )

    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Crawl entire website",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Max pages to crawl (default: 50)",
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw HTML",
    )

    args = parser.parse_args(argv)

    if not args.url:
        parser.error("URL is required")

    try:
        if args.crawl:
            return _crawl(args)
        else:
            return _scrape(args)
    except IntelliScrapeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _scrape(args) -> int:
    """Scrape a single page."""
    scraper = IntelliScrape()

    if args.json:
        result = scraper.get_structured(args.url)
        content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    else:
        content = scraper.scrape(args.url, return_raw=args.raw)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved to {args.output}")
    else:
        print(content)

    return 0


def _crawl(args) -> int:
    """Crawl a website."""
    def log(msg):
        print(msg, file=sys.stderr)

    result = crawl(
        args.url,
        max_pages=args.max_pages,
        log=log,
    )

    if args.json:
        data = {
            "base_url": result.base_url,
            "total_pages": result.total_pages,
            "pages": [{"url": p.url, "content": p.content} for p in result.pages],
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        content = result.to_text()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved {result.total_pages} pages to {args.output}")
    else:
        print(content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

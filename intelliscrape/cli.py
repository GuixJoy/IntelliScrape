"""Command-line interface for IntelliScrape."""

from __future__ import annotations

import argparse
import sys

from .core import scrape
from .exceptions import IntelliScrapeError
from .link_checker import check_links


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelliscrape",
        description="Smart web scraping and link checking utility.",
    )

    parser.add_argument(
        "url",
        help="Target URL to scrape or check.",
    )

    parser.add_argument(
        "--check-links",
        action="store_true",
        help=(
            "Check all HTTP(S) links on the page and exit with a non-zero "
            "status code if any broken links are found."
        ),
    )

    parser.add_argument(
        "--ignore-external",
        action="store_true",
        help="Only check links that belong to the same host as the target URL.",
    )

    return parser


def _log(message: str) -> None:
    print(f"[intelliscrape] {message}", file=sys.stderr, flush=True)


def _run_check_links(url: str, ignore_external: bool) -> int:
    all_ok, broken = check_links(
        url,
        ignore_external=ignore_external,
        log=_log,
    )

    if all_ok:
        print("All links are healthy.")
        return 0

    print("Broken links detected:", file=sys.stderr)
    for link, status in broken:
        print(f"  [{status}] {link}", file=sys.stderr)
    return 1


def _run_scrape(url: str) -> int:
    print(scrape(url))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.url:
        parser.error("URL is required")

    try:
        return (
            _run_check_links(args.url, args.ignore_external)
            if args.check_links
            else _run_scrape(args.url)
        )
    except IntelliScrapeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - safety net
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


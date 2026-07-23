"""Command-line interface for IntelliScrape v2."""

from __future__ import annotations

import argparse
import sys

from .core import IntelliScrape, scrape
from .crawler import crawl
from .exceptions import IntelliScrapeError
from .link_checker import check_links


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelliscrape",
        description="Advanced web scraping with anti-detection capabilities.",
    )

    parser.add_argument(
        "url",
        help="Target URL to scrape or check.",
    )

    # Engine selection
    parser.add_argument(
        "--engine", "-e",
        choices=["auto", "static", "stealth"],
        default="auto",
        help="Scraping engine to use (default: auto-detect).",
    )

    # Proxy options
    parser.add_argument(
        "--proxy", "-p",
        type=str,
        action="append",
        help="Proxy to use (format: host:port or user:pass@host:port). Can be specified multiple times.",
    )

    parser.add_argument(
        "--proxy-type",
        choices=["residential", "datacenter", "mobile"],
        default="residential",
        help="Type of proxy (default: residential).",
    )

    # TLS options
    parser.add_argument(
        "--tls-profile",
        type=str,
        default="chrome131",
        help="TLS fingerprint profile to impersonate (default: chrome131).",
    )

    # CAPTCHA options
    parser.add_argument(
        "--captcha-api-key",
        type=str,
        help="API key for CAPTCHA solving service.",
    )

    parser.add_argument(
        "--captcha-provider",
        choices=["2captcha", "capsolver"],
        default="capsolver",
        help="CAPTCHA solving provider (default: capsolver).",
    )

    # Browser options
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (not headless).",
    )

    parser.add_argument(
        "--no-behavior",
        action="store_true",
        help="Disable human-like behavioral simulation.",
    )

    # Session options
    parser.add_argument(
        "--session",
        type=str,
        help="Persistent session profile name.",
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save scraped content to a file.",
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help="Return raw HTML instead of extracted text.",
    )

    # Crawler options
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Crawl the entire website and scrape all pages.",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum number of pages to crawl (default: 50).",
    )

    # Link checker
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Check all HTTP(S) links on the page for broken links.",
    )

    parser.add_argument(
        "--ignore-external",
        action="store_true",
        help="Only check links that belong to the same host as the target URL.",
    )

    # CAPTCHA check
    parser.add_argument(
        "--check-captcha",
        action="store_true",
        help="Check if the page has a CAPTCHA.",
    )

    # Verbose output
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output.",
    )

    return parser


def _log(message: str) -> None:
    print(f"[intelliscrape] {message}", file=sys.stderr, flush=True)


def _create_scraper(args) -> IntelliScrape:
    """Create an IntelliScrape instance from CLI args."""
    return IntelliScrape(
        proxy=args.proxy,
        api_key=args.captcha_api_key,
        captcha_provider=args.captcha_provider if args.captcha_api_key else None,
        headless=not args.no_headless,
        simulate_behavior=not args.no_behavior,
        tls_profile=args.tls_profile,
        session_profile=args.session,
        log_level="DEBUG" if args.verbose else "WARNING",
    )


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


def _run_scrape(url: str, args) -> int:
    scraper = _create_scraper(args)
    content = scraper.scrape(
        url,
        engine=args.engine if args.engine != "auto" else None,
        return_raw=args.raw,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        _log(f"Saved scraped content to {args.output}")
        print(f"Content saved to {args.output}")
    else:
        print(content)

    return 0


def _run_crawl(url: str, max_pages: int, args) -> int:
    result = crawl(
        url,
        max_pages=max_pages,
        log=_log,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.to_text())
        _log(f"Saved {result.total_pages} pages to {args.output}")
        print(f"Saved {result.total_pages} pages to {args.output}")
    else:
        print(result.to_text())

    if result.total_failed > 0:
        _log(f"Warning: {result.total_failed} pages failed to scrape")

    return 0


def _run_check_captcha(url: str, args) -> int:
    scraper = _create_scraper(args)
    captcha_info = scraper.check_captcha(url)

    if captcha_info:
        print(f"CAPTCHA detected: {captcha_info.captcha_type.value}")
        if captcha_info.site_key:
            print(f"Site key: {captcha_info.site_key}")
        return 1
    else:
        print("No CAPTCHA detected.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.url:
        parser.error("URL is required")

    try:
        if args.check_links:
            return _run_check_links(args.url, args.ignore_external)
        elif args.check_captcha:
            return _run_check_captcha(args.url, args)
        elif args.crawl:
            return _run_crawl(args.url, args.max_pages, args)
        else:
            return _run_scrape(args.url, args)
    except IntelliScrapeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - safety net
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

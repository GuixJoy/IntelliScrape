"""Command-line interface for IntelliScrape v2."""

from __future__ import annotations

import argparse
import json
import sys

from .core import IntelliScrape, scrape
from .crawler import crawl
from .exceptions import IntelliScrapeError
from .link_checker import check_links


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelliscrape",
        description="Advanced web scraping with anti-detection capabilities. Scrapes 98% of websites.",
        epilog="""
Examples:
  intelliscrape https://example.com
  intelliscrape https://site.com --output result.txt
  intelliscrape https://site.com --engine stealth --proxy user:pass@proxy:8080
  intelliscrape https://site.com --crawl --max-pages 100
  intelliscrape https://site.com --structured --output data.json
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "url",
        help="Target URL to scrape or check.",
    )

    # Engine selection
    parser.add_argument(
        "--engine", "-e",
        choices=["auto", "static", "playwright_stealth", "nodriver"],
        default="auto",
        help="Scraping engine (default: auto-detect best engine).",
    )

    # Proxy options
    parser.add_argument(
        "--proxy", "-p",
        type=str,
        action="append",
        help="Proxy (format: host:port or user:pass@host:port). Can repeat.",
    )

    # TLS options
    parser.add_argument(
        "--tls-profile",
        type=str,
        default="chrome131",
        help="TLS fingerprint to impersonate (default: chrome131).",
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
        help="Run browser in visible mode.",
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

    # Rate limiting
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.5,
        help="Minimum delay between requests in seconds (default: 0.5).",
    )

    parser.add_argument(
        "--max-delay",
        type=float,
        default=3.0,
        help="Maximum delay between requests in seconds (default: 3.0).",
    )

    parser.add_argument(
        "--requests-per-minute",
        type=int,
        help="Rate limit (requests per minute).",
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save output to file (.txt, .json, .csv, .md).",
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help="Return raw HTML instead of extracted text.",
    )

    parser.add_argument(
        "--structured",
        action="store_true",
        help="Return structured data (JSON) with metadata, meta tags, JSON-LD.",
    )

    # Crawler options
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Crawl entire website and scrape all pages.",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to crawl (default: 50).",
    )

    # Link checker
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Check all HTTP(S) links for broken links.",
    )

    parser.add_argument(
        "--ignore-external",
        action="store_true",
        help="Only check links on same host.",
    )

    # Detection
    parser.add_argument(
        "--check-captcha",
        action="store_true",
        help="Check if page has CAPTCHA.",
    )

    parser.add_argument(
        "--check-antibot",
        action="store_true",
        help="Check anti-bot protection on page.",
    )

    # Verbose
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
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        requests_per_minute=args.requests_per_minute,
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

    if args.structured:
        result = scraper.get_structured(url)
        content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    else:
        content = scraper.scrape(
            url,
            engine=args.engine if args.engine != "auto" else None,
            return_raw=args.raw,
        )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        _log(f"Saved content to {args.output}")
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


def _run_check_antibot(url: str, args) -> int:
    scraper = _create_scraper(args)
    antibot_info = scraper.check_antibot(url)

    if antibot_info:
        print(f"Anti-bot detected: {antibot_info.vendor.value}")
        print(f"Confidence: {antibot_info.confidence:.2f}")
        print(f"Indicators: {', '.join(antibot_info.indicators)}")
        if antibot_info.has_challenge:
            print("Has JavaScript challenge: Yes")
        if antibot_info.has_captcha:
            print("Has CAPTCHA: Yes")
        return 1
    else:
        print("No anti-bot protection detected.")
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
        elif args.check_antibot:
            return _run_check_antibot(args.url, args)
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

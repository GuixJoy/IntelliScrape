"""Command-line interface for IntelliScrape.

The simplest way to scrape any website.
Just: intelliscrape <url>
"""

from __future__ import annotations

import argparse
import json
import sys
import io

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from .core import IntelliScrape, scrape
from .crawler import crawl
from .auth import Authenticator, LoginCredentials
from .forms import FormSubmitter
from .pagination import Paginator
from .export import DataExporter
from .exceptions import IntelliScrapeError


# Fix Windows console encoding for Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intelliscrape",
        description="Scrape any website in one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scraping
  intelliscrape https://example.com
  intelliscrape https://example.com -o output.txt
  intelliscrape https://example.com --json
  
  # Pagination
  intelliscrape https://example.com/products --paginate --max-pages 10
  
  # Form submission
  intelliscrape https://google.com --search "python scraping"
  
  # Export formats
  intelliscrape https://example.com --export csv -o data.csv
  intelliscrape https://example.com --export json -o data.json
  intelliscrape https://example.com --export excel -o data.xlsx
  
  # Crawl entire site
  intelliscrape https://docs.python.org --crawl --max-pages 50
        """,
    )

    # Main URL
    parser.add_argument("url", help="URL to scrape")

    # Output options
    parser.add_argument("-o", "--output", help="Save output to file")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument("--raw", action="store_true", help="Output raw HTML")

    # Pagination
    parser.add_argument("--paginate", action="store_true", help="Auto-follow pagination")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to scrape")

    # Search
    parser.add_argument("--search", type=str, help="Submit search query")

    # Export
    parser.add_argument("--export", choices=["json", "csv", "excel", "sqlite", "text", "markdown"],
                       help="Export format")

    # Crawl
    parser.add_argument("--crawl", action="store_true", help="Crawl entire website")

    # Force browser
    parser.add_argument("--force-browser", action="store_true", help="Force browser engine")

    args = parser.parse_args(argv)

    if not args.url:
        parser.error("URL is required")

    try:
        if args.crawl:
            return _crawl(args)
        elif args.paginate:
            return _paginate(args)
        elif args.search:
            return _search(args)
        else:
            return _scrape(args)
    except IntelliScrapeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1


def _scrape(args) -> int:
    """Scrape a single page with spinner."""
    scraper = IntelliScrape()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Scraping {args.url}...", total=None)

        if args.json:
            result = scraper.get_structured(args.url, force_browser=args.force_browser)
            content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
        else:
            content = scraper.scrape(args.url, return_raw=args.raw, force_browser=args.force_browser)

        progress.update(task, completed=True)

    # Export
    if args.export:
        return _export_content(content, args.export, args.output, args.url)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[green]Saved to {args.output}[/green]")
    else:
        print(content)

    return 0


def _paginate(args) -> int:
    """Scrape with pagination."""
    scraper = IntelliScrape()
    paginator = Paginator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Paginating...", total=args.max_pages)

        pages = []
        current_url = args.url
        current_page = 1

        while current_url and current_page <= args.max_pages:
            # Fetch page
            content = scraper.scrape(current_url, force_browser=args.force_browser)
            pages.append({"url": current_url, "content": content, "page": current_page})

            progress.update(task, advance=1, description=f"Page {current_page}...")

            # Find next page
            html = scraper.scrape(current_url, return_raw=True, force_browser=args.force_browser)
            current_url = paginator.find_next_page(html, current_url, current_page)
            current_page += 1

        progress.update(task, completed=args.max_pages, description="Pagination complete!")

    # Summary
    console.print()
    console.print(Panel(
        f"[green]Scraped: {len(pages)} pages[/green]\n"
        f"URL: {args.url}",
        title="Pagination Summary",
        border_style="blue",
    ))

    # Export
    if args.export:
        return _export_content(pages, args.export, args.output, args.url)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for page in pages:
                f.write(f"{'='*80}\n")
                f.write(f"URL: {page['url']}\n")
                f.write(f"Page: {page['page']}\n")
                f.write(f"{'='*80}\n\n")
                f.write(page['content'])
                f.write("\n\n")
        console.print(f"[green]Saved {len(pages)} pages to {args.output}[/green]")
    else:
        for page in pages:
            print(f"\n{'='*80}")
            print(f"URL: {page['url']}")
            print(f"Page: {page['page']}")
            print(f"{'='*80}\n")
            print(page['content'])

    return 0


def _search(args) -> int:
    """Submit search and scrape results."""
    scraper = IntelliScrape()
    form_submitter = FormSubmitter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Searching '{args.search}'...", total=None)

        # Get the page
        html = scraper.scrape(args.url, return_raw=True, force_browser=args.force_browser)

        # Find and submit search form
        result_html = form_submitter.search(
            html,
            args.search,
            base_url=args.url,
        )

        progress.update(task, completed=True)

    if result_html:
        # Extract text from results
        content = scraper.scrape(args.url, force_browser=args.force_browser)

        # Export
        if args.export:
            return _export_content(content, args.export, args.output, args.url)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
            console.print(f"[green]Saved to {args.output}[/green]")
        else:
            print(content)
    else:
        console.print("[yellow]No search form found[/yellow]")

    return 0


def _crawl(args) -> int:
    """Crawl a website with progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling...", total=args.max_pages)

        def on_page(done, failed):
            progress.update(task, completed=done + failed)

        result = crawl(
            args.url,
            max_pages=args.max_pages,
            on_page=on_page,
        )

        progress.update(task, completed=args.max_pages, description="Crawl complete!")

    # Summary
    console.print()
    console.print(Panel(
        f"[green]Scraped: {result.total_pages} pages[/green]\n"
        f"[red]Failed: {result.total_failed} pages[/red]\n"
        f"URL: {args.url}",
        title="Crawl Summary",
        border_style="blue",
    ))

    # Convert to exportable format
    pages = [{"url": p.url, "content": p.content} for p in result.pages]

    # Export
    if args.export:
        return _export_content(pages, args.export, args.output, args.url)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.to_text())
        console.print(f"[green]Saved {result.total_pages} pages to {args.output}[/green]")
    else:
        print(result.to_text())

    return 0


def _export_content(content, format: str, output: str, url: str) -> int:
    """Export content to specified format."""
    if isinstance(content, str):
        # Parse text content into structured data
        data = [{"url": url, "content": content}]
    else:
        data = content

    # Determine output filename
    if not output:
        output = f"output.{format if format != 'markdown' else 'md'}"

    # Export
    result = DataExporter.export(data, format=format, file=output)
    console.print(f"[green]Exported to {output} ({format})[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command-line interface for IntelliScrape.

The simplest way to scrape any website.
Just: intelliscrape <url>

IntelliScrape automatically:
- Analyzes the site type and protection level
- Selects the best engine
- Uses free proxies when needed (no API key required!)
- Configures rate limiting automatically
"""

from __future__ import annotations

import argparse
import json
import sys
import io

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

from .core import IntelliScrape, scrape
from .intelligent import SiteAnalyzer
from .crawler import crawl
from .auth import Authenticator, LoginCredentials
from .forms import FormSubmitter
from .pagination import Paginator
from .export import DataExporter
from .downloader import Downloader
from .cookies import CookieManager
from .interceptor import RequestInterceptor
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
  # Basic scraping (intelligent mode on by default)
  intelliscrape https://example.com
  intelliscrape https://example.com -o output.txt
  intelliscrape https://example.com --json
  
  # Analyze site (see what approach IntelliScrape would use)
  intelliscrape https://amazon.com --analyze
  
  # Find free proxies
  intelliscrape --find-proxies
  
  # Use free proxies (automatic!)
  intelliscrape https://amazon.com --use-free-proxies
  
  # Disable intelligent mode (manual control)
  intelliscrape https://example.com --no-intelligent
  
  # Login and scrape
  intelliscrape https://site.com --login --username user --password pass
  
  # Save/load cookies
  intelliscrape https://site.com --save-cookies cookies.json
  intelliscrape https://site.com --load-cookies cookies.json
  
  # Block URLs
  intelliscrape https://site.com --block "analytics,tracking,ads"
  
  # Custom headers
  intelliscrape https://site.com --header "Authorization: Bearer xxx"
  
  # Pagination
  intelliscrape https://example.com/products --paginate --max-pages 10
  
  # Search
  intelliscrape https://google.com --search "python scraping"
  
  # Download files
  intelliscrape https://example.com --download
  intelliscrape https://example.com --download-images
  
  # Export formats
  intelliscrape https://example.com --export csv -o data.csv
  
  # Crawl entire site
  intelliscrape https://docs.python.org --crawl --max-pages 50
  
  # With residential proxy (for better quality)
  intelliscrape https://amazon.com --brightdata-key YOUR_KEY
        """,
    )

    # Main URL (optional for some commands)
    parser.add_argument("url", nargs="?", help="URL to scrape")

    # Output options
    parser.add_argument("-o", "--output", help="Save output to file")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument("--raw", action="store_true", help="Output raw HTML")

    # Intelligent mode
    parser.add_argument("--analyze", action="store_true", help="Analyze site and show recommendations")
    parser.add_argument("--no-intelligent", action="store_true", help="Disable intelligent auto-detection")

    # Free proxy options
    parser.add_argument("--find-proxies", action="store_true", help="Find and test free proxies")
    parser.add_argument("--use-free-proxies", action="store_true", help="Use free proxies (automatic)")
    parser.add_argument("--no-free-proxies", action="store_true", help="Disable free proxy finder")

    # Proxy providers (for residential proxies)
    parser.add_argument("--brightdata-key", type=str, help="Bright Data API key for residential proxies")
    parser.add_argument("--scraperapi-key", type=str, help="ScraperAPI key")
    parser.add_argument("--oxylabs-key", type=str, help="Oxylabs API key")
    parser.add_argument("--smartproxy-key", type=str, help="Smartproxy API key")

    # Authentication
    parser.add_argument("--login", action="store_true", help="Login to site")
    parser.add_argument("--username", type=str, help="Login username/email")
    parser.add_argument("--password", type=str, help="Login password")
    parser.add_argument("--login-url", type=str, help="Explicit login URL")

    # Cookies
    parser.add_argument("--save-cookies", type=str, help="Save cookies to file")
    parser.add_argument("--load-cookies", type=str, help="Load cookies from file")

    # Request modification
    parser.add_argument("--block", type=str, help="Block URLs (comma-separated patterns)")
    parser.add_argument("--header", type=str, action="append", help="Add header (Key: Value)")

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

    # Downloads
    parser.add_argument("--download", action="store_true", help="Download linked files")
    parser.add_argument("--download-images", action="store_true", help="Download all images")
    parser.add_argument("--download-dir", default="downloads", help="Download directory")

    # Force browser
    parser.add_argument("--force-browser", action="store_true", help="Force browser engine")

    args = parser.parse_args(argv)

    # Handle commands that don't require URL
    if args.find_proxies:
        return _find_proxies(args)
    
    if not args.url:
        parser.error("URL is required for most commands")

    try:
        # Handle analyze command
        if args.analyze:
            return _analyze(args)
        
        if args.crawl:
            return _crawl(args)
        elif args.paginate:
            return _paginate(args)
        elif args.search:
            return _search(args)
        elif args.download or args.download_images:
            return _download(args)
        else:
            return _scrape(args)
    except IntelliScrapeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1


def _create_scraper(args) -> IntelliScrape:
    """Create scraper with CLI options."""
    # Parse headers
    headers = {}
    if args.header:
        for h in args.header:
            if ":" in h:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()

    # Create scraper with intelligent mode
    scraper = IntelliScrape(
        brightdata_key=args.brightdata_key,
        scraperapi_key=args.scraperapi_key,
        oxylabs_key=args.oxylabs_key,
        smartproxy_key=args.smartproxy_key,
        intelligent=not args.no_intelligent,
        use_free_proxies=not args.no_free_proxies,
    )

    # Apply headers to all engines
    if headers:
        for engine in scraper.engines.values():
            if hasattr(engine, 'session'):
                engine.session.headers.update(headers)
            if hasattr(engine, 'headers'):
                engine.headers.update(headers)

    return scraper


def _find_proxies(args) -> int:
    """Find and test free proxies."""
    from .proxy.free_finder import FreeProxyFinder
    
    finder = FreeProxyFinder()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Finding free proxies...", total=None)
        
        proxies = finder.find_proxies(
            protocol="https",
            test=True,
            max_workers=10,
        )
        
        progress.update(task, completed=True)
    
    if not proxies:
        console.print("[yellow]No working proxies found[/yellow]")
        return 1
    
    # Create table
    table = Table(title=f"Found {len(proxies)} Working Proxies")
    table.add_column("Proxy URL", style="cyan")
    table.add_column("Speed", style="green")
    table.add_column("Status", style="yellow")
    
    for proxy in sorted(proxies, key=lambda p: p.speed)[:20]:  # Show top 20
        table.add_row(
            proxy.url,
            f"{proxy.speed:.2f}s",
            "Working" if proxy.is_working else "Failed",
        )
    
    console.print(table)
    console.print(f"\n[green]Use with: intelliscrape <url> --use-free-proxies[/green]")
    
    return 0


def _analyze(args) -> int:
    """Analyze a site and show recommendations."""
    analyzer = SiteAnalyzer()
    analysis = analyzer.analyze(args.url)

    # Create analysis table
    table = Table(title=f"Site Analysis: {analysis.domain}", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Site Type", analysis.site_type.value)
    table.add_row("Protection Level", analysis.protection_level.value)
    table.add_row("Requires Browser", "Yes" if analysis.requires_browser else "No")
    table.add_row("Requires Residential Proxy", "Yes" if analysis.requires_residential_proxy else "No")
    table.add_row("Recommended Engine", analysis.recommended_engine)
    table.add_row("Recommended Delay", f"{analysis.recommended_delay:.1f} seconds")
    table.add_row("Recommended Batch Size", str(analysis.recommended_batch_size))

    console.print(table)

    # Show notes
    if analysis.notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in analysis.notes:
            console.print(f"  • {note}")

    # Show proxy status
    scraper = _create_scraper(args)
    proxy_status = scraper.get_proxy_status()
    
    console.print("\n[bold]Proxy Status:[/bold]")
    console.print(f"  • User proxies: {proxy_status['user_proxies']}")
    console.print(f"  • Providers available: {', '.join(proxy_status['providers_available']) or 'None'}")
    console.print(f"  • Healthy proxies: {proxy_status['healthy_proxies']}")
    console.print(f"  • Free proxies enabled: {'Yes' if not args.no_free_proxies else 'No'}")

    return 0


def _scrape(args) -> int:
    """Scrape a single page with spinner."""
    scraper = _create_scraper(args)

    # Handle login
    if args.login:
        if not args.username or not args.password:
            console.print("[red]Error: --username and --password required for login[/red]")
            return 1

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Logging in to {args.url}...", total=None)

            auth = Authenticator(scraper.session_manager.session)
            credentials = LoginCredentials(
                username=args.username,
                password=args.password,
            )
            success = auth.login(args.url, credentials, login_url=args.login_url)

            progress.update(task, completed=True)

        if success:
            console.print("[green]Login successful![/green]")
        else:
            console.print("[yellow]Login failed, continuing anyway...[/yellow]")

    # Load cookies
    if args.load_cookies:
        cookie_mgr = CookieManager()
        try:
            with open(args.load_cookies, "r") as f:
                cookies = json.load(f)
            cookie_mgr.save_cookies(args.url, cookies)
            console.print(f"[green]Loaded cookies from {args.load_cookies}[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not load cookies: {e}[/yellow]")

    # Scrape
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

    # Save cookies
    if args.save_cookies:
        cookie_mgr = CookieManager()
        # Get cookies from the scraper's engines
        cookies = {}
        for engine in scraper.engines.values():
            if hasattr(engine, 'session'):
                cookies.update(dict(engine.session.cookies))
                break
        cookie_mgr.save_cookies(args.url, cookies)
        with open(args.save_cookies, "w") as f:
            json.dump(cookies, f, indent=2)
        console.print(f"[green]Saved cookies to {args.save_cookies}[/green]")

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
    scraper = _create_scraper(args)
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
    scraper = _create_scraper(args)
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
    scraper = _create_scraper(args)

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


def _download(args) -> int:
    """Download files from page."""
    scraper = _create_scraper(args)
    downloader = Downloader()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Downloading from {args.url}...", total=None)

        # Get the page
        html = scraper.scrape(args.url, return_raw=True, force_browser=args.force_browser)

        if args.download_images:
            results = downloader.download_images(html, args.url, args.download_dir)
        else:
            results = downloader.download_links(html, args.url, args.download_dir)

        progress.update(task, completed=True)

    # Summary
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    console.print()
    console.print(Panel(
        f"[green]Downloaded: {successful} files[/green]\n"
        f"[red]Failed: {failed} files[/red]\n"
        f"Directory: {args.download_dir}",
        title="Download Summary",
        border_style="blue",
    ))

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

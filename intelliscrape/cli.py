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
from .link_checker import check_links as _check_links
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
  
  # Manual CAPTCHA solving (opens visible browser when CAPTCHA detected)
  intelliscrape https://site-with-captcha.com --manual-captcha
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

    # Link checking
    parser.add_argument("--check-links", action="store_true",
                       help="Check all links on the page and report status")

    # Website intelligence
    parser.add_argument("--tech", action="store_true",
                       help="Detect website technology stack (frameworks, CMS, analytics, CDN, etc.)")

    # Downloads
    parser.add_argument("--download", action="store_true", help="Download linked files")
    parser.add_argument("--download-images", action="store_true", help="Download all images")
    parser.add_argument("--download-dir", default="downloads", help="Download directory")

    # Force browser
    parser.add_argument("--force-browser", action="store_true", help="Force browser engine")

    # Manual CAPTCHA
    parser.add_argument("--manual-captcha", action="store_true",
                       help="When a CAPTCHA is detected, open a visible browser and wait for you to solve it")

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
        
        if args.check_links:
            return _check_links_cmd(args)
        elif args.tech:
            return _tech_report(args)
        elif args.crawl:
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
        manual_captcha=args.manual_captcha,
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


def _check_links_cmd(args) -> int:
    """Check all links on a page and display results."""
    scraper = _create_scraper(args)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Checking links on {args.url}...", total=None)

        # Fetch the page HTML first (uses the scraper's engine chain)
        html = scraper.scrape(args.url, return_raw=True, force_browser=args.force_browser)

        progress.update(task, description="Checking link statuses...")

        # Use the link_checker with a session from the scraper's static engine
        from requests import Session
        from .downloader import create_session as _create_session

        session = _create_session()
        try:
            report = _check_links(
                args.url,
                timeout=10,
                session=session,
                downloader=lambda url, timeout: html,
            )
        finally:
            session.close()

        progress.update(task, completed=True)

    # --- Summary panel ---
    s = report.summary
    console.print()
    console.print(Panel(
        f"[bold]URL:[/bold] {report.url}\n"
        f"[bold]Total links:[/bold] {s.total}\n"
        f"[green]OK:[/green] {s.ok}  "
        f"[yellow]Redirected:[/yellow] {s.redirected}  "
        f"[red]Broken:[/red] {s.broken}  "
        f"[red]Error:[/red] {s.error}  "
        f"[red]Timeout:[/red] {s.timeout}\n"
        f"[bold]Internal:[/bold] {s.internal}  "
        f"[bold]External:[/bold] {s.external}\n"
        f"[bold]Success rate:[/bold] {s.success_rate:.1f}%",
        title="Link Check Summary",
        border_style="blue",
    ))

    # --- By-type breakdown ---
    if s.by_type:
        type_table = Table(title="Links by Type", show_header=True)
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", justify="right", style="green")
        for lt, count in sorted(s.by_type.items(), key=lambda x: -x[1]):
            type_table.add_row(lt, str(count))
        console.print(type_table)

    # --- Broken links detail ---
    broken = [(r.url, r.status_code, r.error) for r in report.links if not r.is_ok]
    if broken:
        broken_table = Table(title="Broken Links", show_header=True)
        broken_table.add_column("URL", style="red")
        broken_table.add_column("Status", justify="right", style="yellow")
        broken_table.add_column("Error", style="dim")
        for lnk, code, err in broken[:50]:  # limit to first 50
            broken_table.add_row(lnk, str(code) if code else "-", err or "")
        console.print(broken_table)
        if len(broken) > 50:
            console.print(f"  [dim]... and {len(broken) - 50} more broken links[/dim]")
    else:
        console.print("[green]All links are working![/green]")

    # --- Export ---
    if args.export:
        export_data = [
            {
                "url": r.url,
                "status_code": r.status_code,
                "status": r.status.value,
                "type": r.link_type.value,
                "is_external": r.is_external,
                "redirect_url": r.redirect_url or "",
                "error": r.error or "",
            }
            for r in report.links
        ]
        return _export_content(export_data, args.export, args.output, args.url)

    if args.output:
        import json as _json
        export_data = [
            {
                "url": r.url,
                "status_code": r.status_code,
                "status": r.status.value,
                "type": r.link_type.value,
                "is_external": r.is_external,
                "redirect_url": r.redirect_url or "",
                "error": r.error or "",
            }
            for r in report.links
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            _json.dump(export_data, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Saved link check results to {args.output}[/green]")

    return 0


def _tech_report(args) -> int:
    """Detect and display website technology stack."""
    scraper = _create_scraper(args)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Analyzing {args.url}...", total=None)

        tech = scraper.detect_tech(args.url, force_browser=args.force_browser)

        progress.update(task, completed=True)

    # --- Summary panel ---
    s = tech.summary
    total = len(tech.all_tech)
    console.print()
    console.print(Panel(
        f"[bold]URL:[/bold] {tech.url}\n"
        f"[bold]Technologies found:[/bold] {total}",
        title="Website Intelligence",
        border_style="blue",
    ))

    # --- Category tables ---
    category_labels = {
        "frameworks": "Frameworks",
        "css_frameworks": "CSS Frameworks",
        "js_libraries": "JS Libraries",
        "analytics": "Analytics & Tracking",
        "cdn": "CDN",
        "hosting": "Hosting / Platform",
        "cms": "CMS",
        "payment": "Payment Providers",
        "languages": "Languages / Runtimes",
        "email_marketing": "Email / Marketing",
        "other": "Other",
    }

    for attr, label in category_labels.items():
        items = getattr(tech, attr)
        if not items:
            continue
        table = Table(title=label, show_header=True)
        table.add_column("Technology", style="cyan")
        table.add_column("Confidence", justify="right", style="green")
        table.add_column("Evidence", style="dim")
        for t in items:
            table.add_row(
                t.name,
                f"{t.confidence:.0%}",
                ", ".join(t.evidence[:3]),
            )
        console.print(table)

    # --- Server headers ---
    interesting_headers = {
        k: v for k, v in tech.headers.items()
        if k.lower() in (
            "server", "x-powered-by", "x-generator",
            "via", "x-amz-cf-pop", "x-vercel",
            "cf-ray", "x-shopify-stage",
        )
    }
    if interesting_headers:
        htable = Table(title="Server Headers", show_header=True)
        htable.add_column("Header", style="cyan")
        htable.add_column("Value", style="green")
        for k, v in interesting_headers.items():
            htable.add_row(k, v)
        console.print(htable)

    if total == 0:
        console.print("[yellow]No technologies detected.[/yellow]")

    # --- Export ---
    if args.export:
        return _export_content(tech.to_dict(), args.export, args.output, args.url)

    if args.output:
        import json as _json
        with open(args.output, "w", encoding="utf-8") as f:
            _json.dump(tech.to_dict(), f, indent=2, ensure_ascii=False)
        console.print(f"[green]Saved tech report to {args.output}[/green]")

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

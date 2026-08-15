<div align="center">

# IntelliScrape

**Scrape anything.**

A Python web scraping library with anti-detection, TLS fingerprint impersonation, and stealth browsing.

[![PyPI version](https://img.shields.io/pypi/v/intelliscrape?color=blue&label=PyPI&logo=pypi&logoColor=white)](https://pypi.org/project/intelliscrape/)
[![Python](https://img.shields.io/pypi/pyversions/intelliscrape?logo=python&logoColor=white)](https://pypi.org/project/intelliscrape/)
[![Downloads](https://img.shields.io/pypi/dm/intelliscrape?color=green&label=Downloads&logo=python&logoColor=white)](https://pypi.org/project/intelliscrape/)
[![License](https://img.shields.io/pypi/l/intelliscrape?color=yellow)](https://github.com/GuixJoy/IntelliScrape/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/GuixJoy/IntelliScrape?logo=github)](https://github.com/GuixJoy/IntelliScrape)

[Installation](#installation) | [Quick Start](#quick-start) | [CLI Reference](#cli-reference) | [Library API](#library-api-reference) | [Web Search](#web_search--web-search) | [Examples](#examples) | [Engine System](#engine-system) | [Features](#features)

</div>

---

## What is IntelliScrape?

IntelliScrape is a Python web scraping library that **scrapes any website** out of the box. It uses a **5-tier engine system** that automatically escalates from fast HTTP requests to full browser automation — you get the cheapest, fastest method that works, and heavier weapons only when needed.

No more switching between `requests`, `playwright`, and `selenium`. No more debugging why your scraper got blocked. Just `scrape(url)` and you're done.

**Key capabilities:**
- 5-tier engine escalation (static → Playwright → Camoufox → nodriver → DrissionPage)
- TLS fingerprint impersonation (JA3/JA4 bypass)
- Browser fingerprint randomization
- Human-like behavioral simulation
- CAPTCHA detection, automated solving, and manual solving
- Anti-bot vendor detection (Cloudflare, Akamai, DataDome, PerimeterX) with smart false-positive prevention
- Real-time progress reporting (see which engine is running)
- Intelligent site analysis and auto-configuration
- Proxy rotation with free proxy finder
- Export to JSON, CSV, Excel, SQLite, Text, Markdown
- Async support for concurrent scraping
- Link checking (status verification, categorization, broken link detection)
- **Website mirroring** (HTTrack-ported, WARC/ZIP export, offline browsing)

---

## Installation

```bash
pip install intelliscrape
```

### Optional Extras

| Extra | Command | What it adds |
|---|---|---|
| `stealth` | `pip install intelliscrape[stealth]` | nodriver engine (anti-WebDriver detection) |
| `camoufox` | `pip install intelliscrape[camoufox]` | Camoufox engine (Firefox-based, C++ patches) |
| `captcha` | `pip install intelliscrape[captcha]` | CapSolver integration (reCAPTCHA, hCaptcha, Turnstile) |
| `async` | `pip install intelliscrape[async]` | Async/concurrent scraping |
| `all` | `pip install intelliscrape[all]` | Everything above |
| `dev` | `pip install intelliscrape[dev]` | pytest, ruff |

---

## Quick Start

### One-liner (Python)

```python
from intelliscrape import scrape

text = scrape("https://example.com")
print(text[:500])
```

### CLI

```bash
intelliscrape https://example.com
```

### Full-featured class

```python
from intelliscrape import IntelliScrape

scraper = IntelliScrape()
result = scraper.scrape("https://example.com")
print(result)
```

### With proxy

```python
scraper = IntelliScrape(proxy="user:pass@proxy:8080")
result = scraper.scrape("https://protected-site.com")
```

### Get structured data

```python
scraper = IntelliScrape()
data = scraper.get_structured("https://github.com")

print(data.title)          # Page title
print(data.description)    # Meta description
print(data.og_data)        # OpenGraph tags
print(data.json_ld)        # JSON-LD structured data
```

### Crawl entire website

```python
from intelliscrape import crawl

result = crawl("https://docs.python.org", max_pages=100)
print(f"Scraped {result.total_pages} pages")

for page in result.pages:
    print(f"  {page.url}: {len(page.content)} chars")
```

---

## CLI Reference

```
intelliscrape [URL] [OPTIONS]
```

### Output

| Flag | Description |
|---|---|
| `-o, --output FILE` | Save output to file |
| `--json` | Structured JSON (title, description, meta tags) |
| `--raw` | Raw HTML instead of extracted text |

### Intelligent Mode

| Flag | Description |
|---|---|
| `--analyze` | Analyze site and show recommendations |
| `--no-intelligent` | Disable intelligent auto-detection |

### Engine

| Flag | Description |
|---|---|
| `--engine ENGINE` | Force specific engine: `static`, `playwright_stealth`, `camoufox`, `nodriver`, `drissionpage` |
| `--force-browser` | Force browser engine for JS-heavy sites |
| `--manual-captcha` | Open visible browser for manual CAPTCHA solving |
| `-v, --verbose` | Show real-time progress (which engine is running, CAPTCHA solving, etc.) |

### Proxy

| Flag | Description |
|---|---|
| `--use-free-proxies` | Use free proxies automatically |
| `--no-free-proxies` | Disable free proxy finder |
| `--find-proxies` | Find and test free proxies (no scraping) |
| `--brightdata-key KEY` | Bright Data API key |
| `--scraperapi-key KEY` | ScraperAPI key |
| `--oxylabs-key KEY` | Oxylabs API key |
| `--smartproxy-key KEY` | Smartproxy API key |

### Authentication

| Flag | Description |
|---|---|
| `--login` | Login before scraping |
| `--username USER` | Username/email |
| `--password PASS` | Password |
| `--login-url URL` | Explicit login URL |

### Cookies

| Flag | Description |
|---|---|
| `--save-cookies FILE` | Save cookies to JSON |
| `--load-cookies FILE` | Load cookies from JSON |

### Request Modification

| Flag | Description |
|---|---|
| `--block PATTERNS` | Block URLs (comma-separated) |
| `--header "Key: Value"` | Add custom header (repeatable) |

### Pagination & Search

| Flag | Description |
|---|---|
| `--paginate` | Auto-follow pagination |
| `--max-pages N` | Max pages (default: 50) |
| `--search QUERY` | Submit search query on a specific page |

### Web Search

| Flag | Description |
|---|---|
| `--web-search QUERY` | Search the web (DuckDuckGo → Google News → Bing News) and return a list of results |
| `--search-limit N` | Max results for `--web-search` (default: 10) |
| `--fetch-content` | Also scrape the full text of each result page |

### Crawl

| Flag | Description |
|---|---|
| `--crawl` | Crawl entire website |

### Link Checking

| Flag | Description |
|---|---|
| `--check-links` | Check all links on the page and report status |

### Downloads

| Flag | Description |
|---|---|
| `--download` | Download linked files |
| `--download-images` | Download all images |
| `--download-dir DIR` | Download directory (default: downloads) |

### Mirror (HTTrack-style)

| Flag | Description |
|---|---|
| `--mirror` | Mirror entire website for offline browsing |
| `--mirror-depth N` | Max recursion depth (default: 5) |
| `--mirror-output DIR` | Output directory (default: ./mirror) |
| `--mirror-zip FILE` | Also create ZIP archive |
| `--mirror-warc FILE` | Also create WARC archive |
| `--mirror-delay SEC` | Delay between requests (default: 0.5) |
| `--mirror-exclude PAT` | Exclude URL patterns (repeatable) |
| `--mirror-include PAT` | Include URL patterns (repeatable) |
| `--mirror-engine ENG` | Engine: static, playwright, camoufox, nodriver, auto |
| `--mirror-proxy URL` | Proxy for mirroring |
| `--mirror-update` | Resume/update existing mirror |
| `--no-robots` | Ignore robots.txt |

### Export

| Flag | Description |
|---|---|
| `--export FORMAT` | `json`, `csv`, `excel`, `sqlite`, `text`, `markdown` |

### Examples

```bash
# Basic
intelliscrape https://example.com -o output.txt

# Structured data
intelliscrape https://example.com --json

# Analyze protection
intelliscrape https://amazon.com --analyze

# Free proxies
intelliscrape https://amazon.com --use-free-proxies

# Login
intelliscrape https://site.com --login --username user --password pass

# Pagination
intelliscrape https://example.com/products --paginate --max-pages 10

# Crawl
intelliscrape https://docs.python.org --crawl --max-pages 50

# Check links
intelliscrape https://example.com --check-links
intelliscrape https://example.com --check-links --export json -o report.json

# Export
intelliscrape https://example.com --export csv -o data.csv

# Manual CAPTCHA
intelliscrape https://protected-site.com --manual-captcha

# Force browser
intelliscrape https://react-app.com --force-browser

# Mirror entire site
intelliscrape https://example.com --mirror --mirror-depth 3 --mirror-output ./backup

# Mirror + ZIP
intelliscrape https://example.com --mirror --mirror-zip site.zip

# Mirror + WARC
intelliscrape https://example.com --mirror --mirror-warc archive.warc.gz

# Mirror with proxy
intelliscrape https://example.com --mirror --mirror-proxy socks5://proxy:1080

# Mirror excluded patterns
intelliscrape https://example.com --mirror --mirror-exclude "*.pdf" --mirror-exclude "/admin/*"

# Web search (no URL needed)
intelliscrape --web-search "python web scraping"
intelliscrape --web-search "openai news" --search-limit 5
intelliscrape --web-search "site:github.com python scraper" --search-limit 20 --export json -o results.json

# Web search + scrape each result page
intelliscrape --web-search "best python libraries" --fetch-content
intelliscrape --web-search "fastapi tutorial" --fetch-content --export json -o results.json
```

---

## Library API Reference

### `scrape()` — Quick One-liner

```python
from intelliscrape import scrape

text = scrape(url, **kwargs)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | str | required | Target URL |
| `engine` | str | None | Force engine: `static`, `playwright_stealth`, `camoufox`, `nodriver` |
| `extract` | bool | True | Extract text from HTML |
| `clean` | bool | True | Clean extracted text |
| `return_raw` | bool | False | Return raw HTML |
| `return_structured` | bool | False | Return `StructuredData` |
| `handle_consent` | bool | True | Handle cookie consent banners |
| `force_browser` | bool | False | Force browser engine |

---

### `IntelliScrape` — Main Class

#### Constructor

```python
from intelliscrape import IntelliScrape

scraper = IntelliScrape(**kwargs)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `proxy` | str, ProxyConfig, list | None | Single proxy or list |
| `proxies` | list of str | None | Proxy strings |
| `brightdata_key` | str | None | Bright Data API key |
| `scraperapi_key` | str | None | ScraperAPI key |
| `oxylabs_key` | str | None | Oxylabs API key |
| `smartproxy_key` | str | None | Smartproxy API key |
| `prefer_residential` | bool | True | Prefer residential proxies |
| `use_free_proxies` | bool | True | Auto-find free proxies |
| `api_key` | str | None | CAPTCHA solving API key |
| `captcha_provider` | str | None | `2captcha` or `capsolver` |
| `headless` | bool | True | Headless browser mode |
| `simulate_behavior` | bool | True | Human-like behavior simulation |
| `manual_captcha` | bool | False | Manual CAPTCHA solving mode |
| `tls_profile` | str | `chrome131` | TLS fingerprint profile |
| `session_profile` | str | None | Persistent session name |
| `max_retries` | int | 3 | Max retry attempts |
| `min_delay` | float | 0.5 | Min delay between requests |
| `max_delay` | float | 3.0 | Max delay between requests |
| `requests_per_minute` | int | None | Rate limit |
| `intelligent` | bool | True | Enable intelligent mode |
| `log_level` | str | `WARNING` | Logging level |

#### Methods

##### `scrape(url, **kwargs)`

Scrape a URL and return text content.

```python
result = scraper.scrape(
    url="https://example.com",
    engine=None,
    extract=True,
    clean=True,
    return_raw=False,
    return_structured=False,
    handle_consent=True,
    force_browser=False,
    intelligent=None,
)
```

##### `get_structured(url, **kwargs)`

Get structured data (title, description, meta tags, JSON-LD).

```python
data = scraper.get_structured("https://github.com")
print(data.title)
print(data.description)
print(data.og_data)
print(data.json_ld)
```

##### `analyze(url)`

Analyze a site and return recommendations.

```python
analysis = scraper.analyze("https://amazon.com")
print(analysis.site_type)           # "ecommerce"
print(analysis.protection_level)    # "high"
print(analysis.recommended_engine)  # "playwright_stealth"
print(analysis.recommended_delay)   # 3.0
```

##### `scrape_many(urls, **kwargs)`

Scrape multiple URLs with rate limiting.

```python
results = scraper.scrape_many([
    "https://example.com/page1",
    "https://example.com/page2",
])
# Returns: [{"url": ..., "content": ..., "success": ..., "error": ...}, ...]
```

##### `check_captcha(url)`

Check if a URL has a CAPTCHA.

```python
captcha = scraper.check_captcha("https://site.com")
if captcha:
    print(captcha.captcha_type)  # CaptchaType.RECAPTCHA_V2
    print(captcha.site_key)
```

##### `check_antibot(url)`

Check anti-bot protection on a URL.

```python
info = scraper.check_antibot("https://site.com")
if info:
    print(info.vendor)       # AntiBotVendor.CLOUDFLARE
    print(info.confidence)   # 0.95
```

##### `check_links(url, **kwargs)`

Check all links on a page and return a detailed report with status codes, categorization, and summary statistics.

```python
report = scraper.check_links("https://example.com", ignore_external=True)

print(f"Total links: {report.summary.total}")
print(f"OK: {report.summary.ok}, Broken: {report.summary.broken}")
print(f"Success rate: {report.summary.success_rate:.1f}%")
print(f"Internal: {report.summary.internal}, External: {report.summary.external}")
print(f"By type: {report.summary.by_type}")

# Per-link details
for link in report.links:
    print(f"  {link.url} -> {link.status_code} ({link.status.value})")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | str | required | Page URL to check |
| `timeout` | int/float | 5 | Per-request timeout in seconds |
| `ignore_external` | bool | False | Skip external links |
| `max_workers` | int | 10 | Concurrent threads for checking |
| `allowed_statuses` | sequence | 200-399 | HTTP codes considered "OK" |

Returns `LinkCheckReport` with:
- `report.links` — list of `SingleLinkResult` (url, status_code, status, link_type, is_external)
- `report.summary` — `LinkCheckSummary` with aggregate stats
- `report.summary.by_type` — breakdown by link type (page, image, video, etc.)

**Standalone function:**

```python
from intelliscrape import check_links

report = check_links("https://example.com")
print(f"Broken: {report.summary.broken}")
```

---

### `web_search()` — Web Search

Search DuckDuckGo, Google News, and Bing News with automatic engine fallback. Returns a structured list of results and optionally scrapes the full content of each result page in one call.

#### `web_search()` — Convenience Function

```python
from intelliscrape import web_search

report = web_search("python web scraping", limit=10)
print(f"Engine: {report.engine_used}, Results: {report.total}")

for r in report.results:
    print(f"  {r.rank}. {r.title}")
    print(f"     {r.url}")
    print(f"     {r.snippet[:100]}")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | str | required | Search query string |
| `limit` | int | 10 | Maximum number of results |
| `fetch_content` | bool | False | Scrape full text of each result URL |
| `max_concurrent` | int | 3 | Parallel workers for content fetching |
| `scraper` | IntelliScrape | None | Existing scraper instance to reuse |

Returns `WebSearchReport`:
- `report.query` — original query string
- `report.engine_used` — which engine returned results (`duckduckgo`, `google_news`, `bing_news`)
- `report.total` — number of results
- `report.results` — list of `SearchResult` objects
- `report.to_dict()` — JSON-serialisable dict

Each `SearchResult`:
- `result.rank` — 1-based position
- `result.title` — page title
- `result.url` — result URL
- `result.snippet` — short description from the SERP
- `result.content` — full scraped page text (only when `fetch_content=True`, `None` otherwise)
- `result.source` — engine that returned this result
- `result.to_dict()` — JSON-serialisable dict

**With full page content:**

```python
report = web_search("openai news", limit=5, fetch_content=True)
for r in report.results:
    if r.content:
        print(f"{r.title}: {r.content[:300]}")
```

**Export results to JSON:**

```python
from intelliscrape import web_search, DataExporter

report = web_search("python scraping", limit=10)
DataExporter.to_json([r.to_dict() for r in report.results], file="results.json")
```

#### `WebSearch` — Class

```python
from intelliscrape import WebSearch, IntelliScrape

# Reuse an existing scraper (proxies, settings, etc. carry over)
scraper = IntelliScrape(use_free_proxies=True)
ws = WebSearch(scraper=scraper)

report = ws.search("site:github.com python scraper", limit=20)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scraper` | IntelliScrape | None | Existing scraper; creates one if not provided |
| `**scraper_kwargs` | — | — | Forwarded to `IntelliScrape()` when `scraper` is not given |

**`IntelliScrape.search_web()` method:**

```python
from intelliscrape import IntelliScrape

scraper = IntelliScrape()
report = scraper.search_web("python web scraping", limit=10, fetch_content=False)
for r in report.results:
    print(r.rank, r.title, r.url)
```

##### `find_free_proxies(test=True)`

Find and test free proxies.

```python
proxies = scraper.find_free_proxies(test=True)
for p in proxies:
    print(f"{p['url']} - speed: {p['speed']:.2f}s")
```

##### `get_proxy_status()`

Get proxy manager status.

```python
status = scraper.get_proxy_status()
print(status['user_proxies'])
print(status['healthy_proxies'])
```

---

### `crawl()` — Website Crawler

```python
from intelliscrape import crawl

result = crawl(
    url="https://docs.python.org",
    max_pages=50,
    delay=0.5,
    on_page=None,  # Callback: on_page(done, failed)
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | str | required | Starting URL |
| `max_pages` | int | 50 | Maximum pages to crawl |
| `delay` | float | 0.5 | Delay between requests |
| `on_page` | callable | None | Progress callback |

Returns `CrawlResult`:
- `result.pages` — list of `ScrapeResult` (url, content, status)
- `result.failed` — list of failed pages
- `result.total_pages` — total scraped
- `result.total_failed` — total failed
- `result.to_text()` — all content as single text string

---

### `AsyncIntelliScrape` — Async Scraping

```python
import asyncio
from intelliscrape import AsyncIntelliScrape

async def main():
    async with AsyncIntelliScrape() as scraper:
        urls = [
            "https://example.com",
            "https://python.org",
            "https://github.com",
        ]
        results = await scraper.scrape_many(urls, max_concurrent=5)
        for r in results:
            print(f"{r['url']}: {len(r['content'])} chars")

asyncio.run(main())
```

Standalone async functions:

```python
from intelliscrape import scrape_async, scrape_many_async

result = await scrape_async("https://example.com")
results = await scrape_many_async(urls, max_concurrent=10)
```

---

### `DataExporter` — Export Formats

```python
from intelliscrape import DataExporter

DataExporter.to_json(data, file="output.json")
DataExporter.to_csv(data, file="output.csv")
DataExporter.to_excel(data, file="output.xlsx")
DataExporter.to_sqlite(data, file="output.db", table="scraped_data")
DataExporter.to_text(data, file="output.txt")
DataExporter.to_markdown(data, file="output.md")
DataExporter.export(data, format="json", file="output.json")
```

---

### `mirror()` — Website Mirroring

Download entire websites for offline browsing with URL rewriting, robots.txt compliance, and archive support.

```python
from intelliscrape import SiteMirror, MirrorConfig

# Quick mirror
from intelliscrape import mirror_site
result = mirror_site("https://example.com", max_depth=3)
```

#### `mirror()` — Convenience Function

```python
from intelliscrape import mirror_site

result = mirror_site(
    url="https://example.com",
    output_dir="./mirror",
    max_depth=5,
    save_zip="site.zip",
    save_warc="archive.warc.gz",
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | str | required | Starting URL |
| `output_dir` | str | `./mirror` | Output directory |
| `max_depth` | int | 5 | Max link-following depth |
| `save_zip` | str | None | Create ZIP archive at path |
| `save_warc` | str | None | Create WARC archive at path |
| `exclude_patterns` | list | [] | URL exclude patterns |
| `include_patterns` | list | [] | URL include patterns |
| `delay` | float | 0.5 | Delay between requests (seconds) |
| `respect_robots` | bool | True | Respect robots.txt |
| `engine` | str | `static` | Scraping engine |
| `proxy` | str | None | Proxy URL |

Returns `MirrorResult`:
- `result.pages_downloaded` — Number of HTML pages
- `result.assets_downloaded` — Number of assets (CSS, JS, images)
- `result.total_bytes` — Total bytes downloaded
- `result.elapsed_seconds` — Time taken
- `result.errors` — Number of errors
- `result.output_dir` — Output directory path
- `result.zip_path` — ZIP archive path (if created)
- `result.warc_path` — WARC archive path (if created)

#### `SiteMirror` — Full Control

```python
from intelliscrape.track import SiteMirror, MirrorConfig

config = MirrorConfig(
    url="https://example.com",
    max_depth=3,
    output_dir="./my-mirror",
    exclude_patterns=["*.pdf", "/admin/*"],
    engine="static",
    delay=0.5,
    respect_robots=True,
    url_mode="relative",  # relative | absolute | keep_original
)

m = SiteMirror(config)
result = m.run(save_zip="mirror.zip", save_warc="mirror.warc.gz")
```

#### `MirrorConfig` — All Options

```python
from intelliscrape.track import MirrorConfig

config = MirrorConfig(
    # What to mirror
    url="https://example.com",
    max_depth=5,
    max_pages=10000,
    max_file_size=50 * 1024 * 1024,  # 50 MB

    # Scope
    travel="same_domain",  # same_address | same_domain | same_tld | everywhere

    # What to fetch
    fetch_html=True,
    fetch_css=True,
    fetch_js=True,
    fetch_images=True,
    fetch_fonts=True,
    fetch_media=True,
    fetch_documents=True,

    # Filtering
    include_patterns=[],
    exclude_patterns=["*.pdf"],

    # Output
    output_dir="./mirror",
    url_mode="relative",
    generate_index=True,

    # Resume
    use_cache=True,
    update_mode=False,

    # Politeness
    delay=0.5,
    max_concurrent=5,
    respect_robots=True,

    # Engine & proxy
    engine="static",
    proxy=None,
    cookies=None,
)
```

#### CLI Examples

```bash
# Basic mirror
intelliscrape https://example.com --mirror

# Depth 3, custom output
intelliscrape https://example.com --mirror --mirror-depth 3 --mirror-output ./site

# With ZIP
intelliscrape https://example.com --mirror --mirror-zip backup.zip

# With WARC (web archive format)
intelliscrape https://example.com --mirror --mirror-warc archive.warc.gz

# With proxy
intelliscrape https://example.com --mirror --mirror-proxy socks5://proxy:1080

# Exclude patterns
intelliscrape https://example.com --mirror --mirror-exclude "*.pdf" --mirror-exclude "/api/*"

# Resume interrupted mirror
intelliscrape https://example.com --mirror --mirror-update
```

---

### `Downloader` — File Downloads

```python
from intelliscrape import Downloader

downloader = Downloader()

# Download linked files
results = downloader.download_links(html, base_url, "downloads/")

# Download all images
results = downloader.download_images(html, base_url, "downloads/images/")
```

---

### `Authenticator` — Login & Sessions

```python
from intelliscrape import Authenticator, LoginCredentials

auth = Authenticator()
credentials = LoginCredentials(
    username="user@example.com",
    password="secret",
)
success = auth.login("https://site.com/login", credentials)
```

---

### `FormSubmitter` — Form Interaction

```python
from intelliscrape import FormSubmitter

form_submitter = FormSubmitter()
forms = form_submitter.find_forms(html, base_url="https://site.com")
result_html = form_submitter.search(html, "query", base_url="https://site.com")
```

---

### `Paginator` — Auto-pagination

```python
from intelliscrape import Paginator

paginator = Paginator()
next_url = paginator.find_next_page(html, current_url, current_page)
```

---

### `RequestInterceptor` — Request/Response Modification

```python
from intelliscrape import RequestInterceptor

interceptor = RequestInterceptor()
interceptor.block_urls(["analytics", "tracking"])
interceptor.modify_headers({"X-Custom": "value"})
interceptor.add_response_handler(my_handler)
```

---

### `CookieManager` — Cookie Persistence

```python
from intelliscrape import CookieManager

cookie_mgr = CookieManager()
cookie_mgr.save_cookies("https://site.com", {"session": "abc123"})
cookies = cookie_mgr.load_cookies("https://site.com")
```

---

### `CaptchaDetector` & `CaptchaSolver`

```python
from intelliscrape import CaptchaDetector, CaptchaSolver

# Detect
captcha = CaptchaDetector.detect(html, url="https://site.com")

# Solve (requires API key)
solver = CaptchaSolver(provider="capsolver", api_key="YOUR_KEY")
token = solver.solve_recaptcha_v2(site_key, page_url)
token = solver.solve_hcaptcha(site_key, page_url)
token = solver.solve_turnstile(site_key, page_url)
```

---

### `AntiBotDetector` — Anti-bot Vendor Detection

```python
from intelliscrape import AntiBotDetector

info = AntiBotDetector.detect(html=html, headers=headers, cookies=cookies)
if info:
    print(info.vendor)       # AntiBotVendor.CLOUDFLARE
    print(info.confidence)   # 0.95
```

**Smart detection** uses a two-tier approach to avoid false positives:
- **Strong markers** (only on actual challenge pages): 1 match = blocked
- **Weak markers** (can appear in docs/blogs): require 3+ matches AND page <50KB
- Real challenge pages are tiny (<50KB), content pages are large — size prevents false triggers on sites like cloudflare.com that mention their own products

---

### Anti-bot Bypass Classes

```python
from intelliscrape import (
    CloudflareTurnstileBypass,
    DataDomeBypass,
    PerimeterXBypass,
    AkamaiBypass,
)
```

Each bypass class provides detection, recommended settings, and automated token solving where possible.

---

## Engine System

IntelliScrape uses a **5-tier engine escalation** system. It tries the cheapest, fastest method first and escalates only when needed.

```
Tier 1: Static (curl_cffi)        → Sub-second, TLS impersonation
    ↓ if JS-only content
Tier 2: Playwright Stealth         → 2-5s, headless Chromium + patches
    ↓ if still blocked
Tier 3: Camoufox                   → 3-8s, custom Firefox (C++ patches)
    ↓ if still blocked
Tier 4: nodriver                   → 5-15s, raw CDP, no WebDriver traces
    ↓ if still blocked
Tier 5: DrissionPage               → 5-15s, hybrid HTTP+browser mode
```

| Tier | Engine | Speed | Stealth | Best For |
|---|---|---|---|---|
| 1 | `static` | Sub-second | Low | Static sites, APIs |
| 2 | `playwright_stealth` | 2-5s | Medium | JS-heavy sites, basic bot detection |
| 3 | `camoufox` | 3-8s | High | Protected sites, fingerprint detection |
| 4 | `nodriver` | 5-15s | Maximum | DataDome, PerimeterX, Akamai |
| 5 | `drissionpage` | 5-15s | High | Hybrid HTTP+browser, fallback |

```python
# Auto-detect (default)
text = scraper.scrape("https://site.com")

# Force specific engine
text = scraper.scrape("https://site.com", engine="playwright_stealth")

# Force browser for known JS-heavy sites
text = scraper.scrape("https://react-app.com", force_browser=True)
```

```bash
# Force engine via CLI
intelliscrape https://amazon.com --engine camoufox -v

# Auto-detect with verbose progress
intelliscrape https://amazon.com -v
```

---

## Intelligent Mode

Enabled by default (`intelligent=True`). Before scraping, IntelliScrape analyzes the URL to determine:

- **Site type** — ecommerce, social, news, tech, education, etc.
- **Protection level** — none, basic, moderate, high, extreme
- **Recommended engine** — which tier to start with
- **Recommended delay** — slower for protected sites
- **Residential proxy needed** — auto-selects proxy type

```python
analysis = scraper.analyze("https://amazon.com")
print(analysis.site_type.value)         # "ecommerce"
print(analysis.protection_level.value)  # "high"
print(analysis.recommended_engine)      # "playwright_stealth"
print(analysis.requires_residential_proxy)  # True
```

---

## Features

### Anti-Detection

| Feature | Description |
|---|---|
| TLS Fingerprinting | Impersonates Chrome, Firefox, Safari (JA3/JA4) |
| Header Rotation | Randomizes HTTP headers |
| Browser Fingerprinting | Randomizes viewport, timezone, WebGL, canvas |
| Human Simulation | Bezier mouse paths, natural scrolls, realistic delays |
| Cookie Consent | Auto-handles consent banners |
| Rate Limiting | Smart delays based on site protection |
| Retry with Backoff | Exponential backoff on failures |

### CAPTCHA Solving

**Automated** (requires API key):

```python
scraper = IntelliScrape(api_key="YOUR_KEY", captcha_provider="capsolver")
result = scraper.scrape("https://protected-site.com")
```

| CAPTCHA Type | 2Captcha | CapSolver |
|---|---|---|
| reCAPTCHA v2 | Yes | Yes |
| reCAPTCHA v3 | No | Yes |
| hCaptcha | Yes | Yes |
| Cloudflare Turnstile | No | Yes |

**Manual** (opens visible browser):

```python
scraper = IntelliScrape(manual_captcha=True)
result = scraper.scrape("https://site-with-captcha.com")
# Browser opens → solve CAPTCHA → press Enter in terminal
```

```bash
intelliscrape https://site.com --manual-captcha
```

**Anti-bot challenge pages** (Cloudflare, PerimeterX, Akamai, DataDome) are automatically detected during the engine fallback chain. When detected, a browser opens for manual solving (Press and Hold, Turnstile, etc.). No API key needed.

### Proxy Configuration

```python
# Single proxy
scraper = IntelliScrape(proxy="user:pass@proxy:8080")

# Multiple proxies
scraper = IntelliScrape(proxies=["proxy1:8080", "proxy2:8080"])

# Residential proxy
scraper = IntelliScrape(brightdata_key="YOUR_KEY")

# Free proxies (automatic)
scraper = IntelliScrape(use_free_proxies=True)
```

### Export Formats

```python
from intelliscrape import DataExporter

DataExporter.to_json(data, file="output.json")
DataExporter.to_csv(data, file="output.csv")
DataExporter.to_excel(data, file="output.xlsx")
DataExporter.to_sqlite(data, file="output.db")
DataExporter.to_markdown(data, file="output.md")
```

```bash
intelliscrape https://site.com --export csv -o data.csv
intelliscrape https://site.com --export json -o data.json
```

### Website Mirroring

Download complete websites for offline browsing with URL rewriting and archive support.

```python
from intelliscrape import mirror_site

# Basic mirror
result = mirror_site("https://example.com", max_depth=3)

# With ZIP archive
result = mirror_site("https://example.com", save_zip="site.zip")

# Full options
from intelliscrape.track import SiteMirror, MirrorConfig

config = MirrorConfig(
    url="https://example.com",
    max_depth=3,
    output_dir="./mirror",
    exclude_patterns=["*.pdf", "/admin/*"],
    engine="static",
    delay=0.5,
)
m = SiteMirror(config)
result = m.run(save_zip="mirror.zip", save_warc="mirror.warc.gz")
```

```bash
# Mirror site
intelliscrape https://example.com --mirror

# Mirror with depth and output dir
intelliscrape https://example.com --mirror --mirror-depth 3 --mirror-output ./backup

# Mirror + ZIP
intelliscrape https://example.com --mirror --mirror-zip backup.zip

# Mirror + WARC (web archive format)
intelliscrape https://example.com --mirror --mirror-warc archive.warc.gz

# Mirror with proxy
intelliscrape https://example.com --mirror --mirror-proxy socks5://proxy:1080
```

---

## Examples

### Scrape React/Vue/Angular SPAs

```python
result = scraper.scrape("https://react-app.com", force_browser=True)
```

### Scrape with Custom Headers

```python
result = scraper.scrape(
    "https://api.example.com/data",
    headers={"Authorization": "Bearer token123"},
)
```

### Persistent Sessions

```python
scraper = IntelliScrape(session_profile="my_session")
scraper.scrape("https://site.com")       # Creates session
scraper.scrape("https://site.com/dashboard")  # Reuses session
```

### Download Files

```python
from intelliscrape import Downloader

downloader = Downloader()
html = scraper.scrape("https://example.com/downloads", return_raw=True)
results = downloader.download_links(html, "https://example.com", "downloads/")
```

### Batch Scraping with Export

```python
from intelliscrape import IntelliScrape, DataExporter

scraper = IntelliScrape()
urls = [f"https://example.com/page/{i}" for i in range(100)]

results = scraper.scrape_many(urls)
DataExporter.to_csv(
    [{"url": r["url"], "content": r["content"], "success": r["success"]} for r in results],
    file="results.csv",
)
```

### Check Links on a Page

```python
from intelliscrape import check_links

report = check_links("https://example.com")

# Summary
print(f"Total: {report.summary.total}")
print(f"OK: {report.summary.ok}")
print(f"Broken: {report.summary.broken}")
print(f"Success rate: {report.summary.success_rate:.1f}%")

# Only internal links
report = check_links("https://example.com", ignore_external=True)

# Export broken links
for link in report.links:
    if not link.is_ok:
        print(f"BROKEN: {link.url} -> {link.status_code}")
```

### Web Search

```python
from intelliscrape import web_search

# Basic search — returns list of results with title, URL, snippet
report = web_search("python web scraping", limit=10)
print(f"Engine: {report.engine_used}  Results: {report.total}")
for r in report.results:
    print(f"  {r.rank}. {r.title}")
    print(f"     {r.url}")

# With full page content (Firecrawl-style, one call)
report = web_search("fastapi tutorial", limit=5, fetch_content=True)
for r in report.results:
    if r.content:
        print(f"{r.title}: {r.content[:300]}")

# Export to JSON
from intelliscrape import DataExporter
DataExporter.to_json([r.to_dict() for r in report.results], file="results.json")

# Reuse an existing scraper instance (proxies, config carry over)
from intelliscrape import IntelliScrape
scraper = IntelliScrape(use_free_proxies=True)
report = scraper.search_web("site:github.com python scraper", limit=20)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Returns empty or widget text | Use `force_browser=True` — site is a JS SPA |
| CAPTCHA blocking | Use `manual_captcha=True` or `api_key` + `captcha_provider` |
| Blocked by anti-bot | Try `--engine camoufox` + residential proxy |
| Anti-bot challenge opens browser but no CAPTCHA visible | The challenge may require Press and Hold — hold the button for 3-5 seconds |
| False positive: "CAPTCHA detected" on normal site | v3.1.1+ uses smart detection — update with `pip install -U intelliscrape` |
| Playwright not installed | `pip install playwright && playwright install chromium` |
| Camoufox not installed | `pip install "camoufox[geoip]" && python -m camoufox fetch` |
| nodriver not installed | `pip install nodriver` |
| DrissionPage not installed | `pip install DrissionPage` |
| Want to see what's happening | Add `-v` flag for real-time progress output |
| Scraping too slow | Try `--engine static` for fastest results |
| Site requires login | Use `--login --username USER --password PASS` |

---

## Project Structure

```
intelliscrape/
    __init__.py             # Public API exports
    __main__.py             # python -m intelliscrape
    core.py                 # IntelliScrape class (main orchestrator)
    cli.py                  # CLI (argparse + rich)
    progress.py             # ProgressTracker, ScrapeProgress (real-time status)
    async_scraper.py        # AsyncIntelliScrape
    intelligent.py          # SiteAnalyzer, SmartRateLimiter
    auth.py                 # Authenticator, LoginCredentials
    forms.py                # FormSubmitter
    pagination.py           # Paginator
    export.py               # DataExporter
    downloader.py           # Downloader
    cookies.py              # CookieManager
    crawler.py              # crawl(), CrawlResult
    interceptor.py          # RequestInterceptor
    link_checker.py         # check_links, LinkCheckReport
    parser.py               # HTML DOM builder
    cleaner.py              # Text cleaning
    utils.py                # HTML analysis
    exceptions.py           # Exceptions

    engines/                # 5-tier scraping engines
        base.py             # BaseEngine, ScrapeResult
        static.py           # curl_cffi (Tier 1)
        playwright_stealth.py  # Playwright (Tier 2)
        camoufox.py         # Camoufox (Tier 3)
        stealth.py          # nodriver (Tier 4)
        drissionpage.py     # DrissionPage (Tier 5)

    anti_detection/         # Anti-detection subsystem
        antibot.py          # AntiBotDetector
        behavior.py         # HumanBehavior
        bypass.py           # Vendor-specific bypasses
        consent.py          # CookieConsentHandler
        fingerprint.py      # FingerprintGenerator
        headers.py          # HeaderManager
        throttle.py         # SmartThrottle, RateLimiter
        tls.py              # TLSConfig (JA3/JA4)

    challenges/             # Challenge handling
        captcha.py          # CaptchaDetector, CaptchaSolver
        manual.py           # ManualCaptchaSolver (opens visible browser)

    extractor/              # Content extraction
        structured.py       # StructuredExtractor, StructuredData

    proxy/                  # Proxy management
        __init__.py         # ProxyConfig, ProxyManager
        free_finder.py      # FreeProxyFinder
        manager.py          # IntelligentProxyManager
        providers.py        # BrightData, ScraperAPI, etc.

    session/                # Session persistence
        __init__.py         # SessionManager

    track/                  # Website mirroring (HTTrack port)
        __init__.py         # Package exports
        config.py           # MirrorConfig (30+ options)
        mirror.py           # SiteMirror engine (async workers, WARC/ZIP)
        parser.py           # AssetDiscovery (HTML/CSS/JS extraction)
        rewriter.py         # URLRewriter (relative/absolute paths)
        naming.py           # SaveNamer (URL→filesystem mapping)
        cache.py            # MirrorCache (resume support)
        filters.py          # URLFilter (include/exclude patterns)
        robots.py           # RobotsParser (RFC 9309 compliance)
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/GuixJoy/IntelliScrape.git
cd IntelliScrape/IntelliScrape_library
pip install -e ".[dev]"
pytest
```

---

## License

LGPL-2.1 License — see [LICENSE](LICENSE).

---

<div align="center">

**[PyPI](https://pypi.org/project/intelliscrape/)** · **[GitHub](https://github.com/GuixJoy/IntelliScrape)** · **[Report Issues](https://github.com/GuixJoy/IntelliScrape/issues)**

</div>

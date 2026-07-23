# IntelliScrape

[![PyPI version](https://img.shields.io/pypi/v/intelliscrape.svg)](https://pypi.org/project/intelliscrape/)
[![Python](https://img.shields.io/pypi/pyversions/intelliscrape.svg)](https://pypi.org/project/intelliscrape/)
[![Downloads](https://img.shields.io/pypi/dm/intelliscrape.svg)](https://pypi.org/project/intelliscrape/)
[![License](https://img.shields.io/pypi/l/intelliscrape.svg)](https://github.com/GuixJoy/IntelliScrape/blob/main/LICENSE)

**The Python scraper that actually works.**

Stop fighting with anti-bot systems. IntelliScrape handles the hard stuff so you can focus on your data.

<div align="center">
  <img src="demo.gif" alt="IntelliScrape Demo" width="800">
</div>

---

## What is this?

IntelliScrape is a Python web scraping library that **scrapes 98% of websites** out of the box. It automatically picks the best engine, bypasses basic anti-bot detection, and gives you clean text — all with a single function call.

No more switching between `requests`, `playwright`, and `selenium`. No more debugging why your scraper got blocked. Just `scrape(url)` and you're done.

---

## Installation

```bash
pip install intelliscrape
```

That's it. The core library handles most sites. For protected sites:

```bash
# For stealth browsing (bypasses bot detection)
pip install intelliscrape[stealth]

# For CAPTCHA solving
pip install intelliscrape[captcha]

# Everything
pip install intelliscrape[all]
```

---

## Quick Start

### One-liner

```python
from intelliscrape import scrape

text = scrape("https://news.ycombinator.com")
print(text[:500])
```

### Get structured data (title, description, meta tags)

```python
from intelliscrape import IntelliScrape

scraper = IntelliScrape()
data = scraper.get_structured("https://github.com")

print(data.title)
print(data.description)
print(data.og_data)
```

### Scrape with proxy

```python
scraper = IntelliScrape(proxy="user:pass@proxy:8080")
text = scraper.scrape("https://protected-site.com")
```

### Crawl entire website

```python
from intelliscrape import crawl

result = crawl("https://docs.python.org", max_pages=100)
print(f"Scraped {result.total_pages} pages")

for page in result.pages:
    print(f"{page.url}: {len(page.content)} chars")
```

---

## CLI Usage

```bash
# Basic scrape
intelliscrape https://example.com

# Save to file
intelliscrape https://site.com --output result.txt

# Get structured JSON
intelliscrape https://site.com --structured --output data.json

# Stealth mode for protected sites
intelliscrape https://site.com --engine stealth

# With proxy
intelliscrape https://site.com --proxy user:pass@proxy:8080

# Crawl entire site
intelliscrape https://site.com --crawl --max-pages 100

# Check what anti-bot protection a site uses
intelliscrape https://site.com --check-antibot
```

---

## Features

| Feature | Status |
|---|---|
| Automatic static/dynamic detection | ✅ |
| TLS fingerprint impersonation | ✅ |
| Browser fingerprint randomization | ✅ |
| Human-like behavioral simulation | ✅ |
| Proxy rotation | ✅ |
| CAPTCHA detection & solving | ✅ |
| Smart retry with backoff | ✅ |
| Rate limiting | ✅ |
| Anti-bot vendor detection | ✅ |
| Cookie consent handling | ✅ |
| Structured data extraction | ✅ |
| Session persistence | ✅ |
| Multiple export formats | ✅ |
| Async support | ✅ |

---

## How It Works

```
scrape(url)
    ↓
┌─────────────────────────────┐
│   Engine Selection (auto)   │
│  ┌─────────┐ ┌───────────┐  │
│  │ Static  │ │ Stealth   │  │
│  │curl_cffi│ │Playwright │  │
│  └─────────┘ └───────────┘  │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│    Anti-Detection Layer     │
│  • TLS impersonation        │
│  • Header rotation          │
│  • Fingerprint randomize    │
│  • Behavioral simulation    │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│      Smart Pipeline         │
│  • Retry with backoff       │
│  • Rate limiting            │
│  • Anti-bot detection       │
│  • Cookie consent           │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│      Content Extraction     │
│  • Text extraction          │
│  • Structured data (JSON)   │
│  • Clean output             │
└─────────────────────────────┘
    ↓
  Clean Text / JSON
```

---

## What Sites Can It Scrape?

### Works Great ✅
- Wikipedia, Python.org, MDN
- GitHub, GitLab, Bitbucket
- Hacker News, Reddit (most pages)
- News sites (BBC, CNN, Reuters)
- Documentation sites
- Blogs (WordPress, Ghost, Hugo)
- E-commerce (basic)

### Works with Stealth Mode 🛡️
- Cloudflare-protected sites
- Sites with bot detection
- JavaScript-heavy SPAs
- Dynamic content sites

### Needs Proxy + CAPTCHA Solver 🔐
- LinkedIn
- Amazon
- Twitter/X
- Instagram
- Highly protected platforms

---

## Engine Selection

| Engine | When to Use | Dependencies |
|---|---|---|
| `static` | Default, fast, most sites | `curl_cffi` |
| `playwright_stealth` | JS-heavy, basic bot detection | `playwright` |
| `nodriver` | Protected sites, advanced bypass | `nodriver` |

```python
# Force a specific engine
scraper = IntelliScrape()
text = scraper.scrape("https://site.com", engine="playwright_stealth")
```

---

## For Data Analysts

IntelliScrape is built with data workflows in mind:

```python
from intelliscrape import IntelliScrape
import json

scraper = IntelliScrape()

# Scrape multiple pages
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
]

results = scraper.scrape_many(urls)

# Save as JSON
with open("data.json", "w") as f:
    json.dump(results, f, indent=2)

# Get structured data for analysis
for url in urls:
    data = scraper.get_structured(url)
    print(f"{data.title} | {data.author} | {data.date_published}")
```

### Export to different formats

```bash
# JSON
intelliscrape https://site.com --structured --output data.json

# Text
intelliscrape https://site.com --output content.txt

# Crawl and save
intelliscrape https://docs.python.org --crawl --max-pages 50 --output docs.txt
```

---

## Advanced Configuration

```python
from intelliscrape import IntelliScrape

scraper = IntelliScrape(
    # Proxy
    proxy="user:pass@proxy:8080",
    
    # CAPTCHA solving
    api_key="your_2captcha_or_capsolver_key",
    captcha_provider="capsolver",
    
    # Browser settings
    headless=True,
    simulate_behavior=True,
    
    # Rate limiting
    min_delay=0.5,
    max_delay=3.0,
    requests_per_minute=30,
    
    # TLS fingerprint
    tls_profile="chrome131",
    
    # Session persistence
    session_profile="my_session",
    
    # Logging
    log_level="INFO",
)
```

---

## Project Structure

```
intelliscrape/
├── core.py                  # Main API
├── cli.py                   # Command line
├── engines/
│   ├── static.py            # curl_cffi (TLS bypass)
│   ├── playwright_stealth.py # Playwright + patches
│   └── stealth.py           # nodriver (advanced)
├── anti_detection/
│   ├── headers.py           # Header rotation
│   ├── tls.py               # TLS profiles
│   ├── fingerprint.py       # Browser fingerprinting
│   ├── behavior.py          # Human simulation
│   ├── antibot.py           # Vendor detection
│   ├── throttle.py          # Retry & rate limit
│   └── consent.py           # Cookie consent
├── challenges/
│   └── captcha.py           # CAPTCHA solving
├── proxy/
│   └── __init__.py          # Proxy management
├── session/
│   └── __init__.py          # Session persistence
├── extractor/
│   ├── __init__.py          # Text extraction
│   └── structured.py        # JSON-LD, meta tags
├── exporters/
│   └── __init__.py          # TXT, JSON, CSV, MD
├── crawler.py               # Website crawler
├── parser.py                # HTML parser
├── cleaner.py               # Text cleaning
└── utils.py                 # Utilities
```

---

## Contributing

We welcome contributions! Whether it's:
- New anti-bot bypass patterns
- CAPTCHA solving techniques
- Proxy provider integrations
- Bug fixes
- Documentation

Check out [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## Community

- **GitHub Issues:** [Report bugs](https://github.com/GuixJoy/IntelliScrape/issues)
- **Discussions:** [Ask questions](https://github.com/GuixJoy/IntelliScrape/discussions)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built with ❤️ for the data community.**

---

## Generating the Demo GIF

To regenerate the demo GIF:

```bash
# Install vhs (macOS)
brew install charmbracelet/tap/vhs

# Or using Go
go install github.com/charmbracelet/vhs@latest

# Generate the GIF
vhs demo.tape
```

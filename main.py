"""FastAPI backend for IntelliScrape web service.

This is a standalone web backend - it does NOT depend on the intelliscrape
Python library. It uses curl_cffi and playwright directly for scraping.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging
import json
import os
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    curl_requests = None
    CURL_AVAILABLE = False

CLOUDFLARE_MARKERS = [
    "checking your browser", "just a moment", "challenge-platform",
    "cf-browser-verification", "enable javascript", "verify you are human",
    "security check", "please wait", "turnstile", "challenge.js",
]


def _is_cloudflare_blocked(html: str) -> bool:
    """Check if response is a Cloudflare challenge page."""
    lower = html.lower()
    return any(marker in lower for marker in CLOUDFLARE_MARKERS)


STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'permissions', {
    get: () => ({query: (p) => Promise.resolve({state: 'denied', onchange: null})})
});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'connection', {
    get: () => ({rtt: 50, downlink: 10, effectiveType: '4g', saveData: false})
});
"""

try:
    import psycopg
    DB_AVAILABLE = True
except ImportError:
    psycopg = None
    DB_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEB_VERSION = "3.1.1"

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and "channel_binding=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
    logger.info("Stripped channel_binding=require from DATABASE_URL")


def get_db():
    return psycopg.connect(DATABASE_URL, autocommit=True)


def init_db():
    if not DATABASE_URL or not DB_AVAILABLE:
        if not DB_AVAILABLE:
            logger.warning("psycopg not available - scrape logging disabled")
        else:
            logger.warning("DATABASE_URL not set - scrape logging disabled")
        return
    try:
        logger.info(f"Connecting to Neon DB (url prefix: {DATABASE_URL[:30]}...)")
        conn = get_db()
        logger.info("Neon DB connection successful")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'scrapes' AND column_name = 'fingerprint'
                )
            """)
            has_old_col = cur.fetchone()[0]

            if has_old_col:
                cur.execute("DROP TABLE IF EXISTS scrapes CASCADE")
                logger.info("Dropped old scrapes table for schema migration")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS scrapes (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    content_preview TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    fp_hash TEXT,
                    confidence_score DOUBLE PRECISION,
                    incognito BOOLEAN,
                    incognito_browser TEXT,
                    is_bot BOOLEAN,
                    bot_signals JSONB,
                    bot_confidence DOUBLE PRECISION,
                    browser_name TEXT,
                    browser_version TEXT,
                    user_agent TEXT,
                    platform TEXT,
                    screen_width INT,
                    screen_height INT,
                    color_depth INT,
                    color_gamut TEXT,
                    hardware_concurrency INT,
                    device_memory INT,
                    os_name TEXT,
                    os_version TEXT,
                    local_storage BOOLEAN,
                    session_storage BOOLEAN,
                    indexed_db BOOLEAN,
                    audio DOUBLE PRECISION,
                    webgl_vendor TEXT,
                    webgl_renderer TEXT,
                    webgl_image_hash TEXT,
                    canvas_winding BOOLEAN,
                    canvas_geometry TEXT,
                    canvas_text TEXT,
                    plugins JSONB,
                    languages JSONB,
                    cookies_enabled BOOLEAN,
                    do_not_track TEXT,
                    timezone TEXT,
                    touch_max_points INT,
                    touch_event BOOLEAN,
                    touch_start BOOLEAN,
                    vendor TEXT,
                    vendor_flavors JSONB,
                    math_constants JSONB,
                    detected_fonts JSONB,
                    device_type JSONB,
                    enhanced JSONB,
                    ip_address TEXT,
                    ipv4 TEXT,
                    ipv6 TEXT,
                    city TEXT,
                    region_code TEXT,
                    region_name TEXT,
                    country_iso TEXT,
                    country_name TEXT,
                    continent_code TEXT,
                    continent_name TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    geo_accuracy INT,
                    geo_timezone TEXT,
                    is_anonymous BOOLEAN,
                    is_anonymous_proxy BOOLEAN,
                    is_anonymous_vpn BOOLEAN,
                    network TEXT,
                    vpn_status JSONB
                )
            """)
        conn.close()
        logger.info("Database initialized - scrapes table ready")
    except Exception as e:
        logger.error(f"Database init failed: {e}")


app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version=WEB_VERSION,
)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "https://intelliscrape.dev,https://www.intelliscrape.dev,http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_playwright_browsers():
    """Install Playwright browsers if not already present."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.info("Playwright chromium browser installed successfully")
        else:
            logger.warning(f"Playwright install returned code {result.returncode}: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"Playwright browser install failed: {e}")


@app.on_event("startup")
def startup():
    init_db()
    _ensure_playwright_browsers()


class ScrapeRequest(BaseModel):
    url: HttpUrl
    raw: bool = False
    render: bool = False
    fingerprint: Optional[dict] = None


class ScrapeResponse(BaseModel):
    url: str
    content: str
    success: bool = True


class TechRequest(BaseModel):
    url: HttpUrl
    render: bool = False


class TechResponse(BaseModel):
    url: str
    tech: dict
    server_headers: dict = {}
    success: bool = True


def scrape_basic(url: str, raw: bool = False, render_js: bool = False) -> str:
    """Scrape using curl_cffi with auto-fallback to stealth browser for Cloudflare."""
    if render_js:
        return _scrape_with_stealth(url, raw)

    if not CURL_AVAILABLE:
        raise Exception("curl_cffi not available - cannot scrape")

    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome131",
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        raise Exception(f"Request failed: {str(e)}")

    html = resp.text
    content_type = resp.headers.get("content-type", "")

    if raw:
        return html

    if "json" in content_type:
        return html

    if _is_cloudflare_blocked(html):
        logging.info("Cloudflare detected, falling back to stealth browser")
        return _scrape_with_stealth(url, raw)

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string if soup.title else ""
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_desc = meta.get("content", "")

    body = soup.find("body")
    if body:
        for tag in body(["nav", "footer", "header"]):
            tag.decompose()
        text = body.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if meta_desc:
        parts.append(f"Description: {meta_desc}")
    parts.append("")
    parts.append(text)

    return "\n".join(parts)


def fetch_raw(url: str, render_js: bool = False) -> tuple[str, dict[str, str]]:
    """Fetch raw HTML and response headers for tech detection.

    Returns (html, headers_dict).
    """
    if render_js:
        return _fetch_raw_stealth(url)

    if not CURL_AVAILABLE:
        raise Exception("curl_cffi not available - cannot fetch")

    resp = curl_requests.get(
        url,
        impersonate="chrome131",
        timeout=30,
        allow_redirects=True,
    )
    resp.raise_for_status()
    html = resp.text
    if _is_cloudflare_blocked(html):
        logging.info("Cloudflare detected in fetch_raw, falling back to stealth browser")
        return _fetch_raw_stealth(url)
    return html, dict(resp.headers)


def _fetch_raw_stealth(url: str) -> tuple[str, dict[str, str]]:
    """Fetch raw HTML with stealth browser, returning (html, headers)."""
    # Try Playwright with stealth
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080",
                    "--excludeSwitches=enable-automation",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = context.new_page()
            page.add_init_script(STEALTH_JS)
            response_headers: dict[str, str] = {}
            def on_response(resp):
                nonlocal response_headers
                if resp.url == url or resp.url.rstrip("/") == url.rstrip("/"):
                    try:
                        response_headers = resp.headers
                    except Exception:
                        pass
            page.on("response", on_response)
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
            if html and not _is_cloudflare_blocked(html):
                return html, response_headers
    except Exception as e:
        logging.warning(f"Playwright stealth fetch failed: {e}")

    # Try Camoufox
    try:
        from camoufox.sync_api import Camoufox
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            if html and not _is_cloudflare_blocked(html):
                return html, {}
    except Exception as e:
        logging.warning(f"Camoufox fetch failed: {e}")

    # Fallback to plain playwright
    return _fetch_raw_playwright(url)


def _fetch_raw_playwright(url: str) -> tuple[str, dict[str, str]]:
    """Fetch raw HTML via Playwright, returning (html, headers)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise Exception("Playwright not installed - JS rendering unavailable")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        response_headers: dict[str, str] = {}
        def on_response(resp):
            nonlocal response_headers
            if resp.url == url or resp.url.rstrip("/") == url.rstrip("/"):
                try:
                    response_headers = resp.headers
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()

    return html, response_headers


def _scrape_with_stealth(url: str, raw: bool = False) -> str:
    """Scrape with stealth browser fallback: Playwright → Camoufox → Nodriver."""
    html = None

    # Try Playwright with stealth patches
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080",
                    "--excludeSwitches=enable-automation",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = context.new_page()
            page.add_init_script(STEALTH_JS)
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
            if html and not _is_cloudflare_blocked(html):
                return html if raw else _clean_html(html)
    except Exception as e:
        logging.warning(f"Playwright stealth failed: {e}")

    # Try Camoufox (Firefox-based, harder to detect)
    try:
        from camoufox.sync_api import Camoufox
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            if html and not _is_cloudflare_blocked(html):
                return html if raw else _clean_html(html)
    except Exception as e:
        logging.warning(f"Camoufox failed: {e}")

    # Try Nodriver (undetected-chromedriver successor)
    try:
        import nodriver as uc
        import asyncio

        async def _nodriver_fetch():
            browser = await uc.start(headless=True)
            page = await browser.get(url)
            await page.sleep(5)
            content = await page.get_content()
            await browser.stop()
            return content

        html = asyncio.run(_nodriver_fetch())
        if html and not _is_cloudflare_blocked(html):
            return html if raw else _clean_html(html)
    except Exception as e:
        logging.warning(f"Nodriver failed: {e}")

    if html:
        return html if raw else _clean_html(html)
    raise Exception("All stealth engines failed to bypass Cloudflare")


def _clean_html(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string if soup.title else ""
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_desc = meta.get("content", "")

    body = soup.find("body")
    if body:
        for tag in body(["nav", "footer", "header"]):
            tag.decompose()
        text = body.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if meta_desc:
        parts.append(f"Description: {meta_desc}")
    parts.append(f"\nContent:\n{text}")

    return "\n".join(parts)


def scrape_with_playwright(url: str, raw: bool = False) -> str:
    """Render JavaScript using Playwright with stealth patches."""
    return _scrape_with_stealth(url, raw)

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if meta_desc:
        parts.append(f"Description: {meta_desc}")
    parts.append("")
    parts.append(text)

    return "\n".join(parts)


def store_scrape(url: str, content: str, fingerprint: Optional[dict], ip_address: str, user_agent: str):
    """Store scrape record in Neon DB with all fingerprint attributes."""
    if not DATABASE_URL or not DB_AVAILABLE:
        return
    fp = fingerprint or {}
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scrapes (
                    url, content_preview,
                    fp_hash, confidence_score,
                    incognito, incognito_browser,
                    is_bot, bot_signals, bot_confidence,
                    browser_name, browser_version, user_agent, platform,
                    screen_width, screen_height, color_depth, color_gamut,
                    hardware_concurrency, device_memory,
                    os_name, os_version,
                    local_storage, session_storage, indexed_db,
                    audio, webgl_vendor, webgl_renderer, webgl_image_hash,
                    canvas_winding, canvas_geometry, canvas_text,
                    plugins, languages, cookies_enabled, do_not_track,
                    timezone, touch_max_points, touch_event, touch_start,
                    vendor, vendor_flavors,
                    math_constants, detected_fonts, device_type, enhanced,
                    ip_address, ipv4, ipv6,
                    city, region_code, region_name,
                    country_iso, country_name, continent_code, continent_name,
                    latitude, longitude, geo_accuracy, geo_timezone,
                    is_anonymous, is_anonymous_proxy, is_anonymous_vpn,
                    network, vpn_status
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s
                )""",
                (
                    url,
                    content[:500] if content else None,
                    fp.get("hash"),
                    fp.get("confidenceScore"),
                    fp.get("incognito"),
                    fp.get("incognitoBrowser"),
                    fp.get("isBot"),
                    json.dumps(fp.get("botSignals")) if fp.get("botSignals") else None,
                    fp.get("botConfidence"),
                    fp.get("browserName"),
                    fp.get("browserVersion"),
                    user_agent,
                    fp.get("platform"),
                    fp.get("screenW"),
                    fp.get("screenH"),
                    fp.get("colorDepth"),
                    fp.get("colorGamut"),
                    fp.get("hardwareConcurrency"),
                    fp.get("deviceMemory"),
                    fp.get("osName"),
                    fp.get("osVersion"),
                    fp.get("localStorage"),
                    fp.get("sessionStorage"),
                    fp.get("indexedDB"),
                    fp.get("audio"),
                    fp.get("webGLVendor"),
                    fp.get("webGLRenderer"),
                    fp.get("webGLImageHash"),
                    fp.get("canvasWinding"),
                    fp.get("canvasGeometry"),
                    fp.get("canvasText"),
                    json.dumps(fp.get("plugins")) if fp.get("plugins") else None,
                    json.dumps(fp.get("languages")) if fp.get("languages") else None,
                    fp.get("cookiesEnabled"),
                    fp.get("doNotTrack"),
                    fp.get("timezone"),
                    fp.get("touchMaxPoints"),
                    fp.get("touchEvent"),
                    fp.get("touchStart"),
                    fp.get("vendor"),
                    json.dumps(fp.get("vendorFlavors")) if fp.get("vendorFlavors") else None,
                    json.dumps(fp.get("mathConstants")) if fp.get("mathConstants") else None,
                    json.dumps(fp.get("detectedFonts")) if fp.get("detectedFonts") else None,
                    json.dumps(fp.get("deviceType")) if fp.get("deviceType") else None,
                    json.dumps(fp.get("enhanced")) if fp.get("enhanced") else None,
                    ip_address,
                    fp.get("ipv4"),
                    fp.get("ipv6"),
                    fp.get("city"),
                    fp.get("regionCode"),
                    fp.get("regionName"),
                    fp.get("countryIso"),
                    fp.get("countryName"),
                    fp.get("continentCode"),
                    fp.get("continentName"),
                    fp.get("latitude"),
                    fp.get("longitude"),
                    fp.get("geoAccuracy"),
                    fp.get("geoTimeZone"),
                    fp.get("isAnonymous"),
                    fp.get("isAnonymousProxy"),
                    fp.get("isAnonymousVpn"),
                    fp.get("network"),
                    json.dumps(fp.get("vpnStatus")) if fp.get("vpnStatus") else None,
                ),
            )
        conn.close()
    except Exception as e:
        logger.error(f"Failed to store scrape: {type(e).__name__}: {e}")


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": WEB_VERSION,
        "endpoints": {
            "scrape": "POST /scrape",
            "tech": "POST /tech",
            "detect_api": "POST /detect-api",
            "health": "GET /health",
            "version": "GET /version",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": WEB_VERSION, "db": "connected" if (DATABASE_URL and DB_AVAILABLE) else "unconfigured"}


@app.get("/version")
def version():
    try:
        from playwright.sync_api import sync_playwright
        playwright_ok = True
    except ImportError:
        playwright_ok = False
    return {"version": WEB_VERSION, "engine": "standalone", "dependencies": {"curl_cffi": CURL_AVAILABLE, "psycopg": DB_AVAILABLE, "playwright": playwright_ok}}


@app.post("/scrape")
def scrape_url(req: ScrapeRequest, request: Request):
    """Scrape a website and return clean text."""
    url_str = str(req.url)
    logger.info(f"Scrape request: {url_str}")
    try:
        content = scrape_basic(url_str, raw=req.raw, render_js=req.render)
        if not content or len(content.strip()) == 0:
            raise Exception("Empty response from target website")
        logger.info(f"Scrape success: {url_str} ({len(content)} chars)")

        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        store_scrape(url_str, content, req.fingerprint, ip_address, user_agent)

        return ScrapeResponse(url=url_str, content=content)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Scrape failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


@app.post("/tech")
def detect_tech(req: TechRequest):
    """Detect website technology stack (frameworks, CMS, analytics, CDN, etc)."""
    url_str = str(req.url)
    logger.info(f"Tech detection request: {url_str}")
    try:
        from intelliscrape.tech import TechStackExtractor
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="intelliscrape.tech module not installed. Run: pip install intelliscrape",
        )

    try:
        html, headers = fetch_raw(url_str, render_js=req.render)
        if not html:
            raise Exception("Empty response from target website")

        tech = TechStackExtractor.extract(
            html=html,
            headers=headers,
            url=url_str,
        )

        interesting_headers = {
            k: v for k, v in tech.headers.items()
            if k.lower() in (
                "server", "x-powered-by", "x-generator",
                "via", "x-amz-cf-pop", "x-vercel",
                "cf-ray", "x-shopify-stage",
            )
        }

        logger.info(f"Tech detection success: {url_str} ({len(tech.all_tech)} technologies)")
        return TechResponse(
            url=url_str,
            tech=tech.to_dict(),
            server_headers=interesting_headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Tech detection failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


class DetectApiRequest(BaseModel):
    url: HttpUrl
    render: bool = False


class DetectApiResponse(BaseModel):
    url: str
    endpoints: list = []
    key_exposures: list = []
    third_party_apis: list = []
    documentation: list = []
    summary: dict = {}
    success: bool = True


@app.post("/detect-api")
def detect_api(req: DetectApiRequest):
    """Detect API endpoints, third-party services, and exposed keys."""
    url_str = str(req.url)
    logger.info(f"API detection request: {url_str}")
    try:
        from intelliscrape.api_detector import ApiDetector
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="intelliscrape.api_detector module not installed. Run: pip install intelliscrape",
        )

    try:
        html, headers = fetch_raw(url_str, render_js=req.render)
        if not html:
            raise Exception("Empty response from target website")

        report = ApiDetector.extract(
            html=html,
            headers=headers,
            url=url_str,
        )

        logger.info(f"API detection success: {url_str} ({len(report.endpoints)} endpoints, {len(report.third_party_apis)} services)")
        return DetectApiResponse(
            url=url_str,
            endpoints=[ep.to_dict() for ep in report.endpoints],
            key_exposures=[k.to_dict() for k in report.key_exposures],
            third_party_apis=report.third_party_apis,
            documentation=report.documentation,
            summary=report.summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"API detection failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

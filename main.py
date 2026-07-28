"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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

try:
    import psycopg
    DB_AVAILABLE = True
except ImportError:
    psycopg = None
    DB_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and "channel_binding=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
    logger.info("Stripped channel_binding=require from DATABASE_URL (psycopg2 incompatible)")

def get_db():
    return psycopg.connect(DATABASE_URL, autocommit=True)

def init_db():
    if not DATABASE_URL or not DB_AVAILABLE:
        if not DB_AVAILABLE:
            logger.warning("psycopg not available — scrape logging disabled")
        else:
            logger.warning("DATABASE_URL not set — scrape logging disabled")
        return
    try:
        logger.info(f"Connecting to Neon DB (url prefix: {DATABASE_URL[:30]}...)")
        conn = get_db()
        logger.info("Neon DB connection successful")
        with conn.cursor() as cur:
            # Check if old schema exists (has 'fingerprint' column)
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'scrapes' AND column_name = 'fingerprint'
                )
            """)
            has_old_col = cur.fetchone()[0]

            if has_old_col:
                # Drop old table and recreate with new schema
                cur.execute("DROP TABLE IF EXISTS scrapes CASCADE")
                logger.info("Dropped old scrapes table for schema migration")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS scrapes (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    content_preview TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),

                    -- top-level
                    fp_hash TEXT,
                    confidence_score DOUBLE PRECISION,

                    -- incognito
                    incognito BOOLEAN,
                    incognito_browser TEXT,

                    -- bot detection
                    is_bot BOOLEAN,
                    bot_signals JSONB,
                    bot_confidence DOUBLE PRECISION,

                    -- browser
                    browser_name TEXT,
                    browser_version TEXT,
                    user_agent TEXT,
                    platform TEXT,

                    -- display
                    screen_width INT,
                    screen_height INT,
                    color_depth INT,
                    color_gamut TEXT,

                    -- hardware
                    hardware_concurrency INT,
                    device_memory INT,

                    -- os
                    os_name TEXT,
                    os_version TEXT,

                    -- storage
                    local_storage BOOLEAN,
                    session_storage BOOLEAN,
                    indexed_db BOOLEAN,

                    -- media
                    audio DOUBLE PRECISION,
                    webgl_vendor TEXT,
                    webgl_renderer TEXT,
                    webgl_image_hash TEXT,
                    canvas_winding BOOLEAN,
                    canvas_geometry TEXT,
                    canvas_text TEXT,

                    -- plugins & languages
                    plugins JSONB,
                    languages JSONB,
                    cookies_enabled BOOLEAN,
                    do_not_track TEXT,

                    -- timezone & touch
                    timezone TEXT,
                    touch_max_points INT,
                    touch_event BOOLEAN,
                    touch_start BOOLEAN,

                    -- vendor
                    vendor TEXT,
                    vendor_flavors JSONB,

                    -- math & fonts
                    math_constants JSONB,
                    detected_fonts JSONB,

                    -- device type
                    device_type JSONB,

                    -- enhanced fingerprint
                    enhanced JSONB,

                    -- geolocation
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
        logger.info("Database initialized — scrapes table ready")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version="2.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()


class ScrapeRequest(BaseModel):
    url: HttpUrl
    raw: bool = False
    render: bool = False
    fingerprint: Optional[dict] = None


class ScrapeResponse(BaseModel):
    url: str
    content: str
    success: bool = True


class ScrapeLog(BaseModel):
    id: int
    url: str
    content_preview: Optional[str]
    created_at: str
    # fingerprint - top level
    fp_hash: Optional[str] = None
    confidence_score: Optional[float] = None
    # incognito
    incognito: Optional[bool] = None
    incognito_browser: Optional[str] = None
    # bot
    is_bot: Optional[bool] = None
    bot_signals: Optional[list] = None
    bot_confidence: Optional[float] = None
    # browser
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    user_agent: Optional[str] = None
    platform: Optional[str] = None
    # display
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    color_depth: Optional[int] = None
    color_gamut: Optional[str] = None
    # hardware
    hardware_concurrency: Optional[int] = None
    device_memory: Optional[int] = None
    # os
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    # storage
    local_storage: Optional[bool] = None
    session_storage: Optional[bool] = None
    indexed_db: Optional[bool] = None
    # media
    audio: Optional[float] = None
    webgl_vendor: Optional[str] = None
    webgl_renderer: Optional[str] = None
    webgl_image_hash: Optional[str] = None
    canvas_winding: Optional[bool] = None
    canvas_geometry: Optional[str] = None
    canvas_text: Optional[str] = None
    # plugins & languages
    plugins: Optional[list] = None
    languages: Optional[list] = None
    cookies_enabled: Optional[bool] = None
    do_not_track: Optional[str] = None
    # timezone & touch
    timezone: Optional[str] = None
    touch_max_points: Optional[int] = None
    touch_event: Optional[bool] = None
    touch_start: Optional[bool] = None
    # vendor
    vendor: Optional[str] = None
    vendor_flavors: Optional[list] = None
    # math & fonts
    math_constants: Optional[dict] = None
    detected_fonts: Optional[list] = None
    # device type
    device_type: Optional[dict] = None
    # enhanced
    enhanced: Optional[dict] = None
    # geolocation
    ip_address: Optional[str] = None
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    city: Optional[str] = None
    region_code: Optional[str] = None
    region_name: Optional[str] = None
    country_iso: Optional[str] = None
    country_name: Optional[str] = None
    continent_code: Optional[str] = None
    continent_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_accuracy: Optional[int] = None
    geo_timezone: Optional[str] = None
    is_anonymous: Optional[bool] = None
    is_anonymous_proxy: Optional[bool] = None
    is_anonymous_vpn: Optional[bool] = None
    network: Optional[str] = None
    vpn_status: Optional[dict] = None


class StatsResponse(BaseModel):
    total_scrapes: int
    unique_urls: int
    unique_hashes: int
    unique_countries: int
    bot_detected: int
    top_browsers: dict
    top_os: dict
    top_countries: dict


def scrape_basic(url: str, raw: bool = False, render_js: bool = False) -> str:
    """Scrape using curl_cffi (TLS impersonation) with optional Playwright JS rendering."""

    if render_js:
        return scrape_with_playwright(url, raw)

    if not CURL_AVAILABLE:
        raise Exception("curl_cffi not available — cannot scrape")

    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome",
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        raise Exception(f"Request failed: {str(e)}")

    content_type = resp.headers.get("content-type", "")

    if raw:
        return resp.text

    if "json" in content_type:
        return resp.text

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string if soup.title else ""

    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_desc = meta.get("content", "")

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if meta_desc:
        parts.append(f"Description: {meta_desc}")
    parts.append("")
    parts.append(text)

    return "\n".join(parts)


def scrape_with_playwright(url: str, raw: bool = False) -> str:
    """Render JavaScript using Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise Exception("Playwright not installed — JS rendering unavailable")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        content = page.content()
        browser.close()

    if raw:
        return content

    soup = BeautifulSoup(content, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string if soup.title else ""

    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_desc = meta.get("content", "")

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

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
        logger.warning(f"store_scrape skipped: DB_AVAILABLE={DB_AVAILABLE}, DATABASE_URL={'set' if DATABASE_URL else 'unset'}")
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
                    %s,%s,%s,%s,%s
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
        logger.info(f"Scrape stored: {url[:80]}")
    except Exception as e:
        logger.error(f"Failed to store scrape: {type(e).__name__}: {e}")


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": "2.3.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "scrapes": "GET /scrapes",
            "stats": "GET /stats",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.3.0"}


@app.get("/debug/db")
def debug_db():
    """Diagnose database connection state."""
    info = {
        "psycopg_imported": DB_AVAILABLE,
        "database_url_set": bool(DATABASE_URL),
        "database_url_prefix": (DATABASE_URL[:40] + "...") if DATABASE_URL else None,
        "has_channel_binding": "channel_binding" in (DATABASE_URL or ""),
    }
    if not DATABASE_URL:
        info["error"] = "DATABASE_URL env var not set"
        return info
    if not DB_AVAILABLE:
        info["error"] = "psycopg import failed"
        return info
    try:
        conn = psycopg.connect(DATABASE_URL, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            pg_version = cur.fetchone()[0]
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'scrapes')")
            table_exists = cur.fetchone()[0]
            if table_exists:
                cur.execute("SELECT COUNT(*) FROM scrapes")
                row_count = cur.fetchone()[0]
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'scrapes' ORDER BY ordinal_position")
                columns = [r[0] for r in cur.fetchall()]
            else:
                row_count = None
                columns = []
        conn.close()
        info["pg_version"] = pg_version
        info["table_exists"] = table_exists
        info["row_count"] = row_count
        info["column_count"] = len(columns)
        info["status"] = "connected"
    except Exception as e:
        info["status"] = "error"
        info["error"] = f"{type(e).__name__}: {e}"
    return info


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


@app.get("/scrapes")
def get_scrapes(limit: int = 100):
    """Get recent scrape logs with all fingerprint attributes."""
    if not DATABASE_URL or not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM scrapes ORDER BY created_at DESC LIMIT %s""",
                (min(limit, 500),),
            )
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            # Serialize non-JSON-friendly types
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
                elif isinstance(v, (dict, list)):
                    d[k] = v  # psycopg returns dicts/lists for JSONB
            result.append(d)
        return result
    except Exception as e:
        logger.error(f"Failed to fetch scrapes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    """Get scrape statistics with fingerprint analytics."""
    if not DATABASE_URL or not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scrapes")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT url) FROM scrapes")
            unique = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT fp_hash) FROM scrapes WHERE fp_hash IS NOT NULL")
            unique_hashes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT country_iso) FROM scrapes WHERE country_iso IS NOT NULL")
            unique_countries = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM scrapes WHERE is_bot = true")
            bot_detected = cur.fetchone()[0]
            # Top browsers
            cur.execute("SELECT browser_name, COUNT(*) as c FROM scrapes WHERE browser_name IS NOT NULL GROUP BY browser_name ORDER BY c DESC LIMIT 5")
            top_browsers = {r[0]: r[1] for r in cur.fetchall()}
            # Top OS
            cur.execute("SELECT os_name, COUNT(*) as c FROM scrapes WHERE os_name IS NOT NULL GROUP BY os_name ORDER BY c DESC LIMIT 5")
            top_os = {r[0]: r[1] for r in cur.fetchall()}
            # Top countries
            cur.execute("SELECT country_name, COUNT(*) as c FROM scrapes WHERE country_name IS NOT NULL GROUP BY country_name ORDER BY c DESC LIMIT 10")
            top_countries = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()
        return StatsResponse(
            total_scrapes=total,
            unique_urls=unique,
            unique_hashes=unique_hashes,
            unique_countries=unique_countries,
            bot_detected=bot_detected,
            top_browsers=top_browsers,
            top_os=top_os,
            top_countries=top_countries,
        ).model_dump()
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging
import json
import os
import psycopg
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg.connect(DATABASE_URL, autocommit=True)

def init_db():
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set — scrape logging disabled")
        return
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scrapes (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    content_preview TEXT,
                    fingerprint JSONB,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.close()
        logger.info("Database initialized — scrapes table ready")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version="2.2.0",
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
    fingerprint: Optional[dict] = None


class ScrapeResponse(BaseModel):
    url: str
    content: str
    success: bool = True


class ScrapeLog(BaseModel):
    id: int
    url: str
    content_preview: Optional[str]
    fingerprint: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


class StatsResponse(BaseModel):
    total_scrapes: int
    unique_urls: int


def scrape_basic(url: str, raw: bool = False) -> str:
    """Basic scrape using requests + BeautifulSoup with fallback."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise Exception("Request timed out after 30 seconds")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Could not connect to {url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error: {e.response.status_code}")
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


def store_scrape(url: str, content: str, fingerprint: Optional[dict], ip_address: str, user_agent: str):
    """Store scrape record in Neon DB."""
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scrapes (url, content_preview, fingerprint, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    url,
                    content[:500] if content else None,
                    json.dumps(fingerprint) if fingerprint else None,
                    ip_address,
                    user_agent,
                ),
            )
        conn.close()
    except Exception as e:
        logger.error(f"Failed to store scrape: {e}")


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": "2.2.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "scrapes": "GET /scrapes",
            "stats": "GET /stats",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.2.0"}


@app.post("/scrape")
def scrape_url(req: ScrapeRequest, request: Request):
    """Scrape a website and return clean text."""
    url_str = str(req.url)
    logger.info(f"Scrape request: {url_str}")
    try:
        content = scrape_basic(url_str, raw=req.raw)
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
    """Get recent scrape logs."""
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, url, content_preview, fingerprint, ip_address, user_agent, created_at
                   FROM scrapes ORDER BY created_at DESC LIMIT %s""",
                (min(limit, 500),),
            )
            rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append(ScrapeLog(
                id=r[0],
                url=r[1],
                content_preview=r[2],
                fingerprint=json.loads(r[3]) if r[3] else None,
                ip_address=r[4],
                user_agent=r[5],
                created_at=r[6].isoformat() if r[6] else "",
            ).model_dump())
        return result
    except Exception as e:
        logger.error(f"Failed to fetch scrapes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    """Get scrape statistics."""
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scrapes")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT url) FROM scrapes")
            unique = cur.fetchone()[0]
        conn.close()
        return StatsResponse(total_scrapes=total, unique_urls=unique).model_dump()
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

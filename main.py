"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import logging
import traceback
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version="2.1.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeRequest(BaseModel):
    url: HttpUrl
    raw: bool = False


class ScrapeResponse(BaseModel):
    url: str
    content: str
    success: bool = True


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
        # Ensure we return decoded text, not raw bytes
        return resp.text

    if "json" in content_type:
        return resp.text

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Get title
    title = soup.title.string if soup.title else ""

    # Get meta description
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_desc = meta.get("content", "")

    # Get main content
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Build output
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if meta_desc:
        parts.append(f"Description: {meta_desc}")
    parts.append("")
    parts.append(text)

    return "\n".join(parts)


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": "2.1.1",
        "endpoints": {
            "scrape": "POST /scrape",
        }
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}


@app.post("/scrape")
def scrape_url(req: ScrapeRequest):
    """Scrape a website and return clean text."""
    url_str = str(req.url)
    logger.info(f"Scrape request: {url_str}")
    try:
        content = scrape_basic(url_str, raw=req.raw)
        if not content or len(content.strip()) == 0:
            raise Exception("Empty response from target website")
        logger.info(f"Scrape success: {url_str} ({len(content)} chars)")
        return ScrapeResponse(url=url_str, content=content)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Scrape failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

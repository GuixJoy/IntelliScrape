"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import json
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from intelliscrape import IntelliScrape, scrape
from intelliscrape.crawler import crawl

app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version="2.1.0",
)

# Allow CORS for frontend
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


class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 10


class ScrapeResponse(BaseModel):
    url: str
    content: str
    success: bool = True


class StructuredResponse(BaseModel):
    url: str
    title: str
    description: str
    meta_tags: dict
    headings: dict
    success: bool = True


class CrawlResponse(BaseModel):
    base_url: str
    total_pages: int
    pages: list[dict]
    success: bool = True


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": "2.1.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "structured": "POST /structured",
            "crawl": "POST /crawl",
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
        content = scrape(url_str, return_raw=req.raw)
        if not content:
            raise ValueError("Empty response from target website")
        logger.info(f"Scrape success: {url_str} ({len(content)} chars)")
        return ScrapeResponse(url=url_str, content=content)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Scrape failed: {url_str} -> {error_msg}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=400,
            detail=f"Failed to scrape {url_str}: {error_msg}"
        )


@app.post("/structured")
def get_structured(req: ScrapeRequest):
    """Get structured data (title, meta, headings, etc)."""
    url_str = str(req.url)
    logger.info(f"Structured request: {url_str}")
    try:
        scraper = IntelliScrape()
        data = scraper.get_structured(url_str)
        return StructuredResponse(
            url=url_str,
            title=data.title,
            description=data.description,
            meta_tags=data.meta_tags,
            headings=data.headings,
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Structured failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=f"Failed to scrape {url_str}: {error_msg}")


@app.post("/crawl")
def crawl_site(req: CrawlRequest):
    """Crawl a website and return all pages."""
    url_str = str(req.url)
    logger.info(f"Crawl request: {url_str}")
    try:
        max_pages = min(req.max_pages, 20)
        result = crawl(url_str, max_pages=max_pages)
        return CrawlResponse(
            base_url=result.base_url,
            total_pages=result.total_pages,
            pages=[{"url": p.url, "content": p.content} for p in result.pages],
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Crawl failed: {url_str} -> {error_msg}")
        raise HTTPException(status_code=400, detail=f"Failed to crawl {url_str}: {error_msg}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

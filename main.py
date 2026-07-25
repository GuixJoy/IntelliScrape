"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import json

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


@app.post("/scrape")
def scrape_url(req: ScrapeRequest):
    """Scrape a website and return clean text."""
    try:
        content = scrape(str(req.url), return_raw=req.raw)
        return ScrapeResponse(url=str(req.url), content=content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/structured")
def get_structured(req: ScrapeRequest):
    """Get structured data (title, meta, headings, etc)."""
    try:
        scraper = IntelliScrape()
        data = scraper.get_structured(str(req.url))
        return StructuredResponse(
            url=str(req.url),
            title=data.title,
            description=data.description,
            meta_tags=data.meta_tags,
            headings=data.headings,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/crawl")
def crawl_site(req: CrawlRequest):
    """Crawl a website and return all pages."""
    try:
        max_pages = min(req.max_pages, 20)
        result = crawl(str(req.url), max_pages=max_pages)
        return CrawlResponse(
            base_url=result.base_url,
            total_pages=result.total_pages,
            pages=[{"url": p.url, "content": p.content} for p in result.pages],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

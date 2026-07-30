"""FastAPI backend for IntelliScrape."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import json

from intelliscrape import IntelliScrape, scrape
from intelliscrape.crawler import crawl
from intelliscrape.tech import TechStackExtractor

app = FastAPI(
    title="IntelliScrape API",
    description="Scrape any website with anti-detection capabilities",
    version="2.6.0",
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


class TechRequest(BaseModel):
    url: HttpUrl


class TechResponse(BaseModel):
    url: str
    tech: dict
    server_headers: dict = {}
    success: bool = True


class DetectApiRequest(BaseModel):
    url: HttpUrl


class DetectApiResponse(BaseModel):
    url: str
    endpoints: list = []
    key_exposures: list = []
    third_party_apis: list = []
    documentation: list = []
    summary: dict = {}
    success: bool = True


@app.get("/")
def root():
    return {
        "name": "IntelliScrape API",
        "version": "2.6.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "structured": "POST /structured",
            "tech": "POST /tech",
            "detect_api": "POST /detect-api",
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


@app.post("/tech")
def detect_tech(req: TechRequest):
    """Detect website technology stack (frameworks, CMS, analytics, CDN, etc)."""
    try:
        scraper = IntelliScrape()
        tech = scraper.detect_tech(str(req.url))
        return TechResponse(
            url=str(req.url),
            tech=tech.to_dict(),
            server_headers={
                k: v for k, v in tech.headers.items()
                if k.lower() in (
                    "server", "x-powered-by", "x-generator",
                    "via", "x-amz-cf-pop", "x-vercel",
                    "cf-ray", "x-shopify-stage",
                )
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/detect-api")
def detect_api(req: DetectApiRequest):
    """Detect API endpoints, third-party services, and exposed keys."""
    try:
        scraper = IntelliScrape()
        report = scraper.detect_apis(str(req.url))
        return DetectApiResponse(
            url=str(req.url),
            endpoints=[ep.to_dict() for ep in report.endpoints],
            key_exposures=[k.to_dict() for k in report.key_exposures],
            third_party_apis=report.third_party_apis,
            documentation=report.documentation,
            summary=report.summary,
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

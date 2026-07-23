"""Structured data extraction from HTML."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup


@dataclass
class StructuredData:
    """Extracted structured data from a page."""
    url: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    date_published: str = ""
    date_modified: str = ""
    image: str = ""
    favicon: str = ""
    canonical_url: str = ""
    og_data: Dict[str, str] = field(default_factory=dict)
    twitter_data: Dict[str, str] = field(default_factory=dict)
    json_ld: List[Dict[str, Any]] = field(default_factory=list)
    meta_tags: Dict[str, str] = field(default_factory=dict)
    headings: Dict[str, List[str]] = field(default_factory=dict)
    links: List[Dict[str, str]] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "author": self.author,
            "date_published": self.date_published,
            "date_modified": self.date_modified,
            "image": self.image,
            "favicon": self.favicon,
            "canonical_url": self.canonical_url,
            "og_data": self.og_data,
            "twitter_data": self.twitter_data,
            "json_ld": self.json_ld,
            "meta_tags": self.meta_tags,
            "headings": self.headings,
            "links": self.links,
            "images": self.images,
        }


class StructuredExtractor:
    """Extracts structured data from HTML."""

    @classmethod
    def extract(cls, html: str, url: str = "") -> StructuredData:
        """Extract all structured data from HTML.

        Parameters
        ----------
        html : str
            Raw HTML content.
        url : str
            Page URL.

        Returns
        -------
        StructuredData
            Extracted structured data.
        """
        soup = BeautifulSoup(html, "html.parser")
        data = StructuredData(url=url)

        # Extract title
        data.title = cls._extract_title(soup)

        # Extract meta tags
        data.meta_tags = cls._extract_meta_tags(soup)

        # Extract Open Graph data
        data.og_data = cls._extract_og_data(soup)

        # Extract Twitter Card data
        data.twitter_data = cls._extract_twitter_data(soup)

        # Extract JSON-LD
        data.json_ld = cls._extract_json_ld(soup)

        # Extract common fields
        data.description = (
            data.og_data.get("og:description")
            or data.meta_tags.get("description")
            or data.twitter_data.get("twitter:description")
            or ""
        )

        data.author = (
            data.meta_tags.get("author")
            or data.json_ld[0].get("author", {}).get("name", "")
            if data.json_ld
            else ""
        )

        data.image = (
            data.og_data.get("og:image")
            or data.twitter_data.get("twitter:image")
            or ""
        )

        data.canonical_url = cls._extract_canonical(soup)
        data.favicon = cls._extract_favicon(soup)

        # Extract headings
        data.headings = cls._extract_headings(soup)

        # Extract images
        data.images = cls._extract_images(soup, url)

        return data

    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "")

        # Try title tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    @classmethod
    def _extract_meta_tags(cls, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract all meta tags."""
        meta_tags = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            property_name = meta.get("property", "").lower()
            content = meta.get("content", "")

            if name:
                meta_tags[name] = content
            elif property_name:
                meta_tags[property_name] = content

        return meta_tags

    @classmethod
    def _extract_og_data(cls, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract Open Graph meta tags."""
        og_data = {}
        for meta in soup.find_all("meta", property=re.compile(r"^og:")):
            property_name = meta.get("property", "")
            content = meta.get("content", "")
            if property_name and content:
                og_data[property_name] = content
        return og_data

    @classmethod
    def _extract_twitter_data(cls, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract Twitter Card meta tags."""
        twitter_data = {}
        for meta in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            name = meta.get("name", "")
            content = meta.get("content", "")
            if name and content:
                twitter_data[name] = content
        return twitter_data

    @classmethod
    def _extract_json_ld(cls, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract JSON-LD structured data."""
        json_ld_list = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    json_ld_list.extend(data)
                else:
                    json_ld_list.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return json_ld_list

    @classmethod
    def _extract_canonical(cls, soup: BeautifulSoup) -> str:
        """Extract canonical URL."""
        canonical = soup.find("link", rel="canonical")
        return canonical.get("href", "") if canonical else ""

    @classmethod
    def _extract_favicon(cls, soup: BeautifulSoup) -> str:
        """Extract favicon URL."""
        # Try icon link
        icon = soup.find("link", rel=re.compile(r"icon", re.I))
        if icon:
            return icon.get("href", "")

        # Try apple-touch-icon
        apple_icon = soup.find("link", rel="apple-touch-icon")
        if apple_icon:
            return apple_icon.get("href", "")

        # Default
        return "/favicon.ico"

    @classmethod
    def _extract_headings(cls, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract all headings."""
        headings = {}
        for level in range(1, 7):
            tag = f"h{level}"
            elements = soup.find_all(tag)
            if elements:
                headings[tag] = [el.get_text(strip=True) for el in elements]
        return headings

    @classmethod
    def _extract_images(cls, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, str]]:
        """Extract images with alt text."""
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src:
                images.append({"src": src, "alt": alt})
        return images

    @classmethod
    def extract_article(cls, html: str, url: str = "") -> Dict[str, Any]:
        """Extract article-specific structured data.

        Focuses on article content, author, dates, etc.
        """
        data = cls.extract(html, url)

        # Find article JSON-LD
        article_data = None
        for item in data.json_ld:
            if item.get("@type") in ["Article", "NewsArticle", "BlogPosting", "WebPage"]:
                article_data = item
                break

        result = {
            "url": url,
            "title": data.title,
            "description": data.description,
            "author": data.author,
            "image": data.image,
            "published_date": data.date_published,
            "modified_date": data.date_modified,
        }

        if article_data:
            result.update({
                "headline": article_data.get("headline", data.title),
                "description": article_data.get("description", data.description),
                "author": article_data.get("author", {}).get("name", data.author),
                "date_published": article_data.get("datePublished", ""),
                "date_modified": article_data.get("dateModified", ""),
                "publisher": article_data.get("publisher", {}).get("name", ""),
            })

        return result

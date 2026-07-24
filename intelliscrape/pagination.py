"""Auto-pagination for IntelliScrape."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup


@dataclass
class PageInfo:
    """Information about a page."""
    url: str
    content: str
    page_number: int


class Paginator:
    """Auto-detect and follow pagination."""
    
    # Common next page patterns
    NEXT_PATTERNS = [
        # Text patterns
        r"next",
        r"next page",
        r"next\s*»",
        r"»",
        r"›",
        r"→",
        r"forward",
        r"older",
        r"more",
        r"load more",
        r"show more",
        r"view more",
        # Class/ID patterns
        r"next[-_]?page",
        r"pagination[-_]?next",
        r"page[-_]?next",
        r"btn[-_]?next",
        r"arrow[-_]?right",
    ]
    
    # Common page number patterns in URLs
    PAGE_PARAM_PATTERNS = [
        r"page=(\d+)",
        r"p=(\d+)",
        r"offset=(\d+)",
        r"start=(\d+)",
        r"pg=(\d+)",
        r"paged=(\d+)",
    ]
    
    def __init__(self, session=None):
        self.session = session
    
    def find_next_page(
        self,
        html: str,
        current_url: str,
        current_page: int = 1,
    ) -> Optional[str]:
        """Find the next page URL.
        
        Parameters
        ----------
        html : str
            Current page HTML.
        current_url : str
            Current page URL.
        current_page : int
            Current page number.
            
        Returns
        -------
        str or None
            Next page URL, or None if not found.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Try to find "next" link
        next_url = self._find_next_link(soup, current_url)
        if next_url:
            return next_url
        
        # Try to find by page number
        next_url = self._find_by_page_number(soup, current_url, current_page)
        if next_url:
            return next_url
        
        # Try URL manipulation
        next_url = self._find_by_url_pattern(current_url, current_page)
        if next_url:
            return next_url
        
        return None
    
    def has_next_page(self, html: str, current_url: str, current_page: int = 1) -> bool:
        """Check if there's a next page."""
        return self.find_next_page(html, current_url, current_page) is not None
    
    def get_all_pages(
        self,
        start_url: str,
        max_pages: int = 50,
        *,
        callback=None,
    ) -> List[PageInfo]:
        """Get all pages by following pagination.
        
        Parameters
        ----------
        start_url : str
            Starting URL.
        max_pages : int
            Maximum number of pages to scrape.
        callback : callable, optional
            Called after each page: callback(page_info).
            
        Returns
        -------
        List[PageInfo]
            List of page information.
        """
        import requests
        
        pages = []
        current_url = start_url
        current_page = 1
        
        while current_url and len(pages) < max_pages:
            try:
                # Fetch page
                if self.session:
                    response = self.session.get(current_url, timeout=30)
                    html = response.text
                else:
                    response = requests.get(current_url, timeout=30)
                    html = response.text
                
                # Create page info
                page_info = PageInfo(
                    url=current_url,
                    content=html,
                    page_number=current_page,
                )
                pages.append(page_info)
                
                # Callback
                if callback:
                    callback(page_info)
                
                # Find next page
                current_url = self.find_next_page(html, current_url, current_page)
                current_page += 1
                
            except Exception as e:
                print(f"Error fetching page {current_page}: {e}")
                break
        
        return pages
    
    def extract_page_numbers(self, html: str) -> List[int]:
        """Extract all page numbers from pagination links."""
        soup = BeautifulSoup(html, "html.parser")
        page_numbers = set()
        
        # Find pagination container
        pagination = soup.find("nav", class_=re.compile(r"pagination|pager|page")) or \
                     soup.find("div", class_=re.compile(r"pagination|pager|page")) or \
                     soup.find("ul", class_=re.compile(r"pagination|pager|page"))
        
        if pagination:
            # Find all links with page numbers
            for link in pagination.find_all("a"):
                href = link.get("href", "")
                text = link.text.strip()
                
                # Try to extract page number from text
                if text.isdigit():
                    page_numbers.add(int(text))
                
                # Try to extract from URL
                for pattern in self.PAGE_PARAM_PATTERNS:
                    match = re.search(pattern, href)
                    if match:
                        page_numbers.add(int(match.group(1)))
        
        return sorted(page_numbers)
    
    def _find_next_link(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find 'next' link in HTML."""
        # Look for links with "next" in text, class, or aria-label
        for link in soup.find_all("a"):
            href = link.get("href", "")
            text = link.text.strip().lower()
            classes = " ".join(link.get("class", []))
            aria_label = link.get("aria-label", "").lower()
            title = link.get("title", "").lower()
            
            # Check various patterns
            for pattern in self.NEXT_PATTERNS:
                if (re.search(pattern, text, re.IGNORECASE) or
                    re.search(pattern, classes, re.IGNORECASE) or
                    re.search(pattern, aria_label, re.IGNORECASE) or
                    re.search(pattern, title, re.IGNORECASE)):
                    
                    # Resolve URL
                    next_url = urljoin(current_url, href)
                    if next_url != current_url:
                        return next_url
        
        # Look for rel="next"
        for link in soup.find_all("a", rel="next"):
            href = link.get("href", "")
            if href:
                return urljoin(current_url, href)
        
        return None
    
    def _find_by_page_number(
        self,
        soup: BeautifulSoup,
        current_url: str,
        current_page: int,
    ) -> Optional[str]:
        """Find next page by page number."""
        next_page = current_page + 1
        
        # Look for link with page number
        for link in soup.find_all("a"):
            href = link.get("href", "")
            text = link.text.strip()
            
            # Check if text matches page number
            if text == str(next_page):
                return urljoin(current_url, href)
            
            # Check if href contains page parameter
            for pattern in self.PAGE_PARAM_PATTERNS:
                match = re.search(pattern, href)
                if match and int(match.group(1)) == next_page:
                    return urljoin(current_url, href)
        
        return None
    
    def _find_by_url_pattern(self, url: str, current_page: int) -> Optional[str]:
        """Try to find next page by URL pattern."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Check common page parameters
        for param in ["page", "p", "offset", "start", "pg", "paged"]:
            if param in params:
                current_value = int(params[param][0])
                next_value = current_value + 1
                
                # Update parameter
                params[param] = [str(next_value)]
                
                # Reconstruct URL
                new_query = urlencode(params, doseq=True)
                new_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                ))
                return new_url
        
        # Try adding page parameter
        if not params:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}page={current_page + 1}"
        
        return None

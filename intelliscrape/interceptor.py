"""Request and response interception for IntelliScrape."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse


@dataclass
class InterceptedRequest:
    """Intercepted request data."""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)
    modified: bool = False


@dataclass
class InterceptedResponse:
    """Intercepted response data."""
    url: str
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    modified: bool = False


class RequestInterceptor:
    """Intercept and modify requests/responses."""
    
    def __init__(self):
        self.request_handlers: List[Callable[[InterceptedRequest], Optional[InterceptedRequest]]] = []
        self.response_handlers: List[Callable[[InterceptedResponse], Optional[InterceptedResponse]]] = []
        self.url_filters: List[str] = []
        self.blocked_urls: List[str] = []
        self.modified_headers: Dict[str, str] = {}
    
    def add_request_handler(
        self,
        handler: Callable[[InterceptedRequest], Optional[InterceptedRequest]],
    ) -> None:
        """Add a request handler.
        
        Parameters
        ----------
        handler : callable
            Function that receives InterceptedRequest and returns modified version.
            Return None to block the request.
        """
        self.request_handlers.append(handler)
    
    def add_response_handler(
        self,
        handler: Callable[[InterceptedResponse], Optional[InterceptedResponse]],
    ) -> None:
        """Add a response handler.
        
        Parameters
        ----------
        handler : callable
            Function that receives InterceptedResponse and returns modified version.
            Return None to block the response.
        """
        self.response_handlers.append(handler)
    
    def block_urls(self, patterns: List[str]) -> None:
        """Block URLs matching patterns.
        
        Parameters
        ----------
        patterns : list of str
            URL patterns to block (supports regex).
        """
        self.blocked_urls.extend(patterns)
    
    def filter_urls(self, patterns: List[str]) -> None:
        """Only process URLs matching patterns.
        
        Parameters
        ----------
        patterns : list of str
            URL patterns to allow (supports regex).
        """
        self.url_filters.extend(patterns)
    
    def modify_headers(self, headers: Dict[str, str]) -> None:
        """Add/modify headers for all requests.
        
        Parameters
        ----------
        headers : dict
            Headers to add/modify.
        """
        self.modified_headers.update(headers)
    
    def intercept_request(self, request: InterceptedRequest) -> Optional[InterceptedRequest]:
        """Process a request through all handlers.
        
        Parameters
        ----------
        request : InterceptedRequest
            Request to process.
            
        Returns
        -------
        InterceptedRequest or None
            Modified request, or None to block.
        """
        # Check if URL is blocked
        if self._is_blocked(request.url):
            return None
        
        # Check URL filter
        if self.url_filters and not self._matches_filter(request.url):
            return None
        
        # Apply modified headers
        if self.modified_headers:
            request.headers.update(self.modified_headers)
            request.modified = True
        
        # Apply handlers
        for handler in self.request_handlers:
            result = handler(request)
            if result is None:
                return None
            request = result
        
        return request
    
    def intercept_response(self, response: InterceptedResponse) -> Optional[InterceptedResponse]:
        """Process a response through all handlers.
        
        Parameters
        ----------
        response : InterceptedResponse
            Response to process.
            
        Returns
        -------
        InterceptedResponse or None
            Modified response, or None to block.
        """
        # Check if URL is blocked
        if self._is_blocked(response.url):
            return None
        
        # Apply handlers
        for handler in self.response_handlers:
            result = handler(response)
            if result is None:
                return None
            response = result
        
        return response
    
    def _is_blocked(self, url: str) -> bool:
        """Check if URL is blocked."""
        for pattern in self.blocked_urls:
            if re.search(pattern, url):
                return True
        return False
    
    def _matches_filter(self, url: str) -> bool:
        """Check if URL matches filter."""
        for pattern in self.url_filters:
            if re.search(pattern, url):
                return True
        return False
    
    def clear(self) -> None:
        """Clear all handlers and filters."""
        self.request_handlers.clear()
        self.response_handlers.clear()
        self.url_filters.clear()
        self.blocked_urls.clear()
        self.modified_headers.clear()


class ResponseModifier:
    """Modify response content."""
    
    @staticmethod
    def remove_elements(html: str, selectors: List[str]) -> str:
        """Remove elements by CSS selectors.
        
        Parameters
        ----------
        html : str
            HTML content.
        selectors : list of str
            CSS selectors to remove.
            
        Returns
        -------
        str
            Modified HTML.
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, "html.parser")
        
        for selector in selectors:
            for element in soup.select(selector):
                element.decompose()
        
        return str(soup)
    
    @staticmethod
    def extract_elements(html: str, selectors: List[str]) -> List[str]:
        """Extract elements by CSS selectors.
        
        Parameters
        ----------
        html : str
            HTML content.
        selectors : list of str
            CSS selectors to extract.
            
        Returns
        -------
        list of str
            Extracted element HTML.
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        for selector in selectors:
            for element in soup.select(selector):
                results.append(str(element))
        
        return results
    
    @staticmethod
    def modify_text(
        html: str,
        replacements: Dict[str, str],
    ) -> str:
        """Modify text content.
        
        Parameters
        ----------
        html : str
            HTML content.
        replacements : dict
            Dictionary of old_text -> new_text.
            
        Returns
        -------
        str
            Modified HTML.
        """
        for old, new in replacements.items():
            html = html.replace(old, new)
        return html
    
    @staticmethod
    def extract_json(html: str, pattern: str) -> Optional[str]:
        """Extract JSON from HTML using regex.
        
        Parameters
        ----------
        html : str
            HTML content.
        pattern : str
            Regex pattern to match JSON.
            
        Returns
        -------
        str or None
            Extracted JSON string.
        """
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return None

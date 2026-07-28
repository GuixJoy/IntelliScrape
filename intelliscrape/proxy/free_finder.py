"""Free proxy finder and tester.

This module automatically finds and tests free proxies
so you don't have to pay for proxy services.
"""

from __future__ import annotations

import re
import time
import socket
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests


logger = logging.getLogger("intelliscrape")


class ProxyAnonymity(Enum):
    """Proxy anonymity level."""
    TRANSPARENT = "transparent"  # Server knows you're using proxy
    ANONYMOUS = "anonymous"  # Server knows you're using proxy but not your IP
    ELITE = "elite"  # Server doesn't know you're using proxy


@dataclass
class FreeProxy:
    """A free proxy."""
    host: str
    port: int
    protocol: str = "http"
    country: Optional[str] = None
    anonymity: ProxyAnonymity = ProxyAnonymity.ANONYMOUS
    speed: float = 0  # Response time in seconds
    last_checked: float = 0
    is_working: bool = True
    
    @property
    def url(self) -> str:
        """Get proxy URL."""
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def dict(self) -> Dict[str, str]:
        """Get proxy dict for requests."""
        return {
            "http": self.url,
            "https": self.url,
        }


class FreeProxyFinder:
    """Find and test free proxies automatically.
    
    Sources:
    - Free proxy lists from various websites
    - Proxy APIs
    - Community-maintained lists
    """
    
    # Free proxy list sources
    PROXY_SOURCES = [
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    ]
    
    def __init__(
        self,
        timeout: float = 5.0,
        max_proxies: int = 100,
        test_url: str = "https://httpbin.org/ip",
    ):
        """Initialize the free proxy finder.
        
        Parameters
        ----------
        timeout : float
            Timeout for proxy tests (seconds).
        max_proxies : int
            Maximum number of proxies to test.
        test_url : str
            URL to test proxies against.
        """
        self.timeout = timeout
        self.max_proxies = max_proxies
        self.test_url = test_url
        self._proxies: List[FreeProxy] = []
        self._working_proxies: List[FreeProxy] = []
    
    def find_proxies(
        self,
        *,
        protocol: Optional[str] = None,
        country: Optional[str] = None,
        anonymity: Optional[ProxyAnonymity] = None,
        test: bool = True,
        max_workers: int = 10,
    ) -> List[FreeProxy]:
        """Find and optionally test free proxies.
        
        Parameters
        ----------
        protocol : str, optional
            Filter by protocol ("http" or "https"). If None, return all.
        country : str, optional
            Filter by country code (e.g., "us", "uk").
        anonymity : ProxyAnonymity, optional
            Filter by anonymity level.
        test : bool
            Test proxies before returning.
        max_workers : int
            Number of concurrent workers for testing.
            
        Returns
        -------
        List[FreeProxy]
            List of working proxies.
        """
        print("Finding free proxies...")
        
        # Fetch proxy lists
        raw_proxies = self._fetch_proxy_lists()
        print(f"Found {len(raw_proxies)} raw proxies")
        
        # Parse proxies
        self._proxies = self._parse_proxies(raw_proxies)
        print(f"Parsed {len(self._proxies)} valid proxies")
        
        # Filter proxies
        filtered = self._filter_proxies(protocol, country, anonymity)
        print(f"Filtered to {len(filtered)} proxies")
        
        # Test proxies
        if test and filtered:
            self._working_proxies = self._test_proxies(filtered, max_workers)
            print(f"Found {len(self._working_proxies)} working proxies")
        else:
            self._working_proxies = filtered
        
        return self._working_proxies
    
    def get_proxy(self) -> Optional[FreeProxy]:
        """Get a random working proxy."""
        if not self._working_proxies:
            return None
        
        import random
        return random.choice(self._working_proxies)
    
    def get_best_proxy(self) -> Optional[FreeProxy]:
        """Get the fastest working proxy."""
        if not self._working_proxies:
            return None
        
        # Sort by speed (lower is better)
        sorted_proxies = sorted(self._working_proxies, key=lambda p: p.speed)
        return sorted_proxies[0] if sorted_proxies else None
    
    def _fetch_proxy_lists(self) -> List[str]:
        """Fetch proxy lists from sources."""
        all_proxies = []
        
        for url in self.PROXY_SOURCES:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    lines = response.text.strip().split("\n")
                    all_proxies.extend(lines)
                    logger.debug(f"Fetched {len(lines)} proxies from {url}")
            except Exception as e:
                logger.debug(f"Failed to fetch from {url}: {e}")
                continue
        
        return all_proxies
    
    def _parse_proxies(self, raw_proxies: List[str]) -> List[FreeProxy]:
        """Parse raw proxy strings into FreeProxy objects."""
        proxies = []
        seen = set()
        
        for line in raw_proxies:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Try to parse different formats
            proxy = self._parse_proxy_line(line)
            if proxy:
                # Deduplicate
                key = f"{proxy.host}:{proxy.port}"
                if key not in seen:
                    seen.add(key)
                    proxies.append(proxy)
        
        return proxies[:self.max_proxies]
    
    def _parse_proxy_line(self, line: str) -> Optional[FreeProxy]:
        """Parse a single proxy line."""
        try:
            # Remove protocol if present
            line = re.sub(r'^https?://', '', line)
            line = re.sub(r'^socks[45]://', '', line)
            
            # Remove authentication if present
            if "@" in line:
                line = line.split("@")[-1]
            
            # Parse host:port
            parts = line.split(":")
            if len(parts) == 2:
                host = parts[0].strip()
                port = int(parts[1].strip())
                
                # Determine protocol
                protocol = "http"
                if "https" in line.lower():
                    protocol = "https"
                
                return FreeProxy(
                    host=host,
                    port=port,
                    protocol=protocol,
                )
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _filter_proxies(
        self,
        protocol: Optional[str],
        country: Optional[str],
        anonymity: Optional[ProxyAnonymity],
    ) -> List[FreeProxy]:
        """Filter proxies based on criteria."""
        filtered = self._proxies.copy()
        
        # If no protocol specified, return all
        if not protocol:
            return filtered
        
        # Filter by protocol (but also include http as fallback for https)
        if protocol:
            protocol_lower = protocol.lower()
            filtered = [p for p in filtered if p.protocol.lower() in [protocol_lower, "http"]]
        
        return filtered
    
    def _test_proxies(
        self,
        proxies: List[FreeProxy],
        max_workers: int,
    ) -> List[FreeProxy]:
        """Test proxies concurrently."""
        working = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._test_proxy, proxy): proxy
                for proxy in proxies
            }
            
            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    is_working, speed = future.result()
                    if is_working:
                        proxy.is_working = True
                        proxy.speed = speed
                        proxy.last_checked = time.time()
                        working.append(proxy)
                        logger.debug(f"Working proxy: {proxy.url} ({speed:.2f}s)")
                except Exception as e:
                    logger.debug(f"Proxy test failed: {proxy.url}: {e}")
        
        return working
    
    def _test_proxy(self, proxy: FreeProxy) -> Tuple[bool, float]:
        """Test a single proxy."""
        start_time = time.time()
        
        try:
            response = requests.get(
                self.test_url,
                proxies=proxy.dict,
                timeout=self.timeout,
            )
            
            speed = time.time() - start_time
            
            if response.status_code == 200:
                return True, speed
            
            return False, 0
            
        except Exception:
            return False, 0


class IntelligentProxyFinder:
    """Intelligent proxy finder that combines multiple strategies."""
    
    def __init__(
        self,
        brightdata_key: Optional[str] = None,
        scraperapi_key: Optional[str] = None,
        oxylabs_key: Optional[str] = None,
        smartproxy_key: Optional[str] = None,
    ):
        """Initialize with optional paid provider keys."""
        self.brightdata_key = brightdata_key
        self.scraperapi_key = scraperapi_key
        self.oxylabs_key = oxylabs_key
        self.smartproxy_key = smartproxy_key
        
        self.free_finder = FreeProxyFinder()
        self._free_proxies: List[FreeProxy] = []
    
    def find_best_proxy(
        self,
        url: str,
        *,
        prefer_residential: bool = True,
        max_retries: int = 3,
    ) -> Optional[str]:
        """Find the best proxy for a URL.
        
        Strategy:
        1. If paid provider key available, use it
        2. Otherwise, find and test free proxies
        3. Return the fastest working proxy
        """
        # Try paid providers first
        paid_proxy = self._get_paid_proxy(url, prefer_residential)
        if paid_proxy:
            return paid_proxy
        
        # Fall back to free proxies
        if not self._free_proxies:
            print("Finding free proxies (this may take a moment)...")
            self._free_proxies = self.free_finder.find_proxies(
                protocol="https",
                test=True,
                max_workers=10,
            )
        
        # Get a working proxy
        proxy = self.free_finder.get_best_proxy()
        if proxy:
            return proxy.url
        
        return None
    
    def _get_paid_proxy(self, url: str, prefer_residential: bool) -> Optional[str]:
        """Get proxy from paid provider."""
        # Try Bright Data
        if self.brightdata_key:
            return self._get_brightdata_proxy(url)
        
        # Try ScraperAPI
        if self.scraperapi_key:
            return self._get_scraperapi_proxy(url)
        
        # Try Oxylabs
        if self.oxylabs_key:
            return self._get_oxylabs_proxy(url)
        
        # Try Smartproxy
        if self.smartproxy_key:
            return self._get_smartproxy_proxy(url)
        
        return None
    
    def _get_brightdata_proxy(self, url: str) -> str:
        """Get Bright Data proxy."""
        return f"http://brd-customer-{self.brightdata_key}-zone-residential:password@brd.superproxy.io:22225"
    
    def _get_scraperapi_proxy(self, url: str) -> str:
        """Get ScraperAPI proxy."""
        return f"http://scraperapi:{self.scraperapi_key}@proxy.scraperapi.com:8080"
    
    def _get_oxylabs_proxy(self, url: str) -> str:
        """Get Oxylabs proxy."""
        return f"http://customer-{self.oxylabs_key}:password@pr.oxylabs.io:7777"
    
    def _get_smartproxy_proxy(self, url: str) -> str:
        """Get Smartproxy proxy."""
        return f"http://{self.smartproxy_key}:password@gate.smartproxy.com:7000"

"""IP rotation with residential proxy support for IntelliScrape.

Focuses on making requests look like real users, not datacenters.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


class ProxyType(Enum):
    """Proxy types by origin."""
    RESIDENTIAL = "residential"  # Real user IPs - best for avoiding detection
    DATACENTER = "datacenter"    # Server IPs - faster but easier to detect
    MOBILE = "mobile"            # Mobile carrier IPs - very hard to detect
    ISP = "isp"                  # ISP-provided IPs - good balance


@dataclass
class Proxy:
    """Proxy server configuration."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: ProxyType = ProxyType.RESIDENTIAL
    country: Optional[str] = None
    city: Optional[str] = None
    is_healthy: bool = True
    last_used: float = 0
    failure_count: int = 0
    success_count: int = 0
    
    @property
    def url(self) -> str:
        """Get proxy URL."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total


@dataclass
class IPInfo:
    """Information about current IP."""
    ip: str
    country: str = ""
    city: str = ""
    isp: str = ""
    is_datacenter: bool = False
    is_residential: bool = True
    response_time: float = 0


class IPManager:
    """Manage IP rotation with residential proxies.
    
    Focuses on:
    - Using residential/mobile IPs (not datacenter)
    - Natural rotation patterns (not too frequent)
    - Health checking (skip bad proxies)
    - Session persistence (keep same IP for session-based sites)
    """
    
    # Countries with good residential proxy coverage
    RESIDENTIAL_COUNTRIES = [
        "US", "UK", "DE", "FR", "JP", "BR", "IN", "AU", "CA", "NL",
        "ES", "IT", "MX", "KR", "PL", "SE", "CH", "AT", "BE", "DK",
    ]
    
    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        *,
        auto_rotate: bool = True,
        rotate_every: int = 5,  # Rotate every N requests
        health_check: bool = True,
        prefer_residential: bool = True,
        geo_target: Optional[str] = None,
        session_persistence: bool = True,
        min_success_rate: float = 0.5,
    ):
        """Initialize IP manager.
        
        Parameters
        ----------
        proxies : list of str, optional
            List of proxy strings (host:port or user:pass@host:port).
        auto_rotate : bool
            Automatically rotate IPs.
        rotate_every : int
            Rotate IP every N requests.
        health_check : bool
            Enable IP health checking.
        prefer_residential : bool
            Prefer residential proxies over datacenter.
        geo_target : str, optional
            Target country code (e.g., "US", "UK").
        session_persistence : bool
            Keep same IP for session-based sites.
        min_success_rate : float
            Minimum success rate to keep proxy active.
        """
        self.proxies: List[Proxy] = []
        self.auto_rotate = auto_rotate
        self.rotate_every = rotate_every
        self.health_check = health_check
        self.prefer_residential = prefer_residential
        self.geo_target = geo_target
        self.session_persistence = session_persistence
        self.min_success_rate = min_success_rate
        
        # State
        self.current_proxy: Optional[Proxy] = None
        self.request_count = 0
        self.session_ips: Dict[str, str] = {}  # domain -> IP mapping
        
        # Load proxies
        if proxies:
            self.add_proxies(proxies)
    
    def add_proxies(self, proxies: List[str]) -> None:
        """Add multiple proxies.
        
        Parameters
        ----------
        proxies : list of str
            Proxy strings in format:
            - host:port
            - user:pass@host:port
            - protocol://user:pass@host:port
        """
        for proxy_str in proxies:
            self.add_proxy(proxy_str)
    
    def add_proxy(
        self,
        proxy_str: str,
        *,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
        country: Optional[str] = None,
    ) -> None:
        """Add a single proxy.
        
        Parameters
        ----------
        proxy_str : str
            Proxy string.
        proxy_type : ProxyType
            Type of proxy.
        country : str, optional
            Country code.
        """
        # Parse proxy string
        host, port, username, password = self._parse_proxy(proxy_str)
        
        proxy = Proxy(
            host=host,
            port=port,
            username=username,
            password=password,
            proxy_type=proxy_type,
            country=country,
        )
        
        self.proxies.append(proxy)
    
    def get_proxy(self, domain: Optional[str] = None) -> Optional[Proxy]:
        """Get the best proxy for a request.
        
        Parameters
        ----------
        domain : str, optional
            Target domain for session persistence.
            
        Returns
        -------
        Proxy or None
            Best available proxy.
        """
        if not self.proxies:
            return None
        
        # Check session persistence
        if domain and self.session_persistence:
            if domain in self.session_ips:
                saved_ip = self.session_ips[domain]
                for proxy in self.proxies:
                    if proxy.host == saved_ip and proxy.is_healthy:
                        return proxy
        
        # Get healthy proxies
        healthy = [p for p in self.proxies if p.is_healthy]
        
        if not healthy:
            # Reset all proxies if all are unhealthy
            for p in self.proxies:
                p.is_healthy = True
                p.failure_count = 0
            healthy = self.proxies
        
        # Filter by type if preferred
        if self.prefer_residential:
            residential = [p for p in healthy if p.proxy_type in (ProxyType.RESIDENTIAL, ProxyType.MOBILE, ProxyType.ISP)]
            if residential:
                healthy = residential
        
        # Filter by country
        if self.geo_target:
            country_match = [p for p in healthy if p.country == self.geo_target]
            if country_match:
                healthy = country_match
        
        # Sort by success rate and recency
        healthy.sort(key=lambda p: (p.success_rate, -p.last_used), reverse=True)
        
        # Select proxy
        if self.auto_rotate and self.request_count % self.rotate_every == 0:
            # Rotate to different proxy
            available = [p for p in healthy if p != self.current_proxy]
            if available:
                proxy = random.choice(available[:3])  # Choose from top 3
            else:
                proxy = healthy[0]
        else:
            # Use current or best available
            if self.current_proxy and self.current_proxy in healthy:
                proxy = self.current_proxy
            else:
                proxy = healthy[0]
        
        # Update state
        self.current_proxy = proxy
        self.request_count += 1
        proxy.last_used = time.time()
        
        # Save session IP
        if domain:
            self.session_ips[domain] = proxy.host
        
        return proxy
    
    def report_success(self, proxy: Proxy) -> None:
        """Report successful request through proxy."""
        proxy.success_count += 1
    
    def report_failure(self, proxy: Proxy) -> None:
        """Report failed request through proxy."""
        proxy.failure_count += 1
        
        # Check health
        if self.health_check and proxy.success_rate < self.min_success_rate:
            proxy.is_healthy = False
    
    def check_ip(self, proxy: Optional[Proxy] = None) -> Optional[IPInfo]:
        """Check current IP information.
        
        Parameters
        ----------
        proxy : Proxy, optional
            Proxy to check through.
            
        Returns
        -------
        IPInfo or None
            IP information.
        """
        import requests
        
        try:
            proxies = None
            if proxy:
                proxies = {"http": proxy.url, "https": proxy.url}
            
            # Use IP info service
            response = requests.get(
                "https://ipinfo.io/json",
                proxies=proxies,
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                return IPInfo(
                    ip=data.get("ip", ""),
                    country=data.get("country", ""),
                    city=data.get("city", ""),
                    isp=data.get("org", ""),
                    is_datacenter="datacenter" in data.get("org", "").lower(),
                    is_residential="datacenter" not in data.get("org", "").lower(),
                )
        except:
            pass
        
        return None
    
    def get_stats(self) -> Dict:
        """Get proxy statistics."""
        total = len(self.proxies)
        healthy = sum(1 for p in self.proxies if p.is_healthy)
        residential = sum(1 for p in self.proxies if p.proxy_type == ProxyType.RESIDENTIAL)
        
        return {
            "total_proxies": total,
            "healthy_proxies": healthy,
            "residential_proxies": residential,
            "current_proxy": self.current_proxy.host if self.current_proxy else None,
            "request_count": self.request_count,
            "session_domains": len(self.session_ips),
        }
    
    def _parse_proxy(self, proxy_str: str) -> Tuple[str, int, Optional[str], Optional[str]]:
        """Parse proxy string into components."""
        # Remove protocol if present
        if "://" in proxy_str:
            proxy_str = proxy_str.split("://", 1)[1]
        
        # Parse user:pass@host:port
        if "@" in proxy_str:
            auth, host_port = proxy_str.split("@", 1)
            username, password = auth.split(":", 1)
        else:
            username, password = None, None
            host_port = proxy_str
        
        # Parse host:port
        host, port = host_port.split(":")
        
        return host, int(port), username, password


class NaturalRotator:
    """Make IP rotation look natural, not automated."""
    
    # Patterns that look like real users
    REQUEST_PATTERNS = {
        "browse": {"min_delay": 2, "max_delay": 8, "pages_per_session": (3, 15)},
        "search": {"min_delay": 1, "max_delay": 5, "pages_per_session": (5, 20)},
        "scrape": {"min_delay": 0.5, "max_delay": 3, "pages_per_session": (10, 50)},
    }
    
    def __init__(self, pattern: str = "browse"):
        """Initialize natural rotator.
        
        Parameters
        ----------
        pattern : str
            Behavior pattern: "browse", "search", or "scrape".
        """
        self.pattern = pattern
        self.config = self.REQUEST_PATTERNS.get(pattern, self.REQUEST_PATTERNS["browse"])
        self.session_pages = 0
        self.target_pages = random.randint(*self.config["pages_per_session"])
    
    def get_delay(self) -> float:
        """Get natural delay between requests."""
        base_delay = random.uniform(self.config["min_delay"], self.config["max_delay"])
        
        # Add some randomness (real users vary their speed)
        variation = random.uniform(0.5, 1.5)
        
        # Occasional longer pauses (real users get distracted)
        if random.random() < 0.1:
            base_delay *= random.uniform(2, 5)
        
        return base_delay * variation
    
    def should_rotate(self) -> bool:
        """Check if we should rotate IP (simulate new session)."""
        self.session_pages += 1
        
        if self.session_pages >= self.target_pages:
            # Reset session
            self.session_pages = 0
            self.target_pages = random.randint(*self.config["pages_per_session"])
            return True
        
        return False
    
    def get_user_agent(self) -> str:
        """Get a realistic user agent."""
        user_agents = [
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Chrome on Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            # Safari on Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        ]
        return random.choice(user_agents)
    
    def get_accept_language(self) -> str:
        """Get realistic Accept-Language header."""
        languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.9,es;q=0.8",
            "de-DE,de;q=0.9,en-US;q=0.8",
            "fr-FR,fr;q=0.9,en-US;q=0.8",
            "ja-JP,ja;q=0.9,en-US;q=0.8",
        ]
        return random.choice(languages)

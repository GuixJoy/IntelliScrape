"""Intelligent proxy manager with residential proxy support.

This module provides:
- Auto-selection of best proxy based on site analysis
- Residential proxy integration
- Proxy health monitoring
- Automatic failover
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlparse

from ..intelligent import SiteAnalysis, SiteAnalyzer, SiteType, ProtectionLevel


class ProxyProvider(Enum):
    """Available proxy providers."""
    BRIGHTDATA = "brightdata"
    SCRAPERAPI = "scraperapi"
    OXYLABS = "oxylabs"
    SMARTPROXY = "smartproxy"
    IPROYAL = "iproyal"
    USERPROXY = "userproxy"  # User provides their own proxy


@dataclass
class ProxyConfig:
    """Configuration for a proxy."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    country: Optional[str] = None
    is_residential: bool = True
    provider: ProxyProvider = ProxyProvider.USERPROXY


@dataclass
class ProxyHealth:
    """Health tracking for a proxy."""
    proxy: ProxyConfig
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0
    avg_response_time: float = 0
    is_healthy: bool = True
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total
    
    def record_success(self, response_time: float) -> None:
        """Record successful request."""
        self.success_count += 1
        self.last_used = time.time()
        # Update average response time
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time + response_time) / 2
        self.is_healthy = True
    
    def record_failure(self) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_used = time.time()
        # Mark unhealthy if too many failures
        if self.failure_count > 5 and self.success_rate < 0.3:
            self.is_healthy = False


class IntelligentProxyManager:
    """Intelligent proxy manager that auto-selects the best proxy.
    
    This is what makes IntelliScrape truly intelligent about proxies.
    It analyzes the target site and automatically:
    - Selects residential vs datacenter proxy
    - Chooses the best provider
    - Manages proxy rotation
    - Handles failover
    """
    
    def __init__(
        self,
        user_proxies: Optional[List[str]] = None,
        brightdata_key: Optional[str] = None,
        scraperapi_key: Optional[str] = None,
        oxylabs_key: Optional[str] = None,
        smartproxy_key: Optional[str] = None,
        prefer_residential: bool = True,
    ):
        """Initialize the proxy manager.
        
        Parameters
        ----------
        user_proxies : list, optional
            User-provided proxies in format "host:port" or "user:pass@host:port".
        brightdata_key : str, optional
            Bright Data API key.
        scraperapi_key : str, optional
            ScraperAPI key.
        oxylabs_key : str, optional
            Oxylabs credentials.
        smartproxy_key : str, optional
            Smartproxy key.
        prefer_residential : bool
            Prefer residential proxies when available.
        """
        self.prefer_residential = prefer_residential
        self.site_analyzer = SiteAnalyzer()
        
        # Store provider configs
        self._provider_configs: Dict[ProxyProvider, dict] = {}
        
        # Add user proxies
        self._user_proxies: List[ProxyConfig] = []
        if user_proxies:
            for proxy_str in user_proxies:
                proxy = self._parse_proxy_string(proxy_str)
                if proxy:
                    self._user_proxies.append(proxy)
        
        # Initialize providers
        if brightdata_key:
            self._provider_configs[ProxyProvider.BRIGHTDATA] = {
                "api_key": brightdata_key,
            }
        
        if scraperapi_key:
            self._provider_configs[ProxyProvider.SCRAPERAPI] = {
                "api_key": scraperapi_key,
            }
        
        if oxylabs_key:
            self._provider_configs[ProxyProvider.OXYLABS] = {
                "api_key": oxylabs_key,
            }
        
        if smartproxy_key:
            self._provider_configs[ProxyProvider.SMARTPROXY] = {
                "api_key": smartproxy_key,
            }
        
        # Health tracking
        self._proxy_health: Dict[str, ProxyHealth] = {}
        
        # Current proxy index
        self._current_index = 0
    
    def _parse_proxy_string(self, proxy_str: str) -> Optional[ProxyConfig]:
        """Parse a proxy string into ProxyConfig."""
        try:
            # Handle different formats
            if "://" in proxy_str:
                # Format: http://user:pass@host:port
                from urllib.parse import urlparse
                parsed = urlparse(proxy_str)
                return ProxyConfig(
                    host=parsed.hostname,
                    port=parsed.port,
                    username=parsed.username,
                    password=parsed.password,
                    protocol=parsed.scheme,
                    provider=ProxyProvider.USERPROXY,
                )
            elif "@" in proxy_str:
                # Format: user:pass@host:port
                auth, host_port = proxy_str.split("@")
                username, password = auth.split(":")
                host, port = host_port.split(":")
                return ProxyConfig(
                    host=host,
                    port=int(port),
                    username=username,
                    password=password,
                    provider=ProxyProvider.USERPROXY,
                )
            else:
                # Format: host:port
                host, port = proxy_str.split(":")
                return ProxyConfig(
                    host=host,
                    port=int(port),
                    provider=ProxyProvider.USERPROXY,
                )
        except Exception:
            return None
    
    def get_proxy_for_url(self, url: str) -> Optional[ProxyConfig]:
        """Get the best proxy for a URL.
        
        This is the main method - it analyzes the URL and returns
        the best proxy automatically.
        
        Parameters
        ----------
        url : str
            Target URL.
            
        Returns
        -------
        ProxyConfig or None
            Best proxy for the URL, or None if no proxy needed.
        """
        # Analyze the site
        analysis = self.site_analyzer.analyze(url)
        
        # If no proxy needed
        if not analysis.requires_residential_proxy and not self._user_proxies:
            return None
        
        # Try to get a residential proxy if needed
        if analysis.requires_residential_proxy or self.prefer_residential:
            proxy = self._get_residential_proxy(analysis)
            if proxy:
                return proxy
        
        # Fall back to user proxies
        if self._user_proxies:
            return self._get_healthy_proxy(self._user_proxies)
        
        # Fall back to any available provider
        return self._get_proxy_from_providers(analysis)
    
    def _get_residential_proxy(self, analysis: SiteAnalysis) -> Optional[ProxyConfig]:
        """Get a residential proxy based on site analysis."""
        # Determine country based on site
        country = self._get_country_for_site(analysis)
        
        # Try providers in order of preference
        provider_order = [
            ProxyProvider.BRIGHTDATA,  # Best for residential
            ProxyProvider.OXYLABS,
            ProxyProvider.SMARTPROXY,
            ProxyProvider.SCRAPERAPI,
        ]
        
        for provider in provider_order:
            if provider in self._provider_configs:
                proxy = self._create_proxy_from_provider(provider, country)
                if proxy:
                    return proxy
        
        return None
    
    def _get_country_for_site(self, analysis: SiteAnalysis) -> Optional[str]:
        """Determine which country proxy to use based on site."""
        # US sites
        us_sites = ["amazon.com", "walmart.com", "target.com", "bestbuy.com"]
        if any(site in analysis.domain for site in us_sites):
            return "us"
        
        # UK sites
        uk_sites = ["amazon.co.uk", "bbc.co.uk", "theguardian.com"]
        if any(site in analysis.domain for site in uk_sites):
            return "uk"
        
        # India sites
        india_sites = ["flipkart.com", "myntra.com", "snapdeal.com"]
        if any(site in analysis.domain for site in india_sites):
            return "in"
        
        # Default to US
        return "us"
    
    def _create_proxy_from_provider(
        self,
        provider: ProxyProvider,
        country: Optional[str],
    ) -> Optional[ProxyConfig]:
        """Create a proxy from a provider."""
        config = self._provider_configs[provider]
        
        try:
            if provider == ProxyProvider.BRIGHTDATA:
                return self._create_brightdata_proxy(config, country)
            elif provider == ProxyProvider.OXYLABS:
                return self._create_oxylabs_proxy(config, country)
            elif provider == ProxyProvider.SMARTPROXY:
                return self._create_smartproxy_proxy(config, country)
            elif provider == ProxyProvider.SCRAPERAPI:
                return self._create_scraperapi_proxy(config, country)
        except Exception:
            return None
        
        return None
    
    def _create_brightdata_proxy(self, config: dict, country: Optional[str]) -> ProxyConfig:
        """Create Bright Data proxy."""
        api_key = config["api_key"]
        # Bright Data format: brd-customer-USER-country-COUNTRY-zone-ZONE
        username = f"brd-customer-{api_key}"
        if country:
            username += f"-country-{country}"
        username += "-zone-residential"
        
        return ProxyConfig(
            host="brd.superproxy.io",
            port=22225,
            username=username,
            password=config.get("password", ""),
            country=country,
            is_residential=True,
            provider=ProxyProvider.BRIGHTDATA,
        )
    
    def _create_oxylabs_proxy(self, config: dict, country: Optional[str]) -> ProxyConfig:
        """Create Oxylabs proxy."""
        api_key = config["api_key"]
        username = f"customer-{api_key}"
        
        return ProxyConfig(
            host="pr.oxylabs.io",
            port=7777,
            username=username,
            password=config.get("password", ""),
            country=country,
            is_residential=True,
            provider=ProxyProvider.OXYLABS,
        )
    
    def _create_smartproxy_proxy(self, config: dict, country: Optional[str]) -> ProxyConfig:
        """Create Smartproxy proxy."""
        api_key = config["api_key"]
        
        return ProxyConfig(
            host="gate.smartproxy.com",
            port=7000,
            username=api_key,
            password=config.get("password", ""),
            country=country,
            is_residential=True,
            provider=ProxyProvider.SMARTPROXY,
        )
    
    def _create_scraperapi_proxy(self, config: dict, country: Optional[str]) -> ProxyConfig:
        """Create ScraperAPI proxy."""
        api_key = config["api_key"]
        
        return ProxyConfig(
            host="proxy.scraperapi.com",
            port=8080,
            username="scraperapi",
            password=api_key,
            country=country,
            is_residential=True,
            provider=ProxyProvider.SCRAPERAPI,
        )
    
    def _get_healthy_proxy(self, proxies: List[ProxyConfig]) -> ProxyConfig:
        """Get a healthy proxy from a list."""
        # Filter healthy proxies
        healthy = []
        for proxy in proxies:
            key = f"{proxy.host}:{proxy.port}"
            health = self._proxy_health.get(key)
            if health is None or health.is_healthy:
                healthy.append(proxy)
        
        if not healthy:
            # If no healthy proxies, reset all
            for proxy in proxies:
                key = f"{proxy.host}:{proxy.port}"
                if key in self._proxy_health:
                    self._proxy_health[key].is_healthy = True
            healthy = proxies
        
        # Round-robin selection
        proxy = healthy[self._current_index % len(healthy)]
        self._current_index += 1
        
        return proxy
    
    def _get_proxy_from_providers(self, analysis: SiteAnalysis) -> Optional[ProxyConfig]:
        """Get proxy from any available provider."""
        for provider in self._provider_configs:
            proxy = self._create_proxy_from_provider(provider, None)
            if proxy:
                return proxy
        return None
    
    def report_success(self, proxy: ProxyConfig, response_time: float) -> None:
        """Report successful request with proxy."""
        key = f"{proxy.host}:{proxy.port}"
        if key not in self._proxy_health:
            self._proxy_health[key] = ProxyHealth(proxy=proxy)
        self._proxy_health[key].record_success(response_time)
    
    def report_failure(self, proxy: ProxyConfig) -> None:
        """Report failed request with proxy."""
        key = f"{proxy.host}:{proxy.port}"
        if key not in self._proxy_health:
            self._proxy_health[key] = ProxyHealth(proxy=proxy)
        self._proxy_health[key].record_failure()
    
    def get_proxy_dict(self, proxy: ProxyConfig) -> Dict[str, str]:
        """Convert ProxyConfig to requests/proxy dict."""
        if proxy.username and proxy.password:
            auth = f"{proxy.username}:{proxy.password}"
        else:
            auth = ""
        
        url = f"{proxy.protocol}://{auth}@{proxy.host}:{proxy.port}" if auth else \
              f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        
        return {
            "http": url,
            "https": url,
        }
    
    def get_status(self) -> Dict:
        """Get proxy manager status."""
        return {
            "user_proxies": len(self._user_proxies),
            "providers_available": list(self._provider_configs.keys()),
            "healthy_proxies": sum(
                1 for h in self._proxy_health.values() if h.is_healthy
            ),
            "total_proxies_tracked": len(self._proxy_health),
        }

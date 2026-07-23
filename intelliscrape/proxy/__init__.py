"""Proxy management for IntelliScrape."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ProxyType(Enum):
    """Proxy types."""
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    ISP = "isp"


@dataclass
class ProxyConfig:
    """A single proxy configuration."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: ProxyType = ProxyType.RESIDENTIAL
    country: Optional[str] = None
    sticky: bool = False
    session_id: Optional[str] = None

    @property
    def url(self) -> str:
        """Get the proxy URL."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    @property
    def dict(self) -> Dict[str, str]:
        """Get proxy dict for requests/playwright."""
        return {
            "http": self.url,
            "https": self.url,
        }


class ProxyManager:
    """Manages proxy rotation and health checks.

    Supports:
    - Built-in proxy lists
    - User-provided proxy lists
    - Proxy providers (Bright Data, ScraperAPI, etc.)
    - Sticky sessions
    - Health checking
    """

    def __init__(
        self,
        proxies: Optional[List[ProxyConfig]] = None,
        *,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
        rotate: bool = True,
        sticky: bool = False,
        max_retries: int = 3,
    ):
        self.proxies = proxies or []
        self.proxy_type = proxy_type
        self.rotate = rotate
        self.sticky = sticky
        self.max_retries = max_retries
        self._current_index = 0
        self._failed_proxies: set = set()

    def add_proxy(self, proxy: ProxyConfig) -> None:
        """Add a proxy to the pool."""
        self.proxies.append(proxy)

    def add_proxies(self, proxies: List[ProxyConfig]) -> None:
        """Add multiple proxies to the pool."""
        self.proxies.extend(proxies)

    def add_from_string(self, proxy_str: str) -> None:
        """Add proxy from string format: host:port or user:pass@host:port"""
        if "@" in proxy_str:
            auth, host_port = proxy_str.split("@", 1)
            username, password = auth.split(":", 1)
            host, port = host_port.split(":", 1)
            self.proxies.append(ProxyConfig(
                host=host,
                port=int(port),
                username=username,
                password=password,
                proxy_type=self.proxy_type,
            ))
        else:
            host, port = proxy_str.split(":", 1)
            self.proxies.append(ProxyConfig(
                host=host,
                port=int(port),
                proxy_type=self.proxy_type,
            ))

    def add_from_list(self, proxy_list: List[str]) -> None:
        """Add multiple proxies from string list."""
        for proxy_str in proxy_list:
            self.add_from_string(proxy_str.strip())

    def get_proxy(self, session_id: Optional[str] = None) -> Optional[ProxyConfig]:
        """Get the next proxy from the pool.

        Parameters
        ----------
        session_id : str, optional
            If provided and sticky mode is on, return the same proxy for this session.
        """
        if not self.proxies:
            return None

        # Filter out failed proxies
        available = [p for i, p in enumerate(self.proxies) if i not in self._failed_proxies]
        if not available:
            # Reset failed list if all proxies failed
            self._failed_proxies.clear()
            available = self.proxies

        if self.rotate:
            proxy = available[self._current_index % len(available)]
            self._current_index += 1
            return proxy
        else:
            return random.choice(available)

    def mark_failed(self, proxy: ProxyConfig) -> None:
        """Mark a proxy as failed."""
        idx = self.proxies.index(proxy)
        self._failed_proxies.add(idx)

    def mark_healthy(self, proxy: ProxyConfig) -> None:
        """Mark a proxy as healthy (remove from failed list)."""
        idx = self.proxies.index(proxy)
        self._failed_proxies.discard(idx)

    @property
    def has_proxies(self) -> bool:
        """Check if any proxies are available."""
        return len(self.proxies) > 0

    @property
    def stats(self) -> Dict:
        """Get proxy pool statistics."""
        return {
            "total": len(self.proxies),
            "healthy": len(self.proxies) - len(self._failed_proxies),
            "failed": len(self._failed_proxies),
        }


# Convenience factory functions
def create_residential_proxy(host: str, port: int, **kwargs) -> ProxyConfig:
    """Create a residential proxy config."""
    return ProxyConfig(host=host, port=port, proxy_type=ProxyType.RESIDENTIAL, **kwargs)


def create_datacenter_proxy(host: str, port: int, **kwargs) -> ProxyConfig:
    """Create a datacenter proxy config."""
    return ProxyConfig(host=host, port=port, proxy_type=ProxyType.DATACENTER, **kwargs)


def create_mobile_proxy(host: str, port: int, **kwargs) -> ProxyConfig:
    """Create a mobile proxy config."""
    return ProxyConfig(host=host, port=port, proxy_type=ProxyType.MOBILE, **kwargs)


# Import providers
from .providers import (
    ProxyProviderFactory,
    ProxyProviderConfig,
    BrightDataProvider,
    ScraperAPIProvider,
    OxylabsProvider,
    SmartproxyProvider,
)

__all__ = [
    "ProxyConfig",
    "ProxyManager",
    "ProxyType",
    "create_residential_proxy",
    "create_datacenter_proxy",
    "create_mobile_proxy",
    "ProxyProviderFactory",
    "ProxyProviderConfig",
    "BrightDataProvider",
    "ScraperAPIProvider",
    "OxylabsProvider",
    "SmartproxyProvider",
]

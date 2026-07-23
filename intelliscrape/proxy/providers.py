"""Proxy provider integrations for IntelliScrape.

Supported providers:
- Bright Data (residential, datacenter, mobile)
- ScraperAPI (proxy + rendering)
- Oxylabs (residential, datacenter)
- Smartproxy (residential)
- IPRoyal (residential)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlencode

from . import ProxyConfig, ProxyType


@dataclass
class ProxyProviderConfig:
    """Configuration for a proxy provider."""
    api_key: str
    username: Optional[str] = None
    password: Optional[str] = None
    zone: Optional[str] = None
    country: Optional[str] = None
    session_id: Optional[str] = None


class BrightDataProvider:
    """Bright Data proxy provider.

    Supports residential, datacenter, and mobile proxies.
    """

    def __init__(self, config: ProxyProviderConfig):
        self.config = config

    def get_proxy(
        self,
        *,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        """Get a Bright Data proxy.

        Parameters
        ----------
        country : str, optional
            Country code (e.g., "us", "uk", "de").
        session_id : str, optional
            Sticky session ID.
        proxy_type : ProxyType
            Type of proxy.
        """
        username = self.config.username or self.config.api_key
        password = self.config.password or ""

        # Build username with options
        parts = [username]

        if country or self.config.country:
            parts.append(f"country-{country or self.config.country}")

        if session_id or self.config.session_id:
            parts.append(f"session-{session_id or self.config.session_id}")

        proxy_type_map = {
            ProxyType.RESIDENTIAL: "brd",
            ProxyType.DATACENTER: "brd-dc",
            ProxyType.MOBILE: "brd-mobile",
        }

        zone = proxy_type_map.get(proxy_type, "brd")
        if self.config.zone:
            zone = self.config.zone

        parts.append(zone)

        return ProxyConfig(
            host="brd.superproxy.io",
            port=22225,
            username=":".join(parts),
            password=password,
            proxy_type=proxy_type,
            country=country or self.config.country,
            sticky=bool(session_id or self.config.session_id),
            session_id=session_id or self.config.session_id,
        )

    def get_session_proxy(
        self,
        session_id: str,
        *,
        country: Optional[str] = None,
    ) -> ProxyConfig:
        """Get a sticky session proxy."""
        return self.get_proxy(country=country, session_id=session_id)


class ScraperAPIProvider:
    """ScraperAPI proxy provider.

    ScraperAPI handles proxies, browsers, and CAPTCHAs.
    """

    def __init__(self, config: ProxyProviderConfig):
        self.config = config

    def get_proxy(
        self,
        *,
        country: Optional[str] = None,
        render_js: bool = True,
        premium: bool = False,
    ) -> ProxyConfig:
        """Get a ScraperAPI proxy.

        Parameters
        ----------
        country : str, optional
            Country code.
        render_js : bool
            Enable JavaScript rendering.
        premium : bool
            Use premium proxies.
        """
        params = {
            "api_key": self.config.api_key,
        }

        if country:
            params["country_code"] = country

        if render_js:
            params["render"] = "true"

        if premium:
            params["premium"] = "true"

        # ScraperAPI uses a single endpoint with API key
        return ProxyConfig(
            host="proxy.scraperapi.com",
            port=8080,
            username="scraperapi",
            password=self.config.api_key,
            proxy_type=ProxyType.RESIDENTIAL,
            country=country,
        )

    def get_url(self, url: str, **params) -> str:
        """Get ScraperAPI URL for direct requests.

        Parameters
        ----------
        url : str
            Target URL.
        **params
            Additional ScraperAPI parameters.

        Returns
        -------
        str
            ScraperAPI URL.
        """
        request_params = {
            "api_key": self.config.api_key,
            "url": url,
        }
        request_params.update(params)
        return f"https://api.scraperapi.com/?{urlencode(request_params)}"


class OxylabsProvider:
    """Oxylabs proxy provider.

    Supports residential and datacenter proxies.
    """

    def __init__(self, config: ProxyProviderConfig):
        self.config = config

    def get_proxy(
        self,
        *,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        """Get an Oxylabs proxy."""
        username = self.config.username or self.config.api_key
        password = self.config.password or ""

        if session_id or self.config.session_id:
            username = f"customer-{username}-session-{session_id or self.config.session_id}"

        host = "pr.oxylabs.io" if proxy_type == ProxyType.RESIDENTIAL else "dc.oxylabs.io"

        return ProxyConfig(
            host=host,
            port=7777,
            username=username,
            password=password,
            proxy_type=proxy_type,
            country=country or self.config.country,
            sticky=bool(session_id),
            session_id=session_id,
        )


class SmartproxyProvider:
    """Smartproxy provider.

    Residential proxies with sticky sessions.
    """

    def __init__(self, config: ProxyProviderConfig):
        self.config = config

    def get_proxy(
        self,
        *,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ProxyConfig:
        """Get a Smartproxy proxy."""
        username = self.config.username or self.config.api_key
        password = self.config.password or ""

        if session_id:
            username = f"user-session-{session_id}"

        return ProxyConfig(
            host="gate.smartproxy.com",
            port=7000,
            username=username,
            password=password,
            proxy_type=ProxyType.RESIDENTIAL,
            country=country or self.config.country,
            sticky=bool(session_id),
            session_id=session_id,
        )


class ProxyProviderFactory:
    """Factory for creating proxy providers."""

    PROVIDERS = {
        "brightdata": BrightDataProvider,
        "scraperapi": ScraperAPIProvider,
        "oxylabs": OxylabsProvider,
        "smartproxy": SmartproxyProvider,
    }

    @classmethod
    def create(
        cls,
        provider_name: str,
        config: ProxyProviderConfig,
    ):
        """Create a proxy provider.

        Parameters
        ----------
        provider_name : str
            Provider name ("brightdata", "scraperapi", "oxylabs", "smartproxy").
        config : ProxyProviderConfig
            Provider configuration.

        Returns
        -------
        Proxy provider instance.
        """
        provider_class = cls.PROVIDERS.get(provider_name.lower())
        if not provider_class:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {', '.join(cls.PROVIDERS.keys())}"
            )
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List available providers."""
        return list(cls.PROVIDERS.keys())

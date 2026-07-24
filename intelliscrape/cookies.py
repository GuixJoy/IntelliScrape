"""Cookie persistence for IntelliScrape."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from http.cookiejar import Cookie, CookieJar
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class CookieData:
    """Cookie data structure."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[int] = None
    secure: bool = False
    http_only: bool = True
    same_site: str = "Lax"


class CookieManager:
    """Manage cookie persistence across sessions."""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize cookie manager.
        
        Parameters
        ----------
        storage_dir : str, optional
            Directory to store cookie files.
            Defaults to ~/.intelliscrape/cookies/
        """
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".intelliscrape" / "cookies"
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cookies: Dict[str, List[CookieData]] = {}
    
    def save_cookies(
        self,
        url: str,
        cookies: Dict[str, str],
        *,
        domain: Optional[str] = None,
        path: str = "/",
        expires: Optional[int] = None,
        secure: bool = False,
    ) -> None:
        """Save cookies for a URL.
        
        Parameters
        ----------
        url : str
            URL to associate cookies with.
        cookies : dict
            Dictionary of cookie_name -> cookie_value.
        domain : str, optional
            Cookie domain. If None, extracted from URL.
        path : str
            Cookie path.
        expires : int, optional
            Expiration timestamp.
        secure : bool
            Whether cookie is secure.
        """
        if not domain:
            parsed = urlparse(url)
            domain = parsed.netloc
        
        cookie_list = []
        for name, value in cookies.items():
            cookie_data = CookieData(
                name=name,
                value=value,
                domain=domain,
                path=path,
                expires=expires,
                secure=secure,
            )
            cookie_list.append(cookie_data)
        
        self.cookies[url] = cookie_list
        self._save_to_file(url, cookie_list)
    
    def load_cookies(self, url: str) -> Dict[str, str]:
        """Load cookies for a URL.
        
        Parameters
        ----------
        url : str
            URL to load cookies for.
            
        Returns
        -------
        dict
            Dictionary of cookie_name -> cookie_value.
        """
        # Try memory first
        if url in self.cookies:
            return {c.name: c.value for c in self.cookies[url]}
        
        # Try file
        cookie_list = self._load_from_file(url)
        if cookie_list:
            self.cookies[url] = cookie_list
            return {c.name: c.value for c in cookie_list}
        
        return {}
    
    def get_cookie_jar(self, url: str) -> CookieJar:
        """Get a CookieJar for a URL.
        
        Parameters
        ----------
        url : str
            URL to get cookies for.
            
        Returns
        -------
        CookieJar
            Cookie jar with loaded cookies.
        """
        jar = CookieJar()
        cookies = self.load_cookies(url)
        
        parsed = urlparse(url)
        
        for name, value in cookies.items():
            cookie = Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=parsed.netloc,
                domain_specified=True,
                domain_initial_dot=parsed.netloc.startswith("."),
                path=parsed.path,
                path_specified=True,
                secure=False,
                expires=int(time.time()) + 86400,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            jar.set_cookie(cookie)
        
        return jar
    
    def clear_cookies(self, url: Optional[str] = None) -> None:
        """Clear cookies.
        
        Parameters
        ----------
        url : str, optional
            URL to clear cookies for. If None, clears all.
        """
        if url:
            if url in self.cookies:
                del self.cookies[url]
            self._delete_file(url)
        else:
            self.cookies.clear()
            # Delete all cookie files
            for file in self.storage_dir.glob("*.json"):
                file.unlink()
    
    def has_cookies(self, url: str) -> bool:
        """Check if cookies exist for a URL."""
        return url in self.cookies or self._load_from_file(url) is not None
    
    def get_all_domains(self) -> List[str]:
        """Get all domains with saved cookies."""
        domains = set()
        
        # From memory
        for url in self.cookies:
            parsed = urlparse(url)
            domains.add(parsed.netloc)
        
        # From files
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                if "domain" in data:
                    domains.add(data["domain"])
            except:
                pass
        
        return list(domains)
    
    def _save_to_file(self, url: str, cookies: List[CookieData]) -> None:
        """Save cookies to file."""
        filename = self._get_filename(url)
        filepath = self.storage_dir / filename
        
        data = {
            "url": url,
            "domain": urlparse(url).netloc,
            "cookies": [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "expires": c.expires,
                    "secure": c.secure,
                    "http_only": c.http_only,
                    "same_site": c.same_site,
                }
                for c in cookies
            ],
            "saved_at": int(time.time()),
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    def _load_from_file(self, url: str) -> Optional[List[CookieData]]:
        """Load cookies from file."""
        filename = self._get_filename(url)
        filepath = self.storage_dir / filename
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            return [
                CookieData(**cookie)
                for cookie in data.get("cookies", [])
            ]
        except:
            return None
    
    def _delete_file(self, url: str) -> None:
        """Delete cookie file."""
        filename = self._get_filename(url)
        filepath = self.storage_dir / filename
        
        if filepath.exists():
            filepath.unlink()
    
    def _get_filename(self, url: str) -> str:
        """Get filename for URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.replace(":", "_").replace(".", "_")
        return f"{domain}.json"

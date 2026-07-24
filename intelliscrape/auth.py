"""Authentication and session management for IntelliScrape."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import requests
from requests import Session


@dataclass
class LoginCredentials:
    """Login credentials for a website."""
    username_field: str = "username"
    password_field: str = "password"
    username: str = ""
    password: str = ""
    extra_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class AuthSession:
    """Persistent authenticated session."""
    base_url: str
    cookies: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    is_authenticated: bool = False
    last_url: str = ""


class Authenticator:
    """Handle authentication and session persistence."""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or requests.Session()
        self.sessions: Dict[str, AuthSession] = {}
        self.session_dir = Path.home() / ".intelliscrape" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def login(
        self,
        url: str,
        credentials: LoginCredentials,
        *,
        login_url: Optional[str] = None,
        success_indicator: Optional[str] = None,
        timeout: int = 30,
    ) -> bool:
        """Login to a website.
        
        Parameters
        ----------
        url : str
            The website URL (e.g., "https://linkedin.com").
        credentials : LoginCredentials
            Login credentials.
        login_url : str, optional
            Explicit login URL. If None, tries to find login form.
        success_indicator : str, optional
            HTML text that indicates successful login.
        timeout : int
            Request timeout in seconds.
            
        Returns
        -------
        bool
            True if login successful.
        """
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Determine login URL
        if not login_url:
            login_url = self._find_login_url(base_url, timeout)
        
        # Prepare form data
        form_data = {
            credentials.username_field: credentials.username,
            credentials.password_field: credentials.password,
        }
        form_data.update(credentials.extra_fields)
        
        # Attempt login
        try:
            # First GET the login page to get any CSRF tokens
            login_page = self.session.get(login_url, timeout=timeout)
            
            # Extract CSRF token if present
            csrf_token = self._extract_csrf(login_page.text)
            if csrf_token:
                form_data["csrf_token"] = csrf_token
            
            # Submit login form
            response = self.session.post(
                login_url,
                data=form_data,
                timeout=timeout,
                allow_redirects=True,
            )
            
            # Check if login successful
            if success_indicator:
                is_success = success_indicator.lower() in response.text.lower()
            else:
                # Check if we got redirected to a dashboard/home page
                is_success = response.status_code == 200 and (
                    response.url != login_url or
                    "logout" in response.text.lower() or
                    "dashboard" in response.text.lower() or
                    "profile" in response.text.lower()
                )
            
            if is_success:
                # Store session
                session_data = AuthSession(
                    base_url=base_url,
                    cookies=dict(self.session.cookies),
                    headers=dict(self.session.headers),
                    is_authenticated=True,
                    last_url=response.url,
                )
                self.sessions[base_url] = session_data
                self._save_session(base_url, session_data)
            
            return is_success
            
        except Exception as e:
            print(f"Login failed: {e}")
            return False
    
    def logout(self, url: str) -> bool:
        """Logout from a website."""
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        if base_url in self.sessions:
            del self.sessions[base_url]
            self._delete_session(base_url)
            self.session.cookies.clear()
            return True
        return False
    
    def is_logged_in(self, url: str) -> bool:
        """Check if logged in to a website."""
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        if base_url in self.sessions:
            return self.sessions[base_url].is_authenticated
        return False
    
    def get_session(self, url: str) -> Optional[Session]:
        """Get authenticated session for a website."""
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try to load saved session
        if base_url not in self.sessions:
            saved = self._load_session(base_url)
            if saved and saved.is_authenticated:
                self.sessions[base_url] = saved
                # Restore cookies
                self.session.cookies.update(saved.cookies)
        
        if base_url in self.sessions and self.sessions[base_url].is_authenticated:
            return self.session
        return None
    
    def save_cookies(self, url: str, cookies: Dict[str, str]) -> None:
        """Manually save cookies for a URL."""
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        session_data = AuthSession(
            base_url=base_url,
            cookies=cookies,
            is_authenticated=True,
        )
        self.sessions[base_url] = session_data
        self._save_session(base_url, session_data)
    
    def load_cookies(self, url: str) -> Dict[str, str]:
        """Load saved cookies for a URL."""
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        if base_url in self.sessions:
            return self.sessions[base_url].cookies
        return {}
    
    def _find_login_url(self, base_url: str, timeout: int) -> str:
        """Try to find the login URL."""
        common_paths = [
            "/login", "/signin", "/auth", "/account/login",
            "/user/login", "/members/login", "/wp-login.php",
        ]
        
        for path in common_paths:
            try:
                url = urljoin(base_url, path)
                response = self.session.head(url, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    return url
            except:
                continue
        
        # Default to base URL
        return base_url
    
    def _extract_csrf(self, html: str) -> Optional[str]:
        """Extract CSRF token from HTML."""
        import re
        
        # Common CSRF patterns
        patterns = [
            r'<input[^>]*name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'<input[^>]*name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'<input[^>]*name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _save_session(self, base_url: str, session_data: AuthSession) -> None:
        """Save session to file."""
        filename = base_url.replace("://", "_").replace("/", "_").replace(".", "_")
        filepath = self.session_dir / f"{filename}.json"
        
        data = {
            "base_url": session_data.base_url,
            "cookies": session_data.cookies,
            "headers": session_data.headers,
            "is_authenticated": session_data.is_authenticated,
            "last_url": session_data.last_url,
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    def _load_session(self, base_url: str) -> Optional[AuthSession]:
        """Load session from file."""
        filename = base_url.replace("://", "_").replace("/", "_").replace(".", "_")
        filepath = self.session_dir / f"{filename}.json"
        
        if filepath.exists():
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                return AuthSession(**data)
            except:
                pass
        return None
    
    def _delete_session(self, base_url: str) -> None:
        """Delete session file."""
        filename = base_url.replace("://", "_").replace("/", "_").replace(".", "_")
        filepath = self.session_dir / f"{filename}.json"
        
        if filepath.exists():
            filepath.unlink()

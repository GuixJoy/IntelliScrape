"""Authentication and session management for IntelliScrape."""

from __future__ import annotations

import json
import os
import re
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
    auth_token: str = ""  # JWT/Firebase token for SPA auth


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

        # Attempt login
        try:
            # GET the login page to get CSRF tokens and detect form fields
            login_page = self.session.get(login_url, timeout=timeout, allow_redirects=True)
            login_page_url = login_page.url

            # Check if this is an SPA (Single Page Application)
            is_spa = self._is_spa(login_page.text)

            if is_spa:
                # Use Playwright for SPA login
                return self._login_spa(
                    login_page_url, credentials, success_indicator, timeout
                )

            # Auto-detect form fields from HTML
            detected_fields = self._detect_form_fields(login_page.text)
            username_field = detected_fields.get("username_field", credentials.username_field)
            password_field = detected_fields.get("password_field", credentials.password_field)

            # Build form data with detected fields
            form_data = {
                username_field: credentials.username,
                password_field: credentials.password,
            }
            form_data.update(credentials.extra_fields)

            # Extract all hidden fields (CSRF tokens, etc.)
            hidden_fields = self._extract_hidden_fields(login_page.text)
            form_data.update(hidden_fields)

            # Determine form action URL
            form_action = self._extract_form_action(login_page.text, login_page_url)
            post_url = form_action or login_page_url

            # Capture cookies before login
            cookies_before = set(self.session.cookies.keys())

            # Submit login form
            response = self.session.post(
                post_url,
                data=form_data,
                timeout=timeout,
                allow_redirects=True,
            )

            # Capture cookies after login
            cookies_after = set(self.session.cookies.keys())
            new_cookies = cookies_after - cookies_before

            # Check if login successful
            if success_indicator:
                is_success = success_indicator.lower() in response.text.lower()
            else:
                is_success = self._check_login_success(
                    response=response,
                    login_url=login_page_url,
                    new_cookies=new_cookies,
                    cookies_before=cookies_before,
                )

            if is_success:
                # Store session
                session_data = AuthSession(
                    base_url=base_url,
                    cookies=dict(self.session.cookies),
                    headers=dict(self.session.headers),
                    is_authenticated=True,
                    last_url=response.url,
                    auth_token=auth_token or "",
                )
                self.sessions[base_url] = session_data
                self._save_session(base_url, session_data)

            return is_success

        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def _check_login_success(
        self,
        response: requests.Response,
        login_url: str,
        new_cookies: set,
        cookies_before: set,
    ) -> bool:
        """Check if login was successful using multiple signals."""
        # Signal 1: Got new cookies (strongest signal)
        if new_cookies:
            return True

        # Signal 2: Redirected away from login page
        if response.url != login_url:
            return True

        # Signal 3: Response no longer contains login form
        has_login_form = bool(
            re.search(r'<form[^>]*(?:login|signin|auth)[^>]*>', response.text, re.IGNORECASE)
            or re.search(r'type=["\']password["\']', response.text, re.IGNORECASE)
        )
        if not has_login_form and response.status_code == 200:
            return True

        # Signal 4: Contains common post-login indicators
        post_login_keywords = [
            "logout", "sign out", "signout", "log out", "logout",
            "dashboard", "profile", "account", "settings", "welcome",
            "my account", "console", "portal",
        ]
        response_lower = response.text.lower()
        for keyword in post_login_keywords:
            if keyword in response_lower:
                return True

        # Signal 5: Status code is 200 and cookies exist (weaker signal)
        if response.status_code == 200 and len(self.session.cookies) > 0:
            return True

        return False

    def _detect_form_fields(self, html: str) -> Dict[str, str]:
        """Auto-detect username and password field names from login form."""
        result = {"username_field": "username", "password_field": "password"}

        # Find the login form
        form_match = re.search(
            r'<form[^>]*(?:login|signin|auth|account)[^>]*>(.*?)</form>',
            html, re.IGNORECASE | re.DOTALL
        )
        if not form_match:
            # Try finding any form with a password field
            form_match = re.search(
                r'<form[^>]*>(.*?)</form>',
                html, re.IGNORECASE | re.DOTALL
            )

        if not form_match:
            return result

        form_html = form_match.group(1)

        # Detect username/email field
        username_patterns = [
            (r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:type=["\'](?:text|email)["\'][^>]*(?:placeholder|aria-label)[^>]*(?:user|email|login|phone|mobile))', "username"),
            (r'<input[^>]*(?:placeholder|aria-label)[^>]*(?:user|email|login|phone|mobile)[^>]*name=["\']([^"\']+)["\']', "username"),
            (r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']email["\']', "email"),
            (r'<input[^>]*type=["\']email["\'][^>]*name=["\']([^"\']+)["\']', "email"),
            (r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:placeholder|aria-label)[^>]*(?:user|email|login)', "username"),
            (r'<input[^>]*(?:placeholder|aria-label)[^>]*(?:user|email|login)[^>]*name=["\']([^"\']+)["\']', "username"),
        ]

        for pattern, field_type in username_patterns:
            match = re.search(pattern, form_html, re.IGNORECASE)
            if match:
                result["username_field"] = match.group(1)
                break

        # Detect password field
        password_match = re.search(
            r'<input[^>]*type=["\']password["\'][^>]*name=["\']([^"\']+)["\']',
            form_html, re.IGNORECASE
        )
        if not password_match:
            password_match = re.search(
                r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']password["\']',
                form_html, re.IGNORECASE
            )
        if password_match:
            result["password_field"] = password_match.group(1)

        return result

    def _extract_hidden_fields(self, html: str) -> Dict[str, str]:
        """Extract all hidden input fields from a form."""
        hidden_fields = {}
        # Match hidden inputs
        pattern = r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']'
        for match in re.finditer(pattern, html, re.IGNORECASE):
            name, value = match.group(1), match.group(2)
            if value:  # Only include fields with values
                hidden_fields[name] = value

        # Also match inputs where name comes before type
        pattern2 = r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']hidden["\'][^>]*value=["\']([^"\']*)["\']'
        for match in re.finditer(pattern2, html, re.IGNORECASE):
            name, value = match.group(1), match.group(2)
            if value and name not in hidden_fields:
                hidden_fields[name] = value

        return hidden_fields

    def _extract_form_action(self, html: str, page_url: str) -> Optional[str]:
        """Extract the form action URL from a login form."""
        # Find form with login/auth in it
        form_match = re.search(
            r'<form[^>]*(?:login|signin|auth|account)[^>]*action=["\']([^"\']*)["\']',
            html, re.IGNORECASE
        )
        if form_match:
            action = form_match.group(1)
            if action:
                return urljoin(page_url, action)

        # Find any form with a password field
        form_match = re.search(
            r'<form[^>]*action=["\']([^"\']*)["\'][^>]*>.*?type=["\']password["\']',
            html, re.IGNORECASE | re.DOTALL
        )
        if form_match:
            action = form_match.group(1)
            if action:
                return urljoin(page_url, action)

        return None

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
            "/login", "/signin", "/sign-in", "/auth", "/auth/login",
            "/account/login", "/user/login", "/members/login",
            "/wp-login.php", "/admin/login", "/portal/login",
            "/api/login", "/accounts/login", "/session/new",
            "/identify", "/challenge", "/sso/login",
        ]

        for path in common_paths:
            try:
                url = urljoin(base_url, path)
                response = self.session.head(url, timeout=timeout, allow_redirects=True)
                if response.status_code in (200, 302, 301):
                    return url
            except Exception:
                continue

        # Default to base URL
        return base_url

    def _is_spa(self, html: str) -> bool:
        """Detect if the page is a Single Page Application (SPA)."""
        spa_indicators = [
            # React/Vue/Angular root div with no form
            r'<div\s+id=["\']root["\'][^>]*>\s*</div>',
            r'<div\s+id=["\']app["\'][^>]*>\s*</div>',
            r'<div\s+id=["\']__next["\'][^>]*>\s*</div>',
            r'<div\s+id=["\']__nuxt["\'][^>]*>\s*</div>',
            # Heavy JS bundles
            r'<script[^>]*src=["\'][^"\']*\.js["\'][^>]*>',
            # No form tags at all
        ]
        html_lower = html.lower()

        # Check for SPA root divs
        for pattern in spa_indicators:
            if re.search(pattern, html, re.IGNORECASE):
                return True

        # Check if there's a root/app div with no forms
        has_root = bool(re.search(r'<div\s+id=["\'](?:root|app|__next|__nuxt)["\']', html, re.IGNORECASE))
        has_forms = bool(re.search(r'<form[^>]*>', html, re.IGNORECASE))
        has_password = bool(re.search(r'type=["\']password["\']', html, re.IGNORECASE))

        # If there's a root div but no forms/password fields, it's likely an SPA
        if has_root and not has_forms and not has_password:
            return True

        return False

    def _login_spa(
        self,
        url: str,
        credentials: LoginCredentials,
        success_indicator: Optional[str],
        timeout: int,
    ) -> bool:
        """Login to an SPA using Playwright (headless browser)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        try:
            with sync_playwright() as p:
                # Step 1: Try automated login (headless)
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                page = context.new_page()

                # Navigate to login page
                page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                page.wait_for_timeout(2000)

                # Try to find and fill login form
                auto_login_success = self._try_automated_login(page, credentials)

                if auto_login_success:
                    # Check for Firebase errors
                    page_content = page.content()
                    firebase_errors = [
                        "auth/invalid-credential",
                        "auth/user-not-found",
                        "auth/wrong-password",
                        "auth/too-many-requests",
                        "auth/user-disabled",
                        "Firebase: Error",
                    ]
                    has_error = any(error.lower() in page_content.lower() for error in firebase_errors)

                    if not has_error:
                        # Automated login succeeded
                        session_data = self._extract_session(page, context, url)
                        browser.close()
                        if session_data:
                            self.sessions[session_data.base_url] = session_data
                            self._save_session(session_data.base_url, session_data)
                            return True

                # Step 2: Automated login failed, open visible browser for manual login
                browser.close()
                print("\n[SPA Login] Automated login failed. Opening browser for manual login...")
                print("[SPA Login] Please login manually in the browser window.")
                print("[SPA Login] Press Enter here after you've logged in...")

                return self._login_manual(p, url, timeout)

        except Exception as e:
            print(f"SPA login failed: {e}")
            return False

    def _try_automated_login(self, page, credentials: LoginCredentials) -> bool:
        """Try to fill and submit the login form automatically."""
        try:
            # Wait for login form to appear
            page.wait_for_timeout(2000)

            # Try to find email/username input
            username_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="user" i]',
                'input[name="username"]',
                'input[type="text"]',
            ]

            username_input = None
            for selector in username_selectors:
                try:
                    username_input = page.locator(selector).first
                    if username_input.is_visible():
                        break
                    username_input = None
                except Exception:
                    continue

            if not username_input:
                return False

            # Try to find password input
            password_input = None
            try:
                password_input = page.locator('input[type="password"]').first
                if not password_input.is_visible():
                    password_input = None
            except Exception:
                pass

            if not password_input:
                return False

            # Fill in credentials
            username_input.fill(credentials.username)
            page.wait_for_timeout(500)
            password_input.fill(credentials.password)
            page.wait_for_timeout(500)

            # Find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'input[type="submit"]',
            ]

            for selector in submit_selectors:
                try:
                    submit_btn = page.locator(selector).first
                    if submit_btn.is_visible():
                        submit_btn.click()
                        page.wait_for_timeout(3000)
                        return True
                except Exception:
                    continue

            # Try pressing Enter
            password_input.press("Enter")
            page.wait_for_timeout(3000)
            return True

        except Exception:
            return False

    def _login_manual(self, playwright, url: str, timeout: int) -> bool:
        """Open visible browser for manual login and wait for user."""
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # Navigate to login page
        page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

        # Record initial state
        initial_url = page.url
        initial_cookies = {c["name"]: c["value"] for c in context.cookies()}
        initial_storage = {}
        try:
            keys = page.evaluate("Object.keys(localStorage)")
            for key in keys:
                initial_storage[key] = page.evaluate(f"localStorage.getItem('{key}')")
        except Exception:
            pass

        # Wait for user to login manually
        max_wait = 300  # 5 minutes max
        check_interval = 3
        elapsed = 0

        print("[SPA Login] Browser opened. Please login manually.")
        print("[SPA Login] I'll detect when you're logged in automatically.")

        while elapsed < max_wait:
            page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval

            current_url = page.url
            current_cookies = {c["name"]: c["value"] for c in context.cookies()}
            current_storage = {}
            try:
                keys = page.evaluate("Object.keys(localStorage)")
                for key in keys:
                    current_storage[key] = page.evaluate(f"localStorage.getItem('{key}')")
            except Exception:
                pass

            # Detection: Check for changes
            new_cookies = set(current_cookies.keys()) - set(initial_cookies.keys())
            removed_cookies = set(initial_cookies.keys()) - set(current_cookies.keys())

            # Check for NEW keys in localStorage
            new_storage_keys = set(current_storage.keys()) - set(initial_storage.keys())

            # Check for CHANGED values in existing keys (Firebase updates in-place)
            changed_keys = []
            for key in current_storage:
                if key in initial_storage:
                    if current_storage[key] != initial_storage[key]:
                        changed_keys.append(key)

            # Check for auth tokens
            has_auth_token = False
            for key in new_storage_keys | set(changed_keys):
                try:
                    value = current_storage.get(key, "")
                    if value and isinstance(value, str):
                        if "firebase" in key.lower() or "auth" in key.lower():
                            # Check if it contains user/token data
                            if "stsTokenManager" in value or "uid" in value:
                                has_auth_token = True
                                break
                        if value.startswith("eyJ") and "." in value:
                            has_auth_token = True
                            break
                except Exception:
                    pass

            # Login detected if:
            # 1. New auth cookies appeared, OR
            # 2. Auth token detected in localStorage, OR
            # 3. Firebase auth data changed
            is_logged_in = (
                bool(new_cookies) or
                has_auth_token or
                bool(changed_keys)
            )

            if is_logged_in:
                print("[SPA Login] Login detected! Extracting session...")
                page.wait_for_timeout(2000)  # Wait for tokens to settle

                # Extract session
                session_data = self._extract_session(page, context, url)
                browser.close()

                if session_data:
                    self.sessions[session_data.base_url] = session_data
                    self._save_session(session_data.base_url, session_data)
                    return True
                return False

            if elapsed % 15 == 0:
                print(f"[SPA Login] Waiting for login... ({elapsed}s / {max_wait}s)")

        print("[SPA Login] Timeout waiting for login (5 minutes).")
        browser.close()
        return False

    def _extract_session(self, page, context, url: str) -> Optional[AuthSession]:
        """Extract session data (cookies + auth token) from browser."""
        base_url = urlsplit(url).scheme + "://" + urlsplit(url).netloc

        # Get cookies
        cookies = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        # Extract auth tokens from localStorage
        auth_token = None
        try:
            storage_keys = page.evaluate("Object.keys(localStorage)")
            for key in storage_keys:
                value = page.evaluate(f"localStorage.getItem('{key}')")
                if value and isinstance(value, str):
                    # Firebase Auth stores user data
                    if "firebase" in key.lower():
                        try:
                            import json as json_mod
                            user_data = json_mod.loads(value)
                            if "stsTokenManager" in user_data:
                                auth_token = user_data["stsTokenManager"].get("accessToken")
                                if auth_token:
                                    break
                        except Exception:
                            pass
                    # Check for JWT tokens
                    if value.startswith("eyJ") and "." in value:
                        auth_token = value
                        break
        except Exception:
            pass

        return AuthSession(
            base_url=base_url,
            cookies=cookie_dict,
            is_authenticated=True,
            last_url=page.url,
            auth_token=auth_token or "",
        )

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
            except Exception:
                pass
        return None

    def _delete_session(self, base_url: str) -> None:
        """Delete session file."""
        filename = base_url.replace("://", "_").replace("/", "_").replace(".", "_")
        filepath = self.session_dir / f"{filename}.json"

        if filepath.exists():
            filepath.unlink()

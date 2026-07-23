"""Cookie consent detection and handling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup


@dataclass
class CookieConsentInfo:
    """Detected cookie consent information."""
    has_consent: bool = False
    consent_type: str = ""  # "banner", "modal", "popup"
    accept_button_selector: Optional[str] = None
    reject_button_selector: Optional[str] = None
    selectors_tried: List[str] = None

    def __post_init__(self):
        if self.selectors_tried is None:
            self.selectors_tried = []


# Common cookie consent selectors
CONSENT_SELECTORS = {
    "accept": [
        # Generic
        "button.accept",
        "button.accept-all",
        "button.allow",
        "button.allow-all",
        "button.agree",
        "button.agree-all",
        "button consent-accept",
        "[data-testid='cookie-accept']",
        "[data-action='accept']",
        # CookieBot
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#CybotCookiebotDialogBodyButtonAccept",
        # OneTrust
        "#onetrust-accept-btn-handler",
        ".onetrust-close-btn-handler",
        # Quantcast
        ".qc-cmp2-summary-buttons button[mode='primary']",
        # Didomi
        "#didomi-notice-agree-button",
        # Osano
        ".osano-cm-accept-all",
        # TrustArc
        "#truste-consent-button",
        # CookieYes
        ".cky-btn-accept",
        # Iubenda
        ".iubenda-cs-accept-btn",
        # Complianz
        ".cmplz-accept",
        # Usercentrics
        "[data-testid='uc-accept-all-button']",
        # Axeptio
        ".axeptio_widget button[class*='accept']",
        # Klaro
        ".klaro .cm-btn-accept",
        # Cookie Notice
        "#cookie-notice .cn-set-cookie",
        # GDPR Cookie Consent
        "#cookie-law-info-bar .cli-plugin-button",
    ],
    "reject": [
        "button.reject",
        "button.reject-all",
        "button.decline",
        "button.decline-all",
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinDecline",
        "#onetrust-reject-all-handler",
        ".qc-cmp2-summary-buttons button[mode='secondary']",
        "#didomi-notice-disagree-button",
        ".cky-btn-reject",
    ],
}


class CookieConsentHandler:
    """Detects and handles cookie consent banners."""

    @classmethod
    def detect(cls, html: str) -> CookieConsentInfo:
        """Detect cookie consent banner in HTML.

        Parameters
        ----------
        html : str
            Page HTML content.

        Returns
        -------
        CookieConsentInfo
            Detected consent information.
        """
        soup = BeautifulSoup(html, "html.parser")
        html_lower = html.lower()

        # Check for common consent indicators
        consent_indicators = [
            "cookie consent",
            "cookie policy",
            "cookie notice",
            "cookie banner",
            "privacy policy",
            "we use cookies",
            "this website uses cookies",
            "cookie law",
            "gdpr",
            "data protection",
        ]

        has_indicator = any(indicator in html_lower for indicator in consent_indicators)

        if not has_indicator:
            return CookieConsentInfo(has_consent=False)

        # Try to find accept button
        accept_selector = None
        tried_selectors = []

        for selector in CONSENT_SELECTORS["accept"]:
            tried_selectors.append(selector)
            try:
                element = soup.select_one(selector)
                if element:
                    accept_selector = selector
                    break
            except Exception:
                pass

        # Try to find reject button
        reject_selector = None
        for selector in CONSENT_SELECTORS["reject"]:
            try:
                element = soup.select_one(selector)
                if element:
                    reject_selector = selector
                    break
            except Exception:
                pass

        # Determine consent type
        consent_type = "banner"  # Default
        if soup.find("div", class_=re.compile(r"modal|popup|overlay")):
            consent_type = "modal"
        elif soup.find("div", class_=re.compile(r"popup|dialog")):
            consent_type = "popup"

        return CookieConsentInfo(
            has_consent=True,
            consent_type=consent_type,
            accept_button_selector=accept_selector,
            reject_button_selector=reject_selector,
            selectors_tried=tried_selectors,
        )

    @classmethod
    def get_click_script(cls, consent_info: CookieConsentInfo) -> Optional[str]:
        """Get JavaScript to click the accept button.

        Parameters
        ----------
        consent_info : CookieConsentInfo
            Detected consent information.

        Returns
        -------
        str or None
            JavaScript code to click the button, or None if no button found.
        """
        if not consent_info.accept_button_selector:
            return None

        selector = consent_info.accept_button_selector
        return f"""
        (function() {{
            const btn = document.querySelector('{selector}');
            if (btn) {{
                btn.click();
                return true;
            }}
            return false;
        }})();
        """

    @classmethod
    async def handle_consent(cls, page, consent_info: Optional[CookieConsentInfo] = None):
        """Handle cookie consent on a Playwright page.

        Parameters
        ----------
        page : playwright.Page
            The page to handle consent on.
        consent_info : CookieConsentInfo, optional
            Pre-detected consent info. If None, will detect.
        """
        if consent_info is None:
            html = await page.content()
            consent_info = cls.detect(html)

        if not consent_info.has_consent:
            return

        if consent_info.accept_button_selector:
            try:
                await page.click(consent_info.accept_button_selector, timeout=5000)
                await page.wait_for_timeout(1000)
            except Exception:
                # Try JavaScript click as fallback
                script = cls.get_click_script(consent_info)
                if script:
                    try:
                        await page.evaluate(script)
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass

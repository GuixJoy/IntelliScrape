"""Intelligent URL analysis and scraping strategy.

This is what makes IntelliScrape truly intelligent.
It detects from the URL what approach to use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlparse


class SiteType(Enum):
    """Types of websites."""
    ECOMMERCE = "ecommerce"
    SOCIAL = "social"
    NEWS = "news"
    TECH = "tech"
    GOVERNMENT = "government"
    EDUCATION = "education"
    ENTERPRISE = "enterprise"
    BLOG = "blog"
    FORUM = "forum"
    UNKNOWN = "unknown"


class ProtectionLevel(Enum):
    """Level of bot protection."""
    NONE = "none"
    BASIC = "basic"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class SiteAnalysis:
    """Analysis of a website."""
    url: str
    domain: str
    site_type: SiteType
    protection_level: ProtectionLevel
    requires_browser: bool
    requires_residential_proxy: bool
    recommended_engine: str
    recommended_delay: float
    recommended_batch_size: int
    notes: List[str]


class SiteAnalyzer:
    """Analyze URLs and determine the best scraping approach."""
    
    # Site patterns and their characteristics
    SITE_PATTERNS = {
        SiteType.ECOMMERCE: {
            "domains": [
                "amazon", "ebay", "flipkart", "walmart", "target",
                "bestbuy", "etsy", "shopify", "aliexpress", "wish",
                "myntra", "jabong", "snapdeal", "paytm",
            ],
            "protection": ProtectionLevel.HIGH,
            "requires_browser": True,
            "requires_residential": True,
            "delay": 3.0,
            "batch_size": 5,
        },
        SiteType.SOCIAL: {
            "domains": [
                "facebook", "twitter", "x.com", "instagram", "linkedin",
                "tiktok", "reddit", "pinterest", "snapchat", "youtube",
            ],
            "protection": ProtectionLevel.EXTREME,
            "requires_browser": True,
            "requires_residential": True,
            "delay": 5.0,
            "batch_size": 3,
        },
        SiteType.NEWS: {
            "domains": [
                "cnn", "bbc", "reuters", "apnews", "nytimes", "washingtonpost",
                "theguardian", "bloomberg", "forbes", "techcrunch",
                "theverge", "arstechnica", "wired",
            ],
            "protection": ProtectionLevel.MODERATE,
            "requires_browser": False,
            "requires_residential": False,
            "delay": 1.0,
            "batch_size": 20,
        },
        SiteType.TECH: {
            "domains": [
                "github", "gitlab", "stackoverflow", "stackexchange",
                "dev.to", "medium", "hackernews", "producthunt",
            ],
            "protection": ProtectionLevel.BASIC,
            "requires_browser": False,
            "requires_residential": False,
            "delay": 0.5,
            "batch_size": 30,
        },
        SiteType.GOVERNMENT: {
            "domains": [
                ".gov", ".gov.in", ".gov.uk", ".gov.au",
            ],
            "protection": ProtectionLevel.BASIC,
            "requires_browser": False,
            "requires_residential": False,
            "delay": 2.0,
            "batch_size": 10,
        },
        SiteType.EDUCATION: {
            "domains": [
                "edu", "ac.uk", "edu.au", "ac.in",
                "coursera", "edx", "udemy", "khanacademy",
            ],
            "protection": ProtectionLevel.BASIC,
            "requires_browser": False,
            "requires_residential": False,
            "delay": 1.0,
            "batch_size": 20,
        },
        SiteType.UNKNOWN: {
            "domains": [],
            "protection": ProtectionLevel.BASIC,
            "requires_browser": False,
            "requires_residential": False,
            "delay": 1.0,
            "batch_size": 10,
        },
    }
    
    # Known protected sites (need special handling)
    PROTECTED_SITES = {
        "cloudflare": ["challenge", "just a moment", "checking your browser"],
        "akamai": ["access denied", "request denied"],
        "datadome": ["captcha", "access denied"],
        "perimeterx": ["human security", "please verify"],
    }
    
    def analyze(self, url: str) -> SiteAnalysis:
        """Analyze a URL and determine the best approach.
        
        Parameters
        ----------
        url : str
            URL to analyze.
            
        Returns
        -------
        SiteAnalysis
            Analysis with recommendations.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Detect site type
        site_type = self._detect_site_type(domain)
        
        # Get pattern info
        pattern = self.SITE_PATTERNS.get(site_type, self.SITE_PATTERNS[SiteType.UNKNOWN])
        
        # Detect protection level
        protection = self._detect_protection_level(domain, path)
        
        # Determine requirements
        requires_browser = pattern["requires_browser"] or protection.value in ["high", "extreme"]
        requires_residential = pattern["requires_residential"] or protection.value in ["high", "extreme"]
        
        # Select engine
        engine = self._select_engine(requires_browser, protection)
        
        # Calculate delay
        delay = self._calculate_delay(pattern["delay"], protection)
        
        # Calculate batch size
        batch_size = self._calculate_batch_size(pattern["batch_size"], protection)
        
        # Generate notes
        notes = self._generate_notes(site_type, protection, requires_residential)
        
        return SiteAnalysis(
            url=url,
            domain=domain,
            site_type=site_type,
            protection_level=protection,
            requires_browser=requires_browser,
            requires_residential_proxy=requires_residential,
            recommended_engine=engine,
            recommended_delay=delay,
            recommended_batch_size=batch_size,
            notes=notes,
        )
    
    def _detect_site_type(self, domain: str) -> SiteType:
        """Detect the type of site from domain."""
        for site_type, config in self.SITE_PATTERNS.items():
            for pattern in config["domains"]:
                if pattern in domain:
                    return site_type
        
        # Check for government/education TLDs
        if any(tld in domain for tld in [".gov", ".edu", ".ac.uk", ".ac.in"]):
            if ".gov" in domain:
                return SiteType.GOVERNMENT
            elif ".edu" in domain or ".ac." in domain:
                return SiteType.EDUCATION
        
        return SiteType.UNKNOWN
    
    def _detect_protection_level(self, domain: str, path: str) -> ProtectionLevel:
        """Detect the protection level."""
        # Check known protected sites
        for vendor, keywords in self.PROTECTED_SITES.items():
            for keyword in keywords:
                if keyword in domain or keyword in path:
                    return ProtectionLevel.HIGH
        
        # Check domain complexity
        if "login" in path or "signin" in path or "auth" in path:
            return ProtectionLevel.HIGH
        
        # Check for API endpoints
        if "/api/" in path or "api." in domain:
            return ProtectionLevel.MODERATE
        
        return ProtectionLevel.BASIC
    
    def _select_engine(self, requires_browser: bool, protection: ProtectionLevel) -> str:
        """Select the best engine."""
        if not requires_browser:
            return "static"
        
        if protection == ProtectionLevel.EXTREME:
            return "camoufox"  # Firefox-based is harder to detect
        elif protection == ProtectionLevel.HIGH:
            return "playwright_stealth"
        else:
            return "playwright_stealth"
    
    def _calculate_delay(self, base_delay: float, protection: ProtectionLevel) -> float:
        """Calculate appropriate delay based on protection."""
        multiplier = {
            ProtectionLevel.NONE: 0.5,
            ProtectionLevel.BASIC: 1.0,
            ProtectionLevel.MODERATE: 1.5,
            ProtectionLevel.HIGH: 2.0,
            ProtectionLevel.EXTREME: 3.0,
        }
        return base_delay * multiplier.get(protection, 1.0)
    
    def _calculate_batch_size(self, base_size: int, protection: ProtectionLevel) -> int:
        """Calculate batch size based on protection."""
        divisor = {
            ProtectionLevel.NONE: 0.5,
            ProtectionLevel.BASIC: 1.0,
            ProtectionLevel.MODERATE: 0.7,
            ProtectionLevel.HIGH: 0.5,
            ProtectionLevel.EXTREME: 0.3,
        }
        return max(1, int(base_size * divisor.get(protection, 1.0)))
    
    def _generate_notes(
        self,
        site_type: SiteType,
        protection: ProtectionLevel,
        requires_residential: bool,
    ) -> List[str]:
        """Generate helpful notes."""
        notes = []
        
        if site_type == SiteType.ECOMMERCE:
            notes.append("E-commerce site detected - use residential proxy for best results")
            notes.append("Consider adding delays between product page requests")
        
        if site_type == SiteType.SOCIAL:
            notes.append("Social media site - requires login for most content")
            notes.append("Very aggressive bot detection - use with caution")
        
        if protection == ProtectionLevel.HIGH:
            notes.append("High protection detected - residential proxy recommended")
            notes.append("Use --force-browser flag")
        
        if protection == ProtectionLevel.EXTREME:
            notes.append("Extreme protection - residential proxy required")
            notes.append("May require CAPTCHA solving")
            notes.append("Consider using session persistence")
        
        if requires_residential:
            notes.append("Residential proxy recommended to avoid blocks")
        
        return notes


class SmartRateLimiter:
    """Intelligent rate limiting based on site analysis."""
    
    def __init__(self, analysis: SiteAnalysis):
        """Initialize with site analysis."""
        self.analysis = analysis
        self.request_count = 0
        self.last_request_time = 0
        self.consecutive_failures = 0
    
    def get_delay(self) -> float:
        """Get appropriate delay for next request."""
        import time
        
        base_delay = self.analysis.recommended_delay
        
        # Increase delay after failures
        if self.consecutive_failures > 0:
            base_delay *= (1 + self.consecutive_failures * 0.5)
        
        # Add randomness (real users vary their speed)
        import random
        variation = random.uniform(0.7, 1.3)
        
        # Occasional longer pause (real users get distracted)
        if random.random() < 0.1:
            base_delay *= random.uniform(2, 4)
        
        return base_delay * variation
    
    def should_wait(self) -> bool:
        """Check if we should wait before next request."""
        import time
        import random
        
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        required_delay = self.get_delay()
        
        return elapsed < required_delay
    
    def wait_if_needed(self) -> None:
        """Wait if needed before next request."""
        import time
        import random
        
        if self.should_wait():
            delay = self.get_delay() - (time.time() - self.last_request_time)
            if delay > 0:
                time.sleep(delay)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def report_success(self) -> None:
        """Report successful request."""
        self.consecutive_failures = 0
    
    def report_failure(self) -> None:
        """Report failed request."""
        self.consecutive_failures += 1

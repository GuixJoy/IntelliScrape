"""TLS fingerprint configuration for impersonation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Browser TLS profiles for curl_cffi impersonation
# Based on actual curl_cffi BrowserType enum
TLS_PROFILES = {
    # Chrome profiles
    "chrome146": "chrome146",
    "chrome145": "chrome145",
    "chrome142": "chrome142",
    "chrome136": "chrome136",
    "chrome133a": "chrome133a",
    "chrome131": "chrome131",
    "chrome124": "chrome124",
    "chrome123": "chrome123",
    "chrome120": "chrome120",
    "chrome119": "chrome119",
    "chrome116": "chrome116",
    "chrome110": "chrome110",
    "chrome107": "chrome107",
    "chrome104": "chrome104",
    "chrome101": "chrome101",
    "chrome100": "chrome100",
    "chrome99": "chrome99",
    "chrome99_android": "chrome99_android",
    "chrome131_android": "chrome131_android",
    # Safari profiles
    "safari2601": "safari2601",
    "safari260": "safari260",
    "safari184": "safari184",
    "safari180": "safari180",
    "safari172_ios": "safari172_ios",
    "safari170": "safari170",
    "safari155": "safari155",
    "safari153": "safari153",
    "safari15_5": "safari15_5",
    "safari15_3": "safari15_3",
    # Edge profiles
    "edge101": "edge101",
    "edge99": "edge99",
    # Firefox profiles
    "firefox147": "firefox147",
    "firefox144": "firefox144",
    "firefox135": "firefox135",
    "firefox133": "firefox133",
    # Tor
    "tor145": "tor145",
}

# Browser family mapping
BROWSER_FAMILIES = {
    "chrome": ["chrome146", "chrome145", "chrome142", "chrome136", "chrome133a", "chrome131", "chrome124", "chrome123", "chrome120", "chrome119", "chrome116", "chrome110", "chrome107", "chrome104", "chrome101", "chrome100", "chrome99"],
    "safari": ["safari2601", "safari260", "safari184", "safari180", "safari172_ios", "safari170", "safari155", "safari153"],
    "edge": ["edge101", "edge99"],
    "firefox": ["firefox147", "firefox144", "firefox135", "firefox133"],
}


@dataclass
class TLSConfig:
    """TLS configuration for impersonation.

    Parameters
    ----------
    impersonate : str
        Browser profile to impersonate (e.g., "chrome131", "safari15_5").
    randomize : bool
        If True, randomly select a profile from the same browser family.
    """

    impersonate: str = "chrome131"
    randomize: bool = False

    def get_profile(self, browser_family: Optional[str] = None) -> str:
        """Get the TLS profile to use.

        Parameters
        ----------
        browser_family : str, optional
            If provided, randomize within this family ("chrome", "safari", "edge", "firefox").
        """
        if self.randomize:
            if browser_family and browser_family in BROWSER_FAMILIES:
                profiles = BROWSER_FAMILIES[browser_family]
                import random
                return random.choice(profiles)
            import random
            return random.choice(list(TLS_PROFILES.values()))

        return TLS_PROFILES.get(self.impersonate, self.impersonate)

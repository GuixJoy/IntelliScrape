"""TLS fingerprint configuration for impersonation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Browser TLS profiles for curl_cffi impersonation
TLS_PROFILES = {
    # Chrome profiles
    "chrome131": "chrome131",
    "chrome130": "chrome130",
    "chrome124": "chrome124",
    "chrome120": "chrome120",
    "chrome110": "chrome110",
    "chrome107": "chrome107",
    "chrome104": "chrome104",
    "chrome101": "chrome101",
    "chrome100": "chrome100",
    "chrome99": "chrome99",
    "chrome96": "chrome96",
    "chrome92": "chrome92",
    "chrome91": "chrome91",
    "chrome90": "chrome90",
    "chrome87": "chrome87",
    "chrome72": "chrome72",
    # Safari profiles
    "safari15_5": "safari15_5",
    "safari15_3": "safari15_3",
    "safari15_0": "safari15_0",
    "safari14_1": "safari14_1",
    "safari14_0": "safari14_0",
    "safari13_1": "safari13_1",
    "safari13_0": "safari13_0",
    "safari12_1": "safari12_1",
    # Edge profiles
    "edge101": "edge101",
    "edge99": "edge99",
    # Firefox profiles (new)
    "firefox131": "firefox131",
    "firefox130": "firefox130",
    "firefox128": "firefox128",
    "firefox120": "firefox120",
    "firefox115": "firefox115",
    "firefox109": "firefox109",
    "firefox102": "firefox102",
    "firefox91": "firefox91",
}

# Browser family mapping
BROWSER_FAMILIES = {
    "chrome": ["chrome131", "chrome130", "chrome124", "chrome120", "chrome110", "chrome107", "chrome104", "chrome101", "chrome100", "chrome99", "chrome96", "chrome92", "chrome91", "chrome90", "chrome87", "chrome72"],
    "safari": ["safari15_5", "safari15_3", "safari15_0", "safari14_1", "safari14_0", "safari13_1", "safari13_0", "safari12_1"],
    "edge": ["edge101", "edge99"],
    "firefox": ["firefox131", "firefox130", "firefox128", "firefox120", "firefox115", "firefox109", "firefox102", "firefox91"],
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

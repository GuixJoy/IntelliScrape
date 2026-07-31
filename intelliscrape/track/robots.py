"""robots.txt parser and compliance checker.

Ported from HTTrack's ``robots_wizard`` (htsrobots.c).

Parses robots.txt files per RFC 9309 and decides whether a URL is allowed
for a given user-agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class RobotsRule:
    """Parsed rule for one user-agent group."""

    agent: str  # "*" for the global group
    disallow: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)


@dataclass
class RobotsData:
    """Complete parsed robots.txt for one host."""

    host: str
    rules: list[RobotsRule] = field(default_factory=list)
    fetched: bool = False
    status_code: int | None = None  # None = not fetched


class RobotsParser:
    """Per-host robots.txt parser and lookup.

    The parser fetches and caches ``/robots.txt`` for each host encountered
    during a mirror, then answers ``is_allowed(url, user_agent)`` queries.
    """

    def __init__(self) -> None:
        self._hosts: dict[str, RobotsData] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        """Return True if *url* is allowed for *user_agent*.

        If the robots.txt for the host hasn't been fetched yet, returns
        True (optimistic default).
        """
        host = urlparse(url).hostname
        if not host:
            return True

        data = self._hosts.get(host)
        if data is None or not data.fetched:
            return True  # not fetched yet → assume allowed

        return self._check(url, data, user_agent)

    def parse(self, host: str, body: str, status_code: int = 200) -> None:
        """Parse a robots.txt body and store rules for *host*."""
        data = RobotsData(host=host, fetched=True, status_code=status_code)
        data.rules = self._parse_body(body)
        self._hosts[host] = data

    def mark_unfetched(self, host: str, status_code: int | None = None) -> None:
        """Record that robots.txt for *host* couldn't be fetched."""
        self._hosts[host] = RobotsData(
            host=host, fetched=True, status_code=status_code
        )

    def needs_fetch(self, host: str) -> bool:
        """Return True if we haven't yet tried to fetch robots.txt for *host*."""
        return host not in self._hosts

    def get_sitemaps(self, host: str) -> list[str]:
        """Return any Sitemap: URLs found in robots.txt for *host*."""
        data = self._hosts.get(host)
        if data is None:
            return []
        sitemaps: list[str] = []
        for rule in data.rules:
            sitemaps.extend(rule.sitemaps)
        return sitemaps

    def get_crawl_delay(self, host: str, user_agent: str = "*") -> float | None:
        """Return the Crawl-delay for *user_agent* on *host*, or None."""
        data = self._hosts.get(host)
        if data is None:
            return None
        for rule in data.rules:
            if self._agent_matches(user_agent, rule.agent):
                if rule.crawl_delay is not None:
                    return rule.crawl_delay
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check(self, url: str, data: RobotsData, user_agent: str) -> bool:
        """Apply robots.txt rules to decide if *url* is allowed."""
        parsed = urlparse(url)
        path = parsed.path or "/"

        best_action: str | None = None
        best_len = -1

        for rule in data.rules:
            if not self._agent_matches(user_agent, rule.agent):
                continue

            for pattern in rule.disallow:
                if self._path_matches(path, pattern):
                    match_len = len(pattern)
                    if match_len > best_len:
                        best_action = "disallow"
                        best_len = match_len

            for pattern in rule.allow:
                if self._path_matches(path, pattern):
                    match_len = len(pattern)
                    if match_len > best_len:
                        best_action = "allow"
                        best_len = match_len

        # Default: allowed
        return best_action != "disallow"

    @staticmethod
    def _agent_matches(user_agent: str, pattern: str) -> bool:
        if pattern == "*":
            return True
        return user_agent.lower() == pattern.lower()

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        """Simple prefix/wildcard match (HTTrack uses basic string matching)."""
        if not pattern:
            return False
        # Exact match or prefix match
        if path == pattern or path.startswith(pattern):
            return True
        # Wildcard: pattern ends with $ → exact match only
        if pattern.endswith("$"):
            return path == pattern[:-1]
        return False

    def _parse_body(self, body: str) -> list[RobotsRule]:
        """Parse a robots.txt body into a list of rules."""
        rules: list[RobotsRule] = []
        current_agents: list[str] = []
        currentDisallow: list[str] = []
        currentAllow: list[str] = []
        currentDelay: float | None = None
        currentSitemaps: list[str] = []

        for line in body.splitlines():
            # Strip comments
            comment_pos = line.find("#")
            if comment_pos >= 0:
                line = line[:comment_pos]
            line = line.strip()
            if not line:
                continue

            # Split key: value
            colon = line.find(":")
            if colon < 0:
                continue
            key = line[:colon].strip().lower()
            value = line[colon + 1 :].strip()

            if key == "user-agent":
                # Flush previous group
                if current_agents:
                    rules.append(
                        RobotsRule(
                            agent=current_agents[0] if len(current_agents) == 1 else "*",
                            disallow=list(currentDisallow),
                            allow=list(currentAllow),
                            crawl_delay=currentDelay,
                            sitemaps=list(currentSitemaps),
                        )
                    )
                    currentDisallow.clear()
                    currentAllow.clear()
                    currentDelay = None
                    currentSitemaps.clear()
                currentAgents = [value]

            elif key == "disallow":
                if value:
                    currentDisallow.append(value)

            elif key == "allow":
                if value:
                    currentAllow.append(value)

            elif key == "crawl-delay":
                try:
                    currentDelay = float(value)
                except ValueError:
                    pass

            elif key == "sitemap":
                if value:
                    currentSitemaps.append(value)

        # Flush last group
        if current_agents:
            rules.append(
                RobotsRule(
                    agent=current_agents[0] if len(current_agents) == 1 else "*",
                    disallow=list(currentDisallow),
                    allow=list(currentAllow),
                    crawl_delay=currentDelay,
                    sitemaps=list(currentSitemaps),
                )
            )

        return rules

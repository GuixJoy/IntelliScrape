"""API endpoint detector — scans HTML/JS/headers for API patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urljoin

from .signatures import (
    REST_PATTERNS,
    GRAPHQL_PATTERNS,
    WEBSOCKET_PATTERNS,
    DOC_PATHS,
    DOC_SIGNATURES,
    THIRD_PARTY_DOMAINS,
    SDK_SIGNATURES,
    KEY_PATTERNS,
    GENERIC_KEY_PATTERNS,
    NOISE_STRINGS,
    NOISE_PATH_PATTERNS,
)


@dataclass
class ApiEndpoint:
    """A single detected API endpoint."""

    url: str
    method: str
    category: str  # rest, graphql, websocket, documentation, third_party
    source: str  # html, js, header, meta, url
    confidence: float
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "method": self.method,
            "category": self.category,
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class ApiKeyExposure:
    """A detected API key or credential."""

    provider: str
    key_type: str
    location: str
    severity: str
    evidence: str  # redacted

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "key_type": self.key_type,
            "location": self.location,
            "severity": self.severity,
            "evidence": self.evidence,
        }


@dataclass
class ApiReport:
    """Full API detection report for a URL."""

    url: str
    endpoints: List[ApiEndpoint] = field(default_factory=list)
    key_exposures: List[ApiKeyExposure] = field(default_factory=list)
    third_party_apis: List[str] = field(default_factory=list)
    documentation: List[str] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for ep in self.endpoints:
            cats[ep.category] = cats.get(ep.category, 0) + 1
        cats["key_exposures"] = len(self.key_exposures)
        cats["third_party"] = len(self.third_party_apis)
        cats["documentation"] = len(self.documentation)
        return cats

    @property
    def total(self) -> int:
        return (
            len(self.endpoints)
            + len(self.key_exposures)
            + len(self.third_party_apis)
            + len(self.documentation)
        )

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "endpoints": [e.to_dict() for e in self.endpoints],
            "key_exposures": [k.to_dict() for k in self.key_exposures],
            "third_party_apis": self.third_party_apis,
            "documentation": self.documentation,
            "summary": self.summary,
            "total": self.total,
        }


# ── Source weight scoring ─────────────────────────────────────────────────────

_SOURCE_WEIGHTS: Dict[str, float] = {
    "js": 0.35,
    "html": 0.30,
    "header": 0.20,
    "meta": 0.10,
    "url": 0.05,
}

_MIN_CONFIDENCE = 0.3
_MAX_EVIDENCE = 10


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * __import__("math").log2(count / length) for count in freq.values())


def _is_noise_path(path: str) -> bool:
    """Check if a path is a noise/static resource."""
    if path in NOISE_STRINGS or len(path) < 3:
        return True
    for pattern in NOISE_PATH_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            return True
    return False


def _redact_key(match: str) -> str:
    """Redact an API key, showing only first 6 and last 4 chars."""
    if len(match) <= 12:
        return match[:3] + "..." + match[-2:]
    return match[:6] + "..." + match[-4:]


def _normalize_url(url: str, base_url: str = "") -> str:
    """Normalize a detected URL/path."""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/") and base_url:
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    return url


class ApiDetector:
    """Stateless API endpoint detector — all methods are classmethods."""

    @classmethod
    def extract(
        cls,
        html: str = "",
        headers: Optional[Dict[str, str]] = None,
        url: str = "",
    ) -> ApiReport:
        """Detect API endpoints, third-party services, and key exposures."""
        report = ApiReport(url=url)
        headers = headers or {}

        # Extract text content from HTML for JS analysis
        js_content = cls._extract_js_content(html)
        full_content = html  # keep original for HTML-specific patterns

        # Track seen endpoints for dedup
        seen_endpoints: Dict[str, ApiEndpoint] = {}
        seen_keys: set[str] = set()

        # 1. REST API patterns
        cls._scan_patterns(
            REST_PATTERNS, js_content, full_content, headers, url,
            category="rest", report=report, seen=seen_endpoints,
        )

        # 2. GraphQL patterns
        cls._scan_patterns(
            GRAPHQL_PATTERNS, js_content, full_content, headers, url,
            category="graphql", report=report, seen=seen_endpoints,
        )

        # 3. WebSocket patterns
        cls._scan_patterns(
            WEBSOCKET_PATTERNS, js_content, full_content, headers, url,
            category="websocket", report=report, seen=seen_endpoints,
        )

        # 4. API documentation
        cls._scan_doc_paths(html, url, report, seen_endpoints)
        cls._scan_patterns(
            DOC_SIGNATURES, js_content, full_content, headers, url,
            category="documentation", report=report, seen=seen_endpoints,
        )

        # 5. Third-party APIs
        cls._scan_third_party(js_content, full_content, headers, report)

        # 6. SDK signatures
        cls._scan_sdk_signatures(js_content, full_content, report)

        # 7. API key exposures
        cls._scan_keys(js_content, report, seen_keys)

        # Sort endpoints by confidence descending
        report.endpoints.sort(key=lambda e: e.confidence, reverse=True)

        return report

    @classmethod
    def _extract_js_content(cls, html: str) -> str:
        """Extract JavaScript content from HTML."""
        scripts: list[str] = []

        # Inline scripts
        for match in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE):
            content = match.group(1).strip()
            if content and len(content) > 10:
                scripts.append(content)

        # Script src URLs (just the tags, not fetched)
        for match in re.finditer(r'<script[^>]*src\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
            scripts.append(match.group(1))

        # Also include full HTML for attribute-based detection
        return "\n".join(scripts) + "\n" + html

    @classmethod
    def _scan_patterns(
        cls,
        patterns: Dict[str, Dict[str, list[str]]],
        js_content: str,
        html_content: str,
        headers: Dict[str, str],
        base_url: str,
        category: str,
        report: ApiReport,
        seen: Dict[str, ApiEndpoint],
    ) -> None:
        """Scan content against a pattern database."""
        content_map = {
            "js": js_content,
            "html": html_content,
            "header": " ".join(f"{k}: {v}" for k, v in headers.items()),
            "meta": html_content,
            "url": base_url,
        }

        for tech_name, signal_types in patterns.items():
            for source, regex_list in signal_types.items():
                content = content_map.get(source, "")
                if not content:
                    continue

                weight = _SOURCE_WEIGHTS.get(source, 0.1)

                for pattern in regex_list:
                    try:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                    except re.error:
                        continue

                    for m in matches:
                        # Extract the URL/path from the match
                        raw = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
                        raw = raw.strip()

                        if _is_noise_path(raw):
                            continue

                        endpoint_url = _normalize_url(raw, base_url)
                        dedup_key = f"{category}:{endpoint_url}"

                        if dedup_key in seen:
                            # Update confidence if higher
                            existing = seen[dedup_key]
                            if weight > _SOURCE_WEIGHTS.get(existing.source, 0):
                                existing.confidence = min(existing.confidence + 0.1, 1.0)
                                if f"{source}:{tech_name}" not in existing.evidence:
                                    existing.evidence.append(f"{source}:{tech_name}")
                            continue

                        ep = ApiEndpoint(
                            url=endpoint_url,
                            method=cls._guess_method(content, raw),
                            category=category,
                            source=source,
                            confidence=weight,
                            evidence=[f"{source}:{tech_name}"],
                        )
                        seen[dedup_key] = ep
                        report.endpoints.append(ep)

    @classmethod
    def _scan_doc_paths(
        cls,
        html: str,
        base_url: str,
        report: ApiReport,
        seen: Dict[str, ApiEndpoint],
    ) -> None:
        """Check for known API documentation paths."""
        for path in DOC_PATHS:
            # Check if the path appears in the HTML content
            if path.lower() in html.lower():
                endpoint_url = _normalize_url(path, base_url)
                dedup_key = f"documentation:{endpoint_url}"
                if dedup_key not in seen:
                    ep = ApiEndpoint(
                        url=endpoint_url,
                        method="GET",
                        category="documentation",
                        source="html",
                        confidence=0.7,
                        evidence=[f"html:doc_path:{path}"],
                    )
                    seen[dedup_key] = ep
                    report.endpoints.append(ep)
                if endpoint_url not in report.documentation:
                    report.documentation.append(endpoint_url)

    @classmethod
    def _scan_third_party(
        cls,
        js_content: str,
        html_content: str,
        headers: Dict[str, str],
        report: ApiReport,
    ) -> None:
        """Detect third-party API service usage."""
        combined = js_content + "\n" + html_content + "\n" + " ".join(f"{k}: {v}" for k, v in headers.items())
        found_services: set[str] = set()

        for domain_pattern, service_name in THIRD_PARTY_DOMAINS.items():
            if re.search(domain_pattern, combined, re.IGNORECASE):
                found_services.add(service_name)

        report.third_party_apis = sorted(found_services)

    @classmethod
    def _scan_sdk_signatures(
        cls,
        js_content: str,
        html_content: str,
        report: ApiReport,
    ) -> None:
        """Detect SDK/script imports from known providers."""
        combined = js_content + "\n" + html_content
        found_services: set[str] = set(report.third_party_apis)

        for pattern, service_name in SDK_SIGNATURES.items():
            if re.search(pattern, combined, re.IGNORECASE):
                found_services.add(service_name)

        report.third_party_apis = sorted(found_services)

    @classmethod
    def _scan_keys(
        cls,
        content: str,
        report: ApiReport,
        seen: set[str],
    ) -> None:
        """Detect exposed API keys and credentials."""
        # Provider-specific patterns
        for name, info in KEY_PATTERNS.items():
            try:
                for m in re.finditer(info["regex"], content):
                    match_text = m.group(0)
                    if match_text in seen:
                        continue
                    seen.add(match_text)

                    # Get context around the match
                    start = max(0, m.start() - 40)
                    end = min(len(content), m.end() + 40)
                    context = content[start:end].replace("\n", " ").strip()

                    report.key_exposures.append(
                        ApiKeyExposure(
                            provider=info["provider"],
                            key_type=info["key_type"],
                            location=context,
                            severity=info["severity"],
                            evidence=_redact_key(match_text),
                        )
                    )
            except re.error:
                continue

        # Generic patterns
        for name, info in GENERIC_KEY_PATTERNS.items():
            try:
                for m in re.finditer(info["regex"], content):
                    match_text = m.group(0)
                    if match_text in seen:
                        continue
                    seen.add(match_text)

                    start = max(0, m.start() - 40)
                    end = min(len(content), m.end() + 40)
                    context = content[start:end].replace("\n", " ").strip()

                    # For generic patterns, also check entropy
                    if info["key_type"] in ("api_key", "bearer_token", "jwt"):
                        value = m.group(1) if m.lastindex and m.lastindex >= 1 else match_text
                        if _shannon_entropy(value) < 3.5:
                            continue

                    report.key_exposures.append(
                        ApiKeyExposure(
                            provider="generic",
                            key_type=info["key_type"],
                            location=context,
                            severity=info["severity"],
                            evidence=_redact_key(match_text[:60]),
                        )
                    )
            except re.error:
                continue

    @classmethod
    def _guess_method(cls, content: str, path: str) -> str:
        """Try to guess HTTP method from surrounding context."""
        # Look for method near the path in content
        idx = content.find(path)
        if idx == -1:
            return "GET"

        context = content[max(0, idx - 100) : idx + len(path) + 100].upper()

        if any(m in context for m in ["POST", ".POST(", "method.*POST"]):
            return "POST"
        if any(m in context for m in ["PUT", ".PUT(", "method.*PUT"]):
            return "PUT"
        if any(m in context for m in ["DELETE", ".DELETE(", "method.*DELETE"]):
            return "DELETE"
        if any(m in context for m in ["PATCH", ".PATCH(", "method.*PATCH"]):
            return "PATCH"
        return "GET"

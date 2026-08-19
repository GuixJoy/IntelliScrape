"""SEO Analyzer — on-page, technical, and content analysis.

Extracts SEO signals from HTML and returns a scored report with
actionable suggestions. Provides detailed breakdowns of content,
links, images, headings, technical SEO, and page performance.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .signatures import (
    CANONICAL_REL,
    HREFLANG_REL,
    META_DESC_IDEAL_MAX,
    META_DESC_IDEAL_MIN,
    META_DESC_MAX_LENGTH,
    META_DESC_MIN_LENGTH,
    MIN_ALT_COVERAGE,
    MIN_CONTENT_WORDS,
    OG_REQUIRED_TAGS,
    SCHEMA_ORG_SEO_TYPES,
    TITLE_IDEAL_MAX,
    TITLE_IDEAL_MIN,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    TWITTER_REQUIRED_TAGS,
    VIEWPORT_CONTENT,
)

# Common English stop words to exclude from keyword analysis
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "are",
    "this", "that", "these", "those", "can", "will", "just", "not",
    "you", "your", "we", "our", "they", "their", "has", "have", "had",
    "do", "does", "did", "if", "so", "no", "yes", "all", "any", "each",
    "every", "more", "most", "other", "some", "such", "than", "too",
    "very", "also", "how", "what", "when", "where", "who", "which",
    "about", "up", "out", "into", "over", "after", "new", "use",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SEOIssue:
    """A single SEO issue found during analysis."""

    category: str  # title, meta, headings, images, links, technical, content, schema
    severity: str  # critical, warning, info
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class SEOCheck:
    """Result of a single SEO check."""

    name: str
    passed: bool
    score: float  # 0.0 - 1.0
    issues: List[SEOIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 2),
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class ContentAnalysis:
    """Detailed content metrics."""

    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    avg_sentence_length: float = 0.0  # avg words per sentence
    reading_time_minutes: float = 0.0  # estimated reading time
    flesch_kincaid_grade: float = 0.0  # readability grade (US school level)
    top_keywords: List[Tuple[str, int, float]] = field(default_factory=list)  # (word, count, density%)

    def to_dict(self) -> dict:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "avg_sentence_length": round(self.avg_sentence_length, 1),
            "reading_time_minutes": round(self.reading_time_minutes, 1),
            "flesch_kincaid_grade": round(self.flesch_kincaid_grade, 1),
            "top_keywords": [{"word": w, "count": c, "density": round(d, 2)} for w, c, d in self.top_keywords],
        }


@dataclass
class LinkAnalysis:
    """Detailed link metrics."""

    total: int = 0
    internal: int = 0
    external: int = 0
    nofollow: int = 0
    dofollow: int = 0
    sponsored: int = 0
    ugc: int = 0
    empty_anchors: int = 0
    short_anchors: int = 0
    external_domains: List[str] = field(default_factory=list)

    @property
    def nofollow_ratio(self) -> float:
        return self.nofollow / self.total if self.total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "internal": self.internal,
            "external": self.external,
            "nofollow": self.nofollow,
            "dofollow": self.dofollow,
            "sponsored": self.sponsored,
            "ugc": self.ugc,
            "empty_anchors": self.empty_anchors,
            "short_anchors": self.short_anchors,
            "nofollow_ratio": round(self.nofollow_ratio * 100, 1),
            "external_domains": self.external_domains,
        }


@dataclass
class HeadingAnalysis:
    """Detailed heading metrics."""

    counts: Dict[str, int] = field(default_factory=dict)  # {"h1": 1, "h2": 8, ...}
    hierarchy: List[Tuple[int, str]] = field(default_factory=list)  # [(1, "text"), (2, "text"), ...]
    skipped_levels: bool = False

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "hierarchy": [{"level": level, "text": text} for level, text in self.hierarchy],
            "skipped_levels": self.skipped_levels,
            "total": self.total,
        }


@dataclass
class ImageAnalysis:
    """Detailed image metrics."""

    total: int = 0
    with_alt: int = 0
    missing_alt: int = 0
    empty_alt: int = 0
    lazy_loaded: int = 0
    external_domains: List[str] = field(default_factory=list)

    @property
    def alt_coverage(self) -> float:
        return self.with_alt / self.total if self.total > 0 else 1.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "with_alt": self.with_alt,
            "missing_alt": self.missing_alt,
            "empty_alt": self.empty_alt,
            "lazy_loaded": self.lazy_loaded,
            "alt_coverage": round(self.alt_coverage * 100, 1),
            "external_domains": self.external_domains,
        }


@dataclass
class TechnicalAnalysis:
    """Detailed technical SEO metrics."""

    has_viewport: bool = False
    viewport_content: str = ""
    lang_attribute: str = ""
    has_lang: bool = False
    hreflang_tags: List[Dict[str, str]] = field(default_factory=list)
    has_x_default: bool = False
    robots_meta: str = ""
    is_noindex: bool = False
    is_https: bool = False
    has_canonical: bool = False
    canonical_url: str = ""

    def to_dict(self) -> dict:
        return {
            "has_viewport": self.has_viewport,
            "viewport_content": self.viewport_content,
            "lang_attribute": self.lang_attribute,
            "has_lang": self.has_lang,
            "hreflang_tags": self.hreflang_tags,
            "has_x_default": self.has_x_default,
            "robots_meta": self.robots_meta,
            "is_noindex": self.is_noindex,
            "is_https": self.is_https,
            "has_canonical": self.has_canonical,
            "canonical_url": self.canonical_url,
        }


@dataclass
class PerformanceAnalysis:
    """Page performance indicators (from HTML analysis)."""

    script_count: int = 0
    external_scripts: int = 0
    inline_scripts: int = 0
    stylesheet_count: int = 0
    external_stylesheets: int = 0
    inline_css_size: int = 0  # approximate bytes
    external_domains: List[str] = field(default_factory=list)
    total_dom_elements: int = 0

    def to_dict(self) -> dict:
        return {
            "script_count": self.script_count,
            "external_scripts": self.external_scripts,
            "inline_scripts": self.inline_scripts,
            "stylesheet_count": self.stylesheet_count,
            "external_stylesheets": self.external_stylesheets,
            "inline_css_bytes": self.inline_css_size,
            "external_domains": self.external_domains,
            "total_dom_elements": self.total_dom_elements,
        }


@dataclass
class SEOReport:
    """Full SEO analysis report for a URL."""

    url: str
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    overall_score: float = 0.0
    checks: List[SEOCheck] = field(default_factory=list)
    issues: List[SEOIssue] = field(default_factory=list)
    schema_types: List[str] = field(default_factory=list)
    og_tags: Dict[str, str] = field(default_factory=dict)
    twitter_tags: Dict[str, str] = field(default_factory=dict)

    # Detailed analysis sections
    content: ContentAnalysis = field(default_factory=ContentAnalysis)
    links: LinkAnalysis = field(default_factory=LinkAnalysis)
    headings: HeadingAnalysis = field(default_factory=HeadingAnalysis)
    images: ImageAnalysis = field(default_factory=ImageAnalysis)
    technical: TechnicalAnalysis = field(default_factory=TechnicalAnalysis)
    performance: PerformanceAnalysis = field(default_factory=PerformanceAnalysis)

    @property
    def critical_issues(self) -> List[SEOIssue]:
        return [i for i in self.issues if i.severity == "critical"]

    @property
    def warnings(self) -> List[SEOIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def info_issues(self) -> List[SEOIssue]:
        return [i for i in self.issues if i.severity == "info"]

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "meta_description": self.meta_description,
            "canonical": self.canonical,
            "overall_score": round(self.overall_score, 1),
            "checks": [c.to_dict() for c in self.checks],
            "issues": [i.to_dict() for i in self.issues],
            "schema_types": self.schema_types,
            "og_tags": self.og_tags,
            "twitter_tags": self.twitter_tags,
            "content": self.content.to_dict(),
            "links": self.links.to_dict(),
            "headings": self.headings.to_dict(),
            "images": self.images.to_dict(),
            "technical": self.technical.to_dict(),
            "performance": self.performance.to_dict(),
        }


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class SEOAnalyzer:
    """Analyze a webpage for SEO quality.

    Usage
    -----
    >>> from intelliscrape.seo import SEOAnalyzer
    >>> report = SEOAnalyzer.analyze_html(html, "https://example.com")
    >>> print(report.overall_score)
    78.5
    """

    @staticmethod
    def analyze_html(html: str, url: str) -> SEOReport:
        """Analyze raw HTML and return an SEO report.

        Parameters
        ----------
        html : str
            Raw HTML content.
        url : str
            The page URL (used for link resolution).

        Returns
        -------
        SEOReport
            Scored report with issues and suggestions.
        """
        report = SEOReport(url=url)
        soup = BeautifulSoup(html, "html.parser")

        # Run detailed analysis sections (these populate report fields)
        SEOAnalyzer._analyze_content(soup, report)
        SEOAnalyzer._analyze_links(soup, url, report)
        SEOAnalyzer._analyze_headings(soup, report)
        SEOAnalyzer._analyze_images(soup, report)
        SEOAnalyzer._analyze_technical(soup, url, report)
        SEOAnalyzer._analyze_performance(soup, report)

        # Run scoring checks
        checks = []
        checks.append(SEOAnalyzer._check_title(soup, report))
        checks.append(SEOAnalyzer._check_meta_description(soup, report))
        checks.append(SEOAnalyzer._check_headings(soup, report))
        checks.append(SEOAnalyzer._check_images(soup, report))
        checks.append(SEOAnalyzer._check_links(soup, url, report))
        checks.append(SEOAnalyzer._check_canonical(soup, url, report))
        checks.append(SEOAnalyzer._check_open_graph(soup, report))
        checks.append(SEOAnalyzer._check_twitter_cards(soup, report))
        checks.append(SEOAnalyzer._check_schema(soup, report))
        checks.append(SEOAnalyzer._check_technical(soup, url, report))
        checks.append(SEOAnalyzer._check_content(soup, report))

        report.checks = checks

        # Collect all issues
        for check in checks:
            report.issues.extend(check.issues)

        # Calculate overall score (weighted average)
        weights = {
            "title": 12,
            "meta_description": 10,
            "headings": 10,
            "images": 8,
            "links": 10,
            "canonical": 8,
            "open_graph": 7,
            "twitter_cards": 5,
            "schema": 8,
            "technical": 12,
            "content": 10,
        }

        total_weight = 0
        weighted_sum = 0
        for check in checks:
            w = weights.get(check.name, 5)
            weighted_sum += check.score * w
            total_weight += w

        report.overall_score = round((weighted_sum / total_weight) * 100, 1) if total_weight else 0

        return report

    # ------------------------------------------------------------------
    # Detailed analysis (populates report sub-objects)
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_content(soup: BeautifulSoup, report: SEOReport) -> None:
        """Extract detailed content metrics."""
        # Clone soup so we don't destroy the original
        import copy
        soup_copy = copy.copy(soup)
        for tag in soup_copy(["script", "style", "noscript"]):
            tag.decompose()

        body = soup_copy.find("body")
        if not body:
            return

        text = body.get_text(separator=" ", strip=True)
        words = text.split()
        ca = ContentAnalysis()
        ca.word_count = len(words)

        # Sentences
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 5]
        ca.sentence_count = len(sentences)

        # Paragraphs
        paragraphs = body.find_all("p")
        ca.paragraph_count = len(paragraphs)

        # Avg sentence length
        if ca.sentence_count > 0:
            total_words_in_sentences = sum(len(s.split()) for s in sentences)
            ca.avg_sentence_length = total_words_in_sentences / ca.sentence_count

        # Reading time (avg 200 wpm for adult)
        ca.reading_time_minutes = ca.word_count / 200.0 if ca.word_count > 0 else 0

        # Flesch-Kincaid Grade Level
        if ca.sentence_count > 0 and ca.word_count > 0:
            # Count syllables (simplified)
            total_syllables = sum(SEOAnalyzer._count_syllables(w) for w in words)
            ca.flesch_kincaid_grade = (
                0.39 * (ca.word_count / ca.sentence_count)
                + 11.8 * (total_syllables / ca.word_count)
                - 15.59
            )
            ca.flesch_kincaid_grade = max(0, ca.flesch_kincaid_grade)

        # Top keywords
        word_counts = Counter()
        for w in words:
            clean = re.sub(r"[^a-zA-Z]", "", w.lower())
            if clean and len(clean) > 2 and clean not in _STOP_WORDS:
                word_counts[clean] += 1

        if ca.word_count > 0:
            ca.top_keywords = [
                (word, count, (count / ca.word_count) * 100)
                for word, count in word_counts.most_common(15)
            ]

        report.content = ca

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count (simplified algorithm)."""
        word = word.lower()
        if len(word) <= 3:
            return 1
        vowels = "aeiouy"
        count = 0
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e"):
            count -= 1
        return max(1, count)

    @staticmethod
    def _analyze_links(soup: BeautifulSoup, url: str, report: SEOReport) -> None:
        """Extract detailed link metrics."""
        links = soup.find_all("a", href=True)
        parsed_base = urlparse(url)
        la = LinkAnalysis()
        domain_counts = Counter()

        for link in links:
            href = link.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            link_text = link.get_text(strip=True)

            if not link_text:
                la.empty_anchors += 1
            elif len(link_text) < 3:
                la.short_anchors += 1

            parsed_link = urlparse(href)
            if parsed_link.netloc and parsed_link.netloc != parsed_base.netloc:
                la.external += 1
                domain_counts[parsed_link.netloc] += 1
            else:
                la.internal += 1

            rel = link.get("rel", [])
            if "nofollow" in rel:
                la.nofollow += 1
            else:
                la.dofollow += 1
            if "sponsored" in rel:
                la.sponsored += 1
            if "ugc" in rel:
                la.ugc += 1

        la.total = la.internal + la.external
        la.external_domains = [d for d, _ in domain_counts.most_common(10)]

        report.links = la

    @staticmethod
    def _analyze_headings(soup: BeautifulSoup, report: SEOReport) -> None:
        """Extract detailed heading metrics."""
        ha = HeadingAnalysis()

        for level in range(1, 7):
            tag_name = f"h{level}"
            headings = soup.find_all(tag_name)
            if headings:
                ha.counts[tag_name] = len(headings)
                for h in headings:
                    text = h.get_text(strip=True)[:80]
                    ha.hierarchy.append((level, text))

        # Check for skipped levels
        prev_level = 0
        for level, _ in ha.hierarchy:
            if prev_level > 0 and level > prev_level + 1:
                ha.skipped_levels = True
                break
            prev_level = level

        report.headings = ha

    @staticmethod
    def _analyze_images(soup: BeautifulSoup, report: SEOReport) -> None:
        """Extract detailed image metrics."""
        images = soup.find_all("img")
        ia = ImageAnalysis()
        domain_counts = Counter()
        parsed_base = None  # will set if we need domain filtering

        ia.total = len(images)

        for img in images:
            alt = img.get("alt")
            if alt is None:
                ia.missing_alt += 1
            elif alt.strip() == "":
                ia.empty_alt += 1
            else:
                ia.with_alt += 1

            # Lazy loading
            loading = img.get("loading", "")
            if loading == "lazy":
                ia.lazy_loaded += 1
            # Also check data-src (common lazy load pattern)
            if img.get("data-src"):
                ia.lazy_loaded += 1

            # External image domains
            src = img.get("src", "") or img.get("data-src", "")
            if src:
                parsed = urlparse(src)
                if parsed.netloc:
                    domain_counts[parsed.netloc] += 1

        ia.external_domains = [d for d, _ in domain_counts.most_common(10)]

        report.images = ia

    @staticmethod
    def _analyze_technical(soup: BeautifulSoup, url: str, report: SEOReport) -> None:
        """Extract detailed technical SEO metrics."""
        ta = TechnicalAnalysis()

        # Viewport
        viewport = soup.find("meta", attrs={"name": "viewport"})
        ta.has_viewport = viewport is not None
        ta.viewport_content = viewport.get("content", "") if viewport else ""

        # Language
        html_tag = soup.find("html")
        if html_tag:
            lang = html_tag.get("lang", "")
            ta.has_lang = bool(lang)
            ta.lang_attribute = lang

        # Hreflang
        hreflang_tags = soup.find_all("link", rel=HREFLANG_REL)
        for tag in hreflang_tags:
            ta.hreflang_tags.append({
                "hreflang": tag.get("hreflang", ""),
                "href": tag.get("href", ""),
            })
        ta.has_x_default = any(t.get("hreflang") == "x-default" for t in ta.hreflang_tags)

        # Robots meta
        robots_meta = soup.find("meta", attrs={"name": "robots"})
        if robots_meta:
            ta.robots_meta = robots_meta.get("content", "")
            ta.is_noindex = "noindex" in ta.robots_meta.lower()

        # HTTPS
        ta.is_https = urlparse(url).scheme == "https"

        # Canonical
        canonical = soup.find("link", rel=CANONICAL_REL)
        ta.has_canonical = canonical is not None
        ta.canonical_url = canonical.get("href", "") if canonical else ""

        report.technical = ta

    @staticmethod
    def _analyze_performance(soup: BeautifulSoup, report: SEOReport) -> None:
        """Extract page performance indicators from HTML."""
        pa = PerformanceAnalysis()

        # Scripts
        scripts = soup.find_all("script")
        pa.script_count = len(scripts)
        for s in scripts:
            src = s.get("src", "")
            if src:
                pa.external_scripts += 1
            else:
                pa.inline_scripts += 1

        # Stylesheets
        stylesheets = soup.find_all("link", rel="stylesheet")
        pa.stylesheet_count = len(stylesheets)
        pa.external_stylesheets = len([s for s in stylesheets if s.get("href")])

        # Inline CSS size
        for style in soup.find_all("style"):
            pa.inline_css_size += len(style.string or "")

        # External domains loaded
        domain_counts = Counter()
        for tag in soup.find_all(["script", "link", "img", "iframe"]):
            for attr in ["src", "href"]:
                val = tag.get(attr, "")
                if val:
                    parsed = urlparse(val)
                    if parsed.netloc:
                        domain_counts[parsed.netloc] += 1

        pa.external_domains = [d for d, _ in domain_counts.most_common(15)]

        # DOM element count (approximate)
        pa.total_dom_elements = len(soup.find_all(True))

        report.performance = pa

    # ------------------------------------------------------------------
    # Scoring checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_title(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        title_tag = soup.find("title")
        issues = []

        if not title_tag or not title_tag.string:
            issues.append(SEOIssue(
                category="title",
                severity="critical",
                message="Missing <title> tag",
                suggestion="Add a descriptive title tag between 50-60 characters.",
            ))
            return SEOCheck(name="title", passed=False, score=0.0, issues=issues)

        title = title_tag.string.strip()
        report.title = title
        length = len(title)

        if length < TITLE_MIN_LENGTH:
            issues.append(SEOIssue(
                category="title",
                severity="warning",
                message=f"Title too short ({length} chars, minimum {TITLE_MIN_LENGTH})",
                suggestion="Expand your title to include target keywords naturally.",
            ))
        elif length > TITLE_MAX_LENGTH:
            issues.append(SEOIssue(
                category="title",
                severity="warning",
                message=f"Title too long ({length} chars, maximum {TITLE_MAX_LENGTH})",
                suggestion="Shorten your title to avoid truncation in search results.",
            ))

        words = title.lower().split()
        if len(words) != len(set(words)):
            dupes = [w for w in words if words.count(w) > 1]
            issues.append(SEOIssue(
                category="title",
                severity="info",
                message=f"Repeated words in title: {', '.join(set(dupes))}",
                suggestion="Avoid keyword stuffing in titles.",
            ))

        score = 1.0
        if TITLE_IDEAL_MIN <= length <= TITLE_IDEAL_MAX:
            score = 1.0
        elif length < TITLE_MIN_LENGTH or length > TITLE_MAX_LENGTH:
            score = 0.5
        else:
            score = 0.8

        if issues:
            score *= 0.8

        return SEOCheck(name="title", passed=len(issues) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_meta_description(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        meta = soup.find("meta", attrs={"name": "description"})
        issues = []

        if not meta or not meta.get("content"):
            issues.append(SEOIssue(
                category="meta",
                severity="critical",
                message="Missing meta description",
                suggestion="Add a compelling meta description between 120-155 characters.",
            ))
            return SEOCheck(name="meta_description", passed=False, score=0.0, issues=issues)

        desc = meta["content"].strip()
        report.meta_description = desc
        length = len(desc)

        if length < META_DESC_MIN_LENGTH:
            issues.append(SEOIssue(
                category="meta",
                severity="warning",
                message=f"Meta description too short ({length} chars, minimum {META_DESC_MIN_LENGTH})",
                suggestion="Expand your description to include target keywords and a call to action.",
            ))
        elif length > META_DESC_MAX_LENGTH:
            issues.append(SEOIssue(
                category="meta",
                severity="warning",
                message=f"Meta description too long ({length} chars, maximum {META_DESC_MAX_LENGTH})",
                suggestion="Shorten your description to avoid truncation in search results.",
            ))

        score = 1.0
        if META_DESC_IDEAL_MIN <= length <= META_DESC_IDEAL_MAX:
            score = 1.0
        elif length < META_DESC_MIN_LENGTH or length > META_DESC_MAX_LENGTH:
            score = 0.4
        else:
            score = 0.7

        if issues:
            score *= 0.8

        return SEOCheck(name="meta_description", passed=len(issues) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_headings(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        issues = []
        ha = report.headings

        h1_count = ha.counts.get("h1", 0)
        if h1_count == 0:
            issues.append(SEOIssue(
                category="headings",
                severity="critical",
                message="Missing <h1> tag",
                suggestion="Add exactly one <h1> tag with your primary keyword.",
            ))
        elif h1_count > 1:
            issues.append(SEOIssue(
                category="headings",
                severity="warning",
                message=f"Multiple <h1> tags found ({h1_count})",
                suggestion="Use only one <h1> per page for clear content hierarchy.",
            ))

        if ha.skipped_levels:
            issues.append(SEOIssue(
                category="headings",
                severity="warning",
                message="Heading levels are skipped (e.g., h1 → h3 without h2)",
                suggestion="Maintain proper heading hierarchy for accessibility and SEO.",
            ))

        score = 1.0
        if h1_count == 0:
            score = 0.0
        elif h1_count > 1:
            score = 0.7
        if ha.total < 2:
            score = min(score, 0.5)

        return SEOCheck(name="headings", passed=len(issues) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_images(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        ia = report.images
        issues = []

        if ia.total == 0:
            return SEOCheck(name="images", passed=True, score=1.0, issues=[])

        if ia.missing_alt > 0:
            coverage = ia.with_alt / ia.total
            issues.append(SEOIssue(
                category="images",
                severity="warning",
                message=f"{ia.missing_alt} of {ia.total} images missing alt text ({(1-coverage)*100:.0f}%)",
                suggestion="Add descriptive alt text to all images for accessibility and image search.",
            ))

        score = ia.alt_coverage
        if ia.alt_coverage < 0.5:
            score = 0.3
        elif ia.alt_coverage < MIN_ALT_COVERAGE:
            score = 0.6

        return SEOCheck(name="images", passed=ia.alt_coverage >= MIN_ALT_COVERAGE, score=max(0, score), issues=issues)

    @staticmethod
    def _check_links(soup: BeautifulSoup, url: str, report: SEOReport) -> SEOCheck:
        la = report.links
        issues = []

        if la.empty_anchors > 0:
            issues.append(SEOIssue(
                category="links",
                severity="warning",
                message=f"{la.empty_anchors} links with no anchor text",
                suggestion="Add descriptive anchor text to help search engines understand link destinations.",
            ))

        if la.total > 0 and la.nofollow_ratio > 0.5 and la.total > 10:
            issues.append(SEOIssue(
                category="links",
                severity="info",
                message=f"High nofollow ratio: {la.nofollow_ratio*100:.0f}% ({la.nofollow}/{la.total})",
                suggestion="Review nofollow links — excessive nofollow may limit link equity flow.",
            ))

        if la.internal == 0:
            issues.append(SEOIssue(
                category="links",
                severity="warning",
                message="No internal links found",
                suggestion="Add internal links to help search engines discover and rank your content.",
            ))

        score = 1.0
        if la.internal == 0:
            score = 0.3
        if la.empty_anchors > la.total * 0.2:
            score = min(score, 0.5)

        return SEOCheck(name="links", passed=len(issues) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_canonical(soup: BeautifulSoup, url: str, report: SEOReport) -> SEOCheck:
        ta = report.technical
        issues = []

        if not ta.has_canonical:
            issues.append(SEOIssue(
                category="technical",
                severity="warning",
                message="Missing canonical tag",
                suggestion="Add a canonical tag to prevent duplicate content issues.",
            ))
            return SEOCheck(name="canonical", passed=False, score=0.4, issues=issues)

        parsed_canonical = urlparse(ta.canonical_url)
        parsed_page = urlparse(url)

        if parsed_canonical.netloc and parsed_canonical.netloc != parsed_page.netloc:
            issues.append(SEOIssue(
                category="technical",
                severity="info",
                message=f"Canonical points to different domain: {parsed_canonical.netloc}",
                suggestion="Ensure cross-domain canonical is intentional.",
            ))

        return SEOCheck(name="canonical", passed=True, score=1.0, issues=issues)

    @staticmethod
    def _check_open_graph(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        issues = []
        og_tags = {}

        for tag in soup.find_all("meta", property=True):
            prop = tag.get("property", "")
            if prop.startswith("og:"):
                og_tags[prop] = tag.get("content", "")

        report.og_tags = og_tags

        missing = OG_REQUIRED_TAGS - set(og_tags.keys())
        if missing:
            issues.append(SEOIssue(
                category="open_graph",
                severity="warning",
                message=f"Missing Open Graph tags: {', '.join(sorted(missing))}",
                suggestion="Add all required OG tags for optimal social media sharing.",
            ))

        if not og_tags:
            issues.append(SEOIssue(
                category="open_graph",
                severity="info",
                message="No Open Graph tags found",
                suggestion="Add og:title, og:description, og:image, and og:url for social sharing.",
            ))

        score = 1.0 - (len(missing) / len(OG_REQUIRED_TAGS)) if OG_REQUIRED_TAGS else 1.0
        if not og_tags:
            score = 0.0

        return SEOCheck(name="open_graph", passed=len(missing) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_twitter_cards(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        issues = []
        twitter_tags = {}

        for tag in soup.find_all("meta", attrs={"name": True}):
            name = tag.get("name", "")
            if name.startswith("twitter:"):
                twitter_tags[name] = tag.get("content", "")

        report.twitter_tags = twitter_tags

        missing = TWITTER_REQUIRED_TAGS - set(twitter_tags.keys())
        if missing:
            issues.append(SEOIssue(
                category="twitter_cards",
                severity="info",
                message=f"Missing Twitter Card tags: {', '.join(sorted(missing))}",
                suggestion="Add Twitter Card tags for better Twitter/X sharing.",
            ))

        if not twitter_tags:
            issues.append(SEOIssue(
                category="twitter_cards",
                severity="info",
                message="No Twitter Card tags found",
                suggestion="Add twitter:card, twitter:title, and twitter:description.",
            ))

        score = 1.0 - (len(missing) / len(TWITTER_REQUIRED_TAGS)) if TWITTER_REQUIRED_TAGS else 1.0
        if not twitter_tags:
            score = 0.3

        return SEOCheck(name="twitter_cards", passed=len(missing) == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_schema(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        issues = []
        schema_types = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    t = data.get("@type", "")
                    if t:
                        schema_types.append(t)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            t = item.get("@type", "")
                            if t:
                                schema_types.append(t)
            except (json.JSONDecodeError, TypeError):
                pass

        report.schema_types = schema_types

        if not schema_types:
            issues.append(SEOIssue(
                category="schema",
                severity="info",
                message="No structured data (JSON-LD) found",
                suggestion="Add Schema.org structured data for rich snippets in search results.",
            ))

        seo_relevant = [t for t in schema_types if t in SCHEMA_ORG_SEO_TYPES]
        if schema_types and not seo_relevant:
            issues.append(SEOIssue(
                category="schema",
                severity="info",
                message=f"Schema types found but none are SEO-optimized: {', '.join(schema_types)}",
                suggestion="Consider adding Organization, Article, or FAQPage schema for rich snippets.",
            ))

        score = 1.0
        if not schema_types:
            score = 0.3
        elif not seo_relevant:
            score = 0.6

        return SEOCheck(name="schema", passed=not issues, score=max(0, score), issues=issues)

    @staticmethod
    def _check_technical(soup: BeautifulSoup, url: str, report: SEOReport) -> SEOCheck:
        ta = report.technical
        issues = []

        if not ta.has_viewport or VIEWPORT_CONTENT not in ta.viewport_content:
            issues.append(SEOIssue(
                category="technical",
                severity="critical",
                message="Missing or incorrect viewport meta tag",
                suggestion="Add <meta name='viewport' content='width=device-width, initial-scale=1'> for mobile SEO.",
            ))

        if not ta.has_lang:
            issues.append(SEOIssue(
                category="technical",
                severity="warning",
                message="Missing lang attribute on <html> tag",
                suggestion="Add lang attribute (e.g., <html lang='en'>) for accessibility and SEO.",
            ))

        if ta.hreflang_tags and not ta.has_x_default:
            issues.append(SEOIssue(
                category="technical",
                severity="info",
                message="Hreflang tags present but no x-default",
                suggestion="Add hreflang='x-default' for the fallback language.",
            ))

        if ta.is_noindex:
            issues.append(SEOIssue(
                category="technical",
                severity="critical",
                message="Page is set to noindex — will not appear in search results",
                suggestion="Remove noindex unless you intentionally want to exclude this page.",
            ))

        og_url = soup.find("meta", property="og:url")
        canonical = soup.find("link", rel=CANONICAL_REL)
        if og_url and canonical:
            og = og_url.get("content", "")
            can = canonical.get("href", "")
            if og and can and urlparse(og).path != urlparse(can).path:
                issues.append(SEOIssue(
                    category="technical",
                    severity="warning",
                    message="og:url and canonical URL paths don't match",
                    suggestion="Ensure og:url and canonical point to the same URL.",
                ))

        score = 1.0
        critical = sum(1 for i in issues if i.severity == "critical")
        warnings = sum(1 for i in issues if i.severity == "warning")
        score -= critical * 0.3
        score -= warnings * 0.1

        return SEOCheck(name="technical", passed=critical == 0, score=max(0, score), issues=issues)

    @staticmethod
    def _check_content(soup: BeautifulSoup, report: SEOReport) -> SEOCheck:
        issues = []
        ca = report.content

        if ca.word_count == 0:
            issues.append(SEOIssue(
                category="content",
                severity="critical",
                message="No <body> tag found",
                suggestion="Ensure the page has proper HTML structure.",
            ))
            return SEOCheck(name="content", passed=False, score=0.0, issues=issues)

        if ca.word_count < MIN_CONTENT_WORDS:
            issues.append(SEOIssue(
                category="content",
                severity="warning",
                message=f"Thin content: only {ca.word_count} words (recommended: {MIN_CONTENT_WORDS}+)",
                suggestion="Add more comprehensive content to improve rankings for competitive keywords.",
            ))

        if ca.sentence_count > 10:
            unique = set(s.strip() for s in re.split(r"[.!?]+", ca.sentence_count and "x" or ""))
            # Use the actual sentences from text
            import copy
            soup_copy = copy.copy(soup)
            for tag in soup_copy(["script", "style", "noscript"]):
                tag.decompose()
            body = soup_copy.find("body")
            if body:
                text = body.get_text(separator=" ", strip=True)
                sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]
                if len(sentences) > 10:
                    unique_sentences = set(sentences)
                    dup_ratio = 1 - (len(unique_sentences) / len(sentences))
                    if dup_ratio > 0.15:
                        issues.append(SEOIssue(
                            category="content",
                            severity="warning",
                            message=f"High content repetition: {dup_ratio*100:.0f}% duplicate sentences",
                            suggestion="Reduce content duplication — unique content ranks better.",
                        ))

        if ca.word_count > 50 and report.title:
            title_words = [w.lower() for w in report.title.split() if len(w) > 3]
            content_lower = " ".join(w[0].lower() for w in ca.top_keywords[:50]) if ca.top_keywords else ""
            if not content_lower:
                import copy
                soup_copy = copy.copy(soup)
                for tag in soup_copy(["script", "style", "noscript"]):
                    tag.decompose()
                body = soup_copy.find("body")
                if body:
                    content_lower = body.get_text(" ", strip=True).lower()
            missing_keywords = [w for w in title_words if w not in content_lower]
            if missing_keywords and len(missing_keywords) < len(title_words):
                issues.append(SEOIssue(
                    category="content",
                    severity="info",
                    message=f"Title keywords not found in content: {', '.join(missing_keywords[:3])}",
                    suggestion="Include your primary keywords naturally in the body content.",
                ))

        score = 1.0
        if ca.word_count < MIN_CONTENT_WORDS:
            score = min(score, 0.4)
        elif ca.word_count < 500:
            score = min(score, 0.7)

        return SEOCheck(name="content", passed=len(issues) == 0, score=max(0, score), issues=issues)

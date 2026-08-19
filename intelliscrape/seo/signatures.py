"""SEO analysis signatures and scoring rules."""

from __future__ import annotations

# Title tag scoring
TITLE_MIN_LENGTH = 30
TITLE_MAX_LENGTH = 60
TITLE_IDEAL_MIN = 50
TITLE_IDEAL_MAX = 60

# Meta description scoring
META_DESC_MIN_LENGTH = 70
META_DESC_MAX_LENGTH = 160
META_DESC_IDEAL_MIN = 120
META_DESC_IDEAL_MAX = 155

# Heading hierarchy
MAX_H1_COUNT = 1
MIN_CONTENT_WORDS = 300
IDEAL_CONTENT_WORDS = 1500

# Image alt text
MIN_ALT_COVERAGE = 0.8  # 80% of images should have alt text

# Link thresholds
MAX_INTERNAL_LINKS = 200
MAX_EXTERNAL_LINKS = 100
MIN_ANCHOR_TEXT_LENGTH = 2
MAX_NOFOLLOW_RATIO = 0.5  # More than 50% nofollow is suspicious

# Readability
TARGET_FLESCH_KINCAID = 60  # 60-70 is "standard" readability
MIN_SENTENCE_LENGTH = 10
MAX_SENTENCE_LENGTH = 25

# Schema.org types that matter for SEO
SCHEMA_ORG_SEO_TYPES = {
    "Organization", "LocalBusiness", "Product", "Article",
    "BlogPosting", "NewsArticle", "WebPage", "BreadcrumbList",
    "FAQPage", "HowTo", "Event", "Recipe", "Review",
    "LocalBusiness", "MedicalWebPage", "JobPosting",
}

# Open Graph required tags for different content types
OG_REQUIRED_TAGS = {"og:title", "og:description", "og:image", "og:url", "og:type"}

# Twitter Card required tags
TWITTER_REQUIRED_TAGS = {"twitter:card", "twitter:title", "twitter:description"}

# Technical SEO checks
SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]
ROBOTS_TXT_PATH = "/robots.txt"
CANONICAL_REL = "canonical"
HREFLANG_REL = "alternate"
VIEWPORT_CONTENT = "width=device-width"

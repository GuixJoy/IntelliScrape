from intelliscrape.downloader import download_html
from intelliscrape.utils import (
    is_html_empty,
    looks_like_js_page,
    has_meaningful_text,
    html_needs_browser
)

html = download_html("https://en.wikipedia.org/wiki/Web_scraping")

print("Length:", len(html))
print()

print("Empty:", is_html_empty(html))
print("JS Page:", looks_like_js_page(html))
print("Meaningful:", has_meaningful_text(html))

print()
print("FINAL:", html_needs_browser(html))
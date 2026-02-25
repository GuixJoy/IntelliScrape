from intelliscrape.downloader import download_html
from intelliscrape.parser import build_dom
from intelliscrape.extractor import extract_text

html = download_html("https://example.com")

soup = build_dom(html)

text = extract_text(soup)

print(text)
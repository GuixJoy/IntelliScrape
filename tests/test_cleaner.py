from intelliscrape.downloader import download_html
from intelliscrape.parser import build_dom
from intelliscrape.extractor import extract_text
from intelliscrape.cleaner import clean_text

html = download_html("https://example.com")

soup = build_dom(html)

text = extract_text(soup)

clean = clean_text(text)

print(clean)
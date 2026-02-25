from intelliscrape.downloader import download_html
from intelliscrape.parser import build_dom

html = download_html("https://example.com")

soup = build_dom(html)

print(soup.title.text)
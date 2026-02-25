from intelliscrape import scrape

urls = [
    "https://example.com",
    "https://www.python.org",
    "https://docs.python.org/3/",
    "https://en.wikipedia.org/wiki/Web_scraping"
]

for url in urls:

    print("\n====================")
    print("URL:", url)

    try:
        text = scrape(url)

        print("SUCCESS")
        print("Length:", len(text))

        print("\nPreview:")
        print(text[:300])

    except Exception as e:

        print("FAILED")
        print(e)
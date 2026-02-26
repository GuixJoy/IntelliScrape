from intelliscrape import scrape

text = scrape("https://stagging.digiscale.in/")

print(len(text))
print(text)
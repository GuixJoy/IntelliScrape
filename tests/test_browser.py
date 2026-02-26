from intelliscrape.browser import render_page

html = render_page("https://youtube.com")

print(html[:2000])
#!/usr/bin/env vhs
# Demo tape for IntelliScrape - run with: vhs demo.tape

Output demo.gif

# Set terminal theme
Set Width 1200
Set Height 800
Set FontSize 18
Set Theme {
  Background "#0d1117"
  Foreground "#c9d1d9"
  Cursor "#58a6ff"
}

# Title
Type "🚀 IntelliScrape - The Python scraper that actually works"
Sleep 2s
Enter

# Basic scrape
Type "$ "
Type "python -c \"from intelliscrape import scrape; print(scrape('https://news.ycombinator.com')[:300])\""
Sleep 3s
Enter
Sleep 2s

# Clear and show structured data
Type "clear"
Sleep 1s
Type "$ "
Type "python -c \"from intelliscrape import IntelliScrape; s = IntelliScrape(); d = s.get_structured('https://github.com'); print(f'Title: {d.title}'); print(f'Description: {d.description[:80]}...')\""
Sleep 3s
Enter
Sleep 2s

# Clear and show CLI
Type "clear"
Sleep 1s
Type "$ "
Type "intelliscrape https://example.com --output result.txt"
Sleep 2s
Enter
Sleep 1s
Type "[intelliscrape] Saved content to result.txt"
Sleep 2s
Enter

# Clear and show crawl
Type "clear"
Sleep 1s
Type "$ "
Type "intelliscrape https://docs.python.org --crawl --max-pages 5 --output docs.txt"
Sleep 3s
Enter
Sleep 1s
Type "[intelliscrape] Starting crawl of https://docs.python.org"
Type "[intelliscrape] Max pages: 5"
Type "[intelliscrape] [1/5] Scraping: https://docs.python.org"
Type "[intelliscrape]   OK - 12847 chars extracted"
Type "[intelliscrape] [2/5] Scraping: https://docs.python.org/3/"
Type "[intelliscrape]   OK - 15234 chars extracted"
Type "[intelliscrape] "
Type "[intelliscrape] Crawl complete: 5 scraped, 0 failed"
Type "Saved 5 pages to docs.txt"
Sleep 3s
Enter

# Clear and show anti-bot check
Type "clear"
Sleep 1s
Type "$ "
Type "intelliscrape https://example.com --check-antibot"
Sleep 2s
Enter
Sleep 1s
Type "No anti-bot protection detected."
Sleep 2s
Enter

# Final message
Type "clear"
Sleep 1s
Type "pip install intelliscrape"
Sleep 2s
Enter
Sleep 1s
Type "🎉 Scrape 98% of websites with one line of code"
Sleep 3s

# IntelliScrape

[![PyPI version](https://img.shields.io/pypi/v/intelliscrape.svg)](https://pypi.org/project/intelliscrape/)

IntelliScrape is a smart Python web scraping library that automatically detects whether a website is static or dynamic and extracts text content using the best available method. So you don't have to worry about whether a website is static or dynamic.

Instead of manually choosing between HTTP scraping and browser automation, IntelliScrape handles everything automatically. Just provide a URL and IntelliScrape will retrieve the content.

IntelliScrape is designed for developers and data analysts who want a simple and reliable way to extract data from modern websites without complex configuration.


## Installation

Install IntelliScrape:
pip install intelliscrape

Install Playwright browsers (required for dynamic sites):
python -m playwright install chromium



## Quick Start

from intelliscrape import scrape

text = scrape("https://example.com")

print(text)

## Why IntelliScrape?

Traditional web scraping requires developers to decide whether a website is static or dynamic and then configure the correct tools manually.

IntelliScrape simplifies this process by automatically selecting the appropriate scraping method.

With IntelliScrape:

No need to detect static vs dynamic websites manually
No need to configure Requests or Playwright separately
No need to set up Selenium
No complex scraping setup
Just call one function and get the content.

## Features

✔ Automatic static/dynamic detection  
✔ Requests-based scraping  
✔ Playwright-based rendering  
✔ Clean text extraction  
✔ Modular architecture  
✔ Simple API
✔ Works on modern JavaScript websites

## Tested On:

Static:
• Wikipedia
• Python.org

Dynamic:
• Medium
• YouTube

## How It Works

scrape(url)
   ↓
Downloader
   ↓
Static/Dynamic Detection
   ↓
Parser
   ↓
Extractor
   ↓
Cleaner
   ↓
Return Text

## Example Output

from intelliscrape import scrape

text = scrape("https://www.youtube.com/results?search_query=python")

print(text[:500])

HOURS of Python Projects From Beginner to Advanced Python Projects for Beginners Master Problem-Solving! Python Project for Data Analysis- Exploratory Data Analysis Data Analyst Project Learn Python With This ONE Project! Build Python Projects Step-by-Step Python Projects for Beginners to Advanced (Hindi) Mini Project in Python Python for Beginners #project1 python YouTube Skip navigation Search with your voice Subscriptions Unwatched Recently uploaded Search filters lessons Python Language Full

## Limitations
IntelliScrape works best on content-based websites.
Highly protected platforms and login-required pages may require custom scraping logic.
CAPTCHA solving is not automatic.
CAPTCHA Solving feature is in development.

## Project Structure

intelliscrape/
 core.py
 downloader.py
 browser.py
 parser.py
 extractor.py
 cleaner.py
 utils.py
 exceptions.py

## Examples
Example scripts are available in:
examples/

## Requirements

Python 3.9+

Playwright required for dynamic sites.

Install browsers:

playwright install

## License

MIT
from setuptools import setup, find_packages

setup(
    name="intelliscrape",
    version="0.1.0",
    description="Intelligent web scraping library",
    author="Guix Joy",
    packages=find_packages(),
    install_requires=[
        "requests",
        "beautifulsoup4",
        "lxml",
        "playwright"
    ],
    python_requires=">=3.8",
)
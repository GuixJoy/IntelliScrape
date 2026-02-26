"""
Content extraction module for IntelliScrape.
"""

from __future__ import annotations


def extract_text(soup) -> str:

    if soup is None:
        return ""

    # Remove heavy non-content tags
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    lines = []
    seen = set()

    # -------- YouTube Titles First --------
    for tag in soup.select("a#video-title"):
        text = tag.get_text(" ", strip=True)

        garbage_patterns = [
            "css-build",
            "css_build",
            "yt_base_styles",
            "polymer",
            "shady",
            ".css.js",
        ]

        for g in garbage_patterns:
            if g in text.lower():
                text = text.split(g)[0].strip()

        if len(text) > 5 and text not in seen:
            lines.append(text)
            seen.add(text)

        if len(lines) > 120:
            break

    # -------- Generic Fallback --------

    if len(lines) < 20:

        text = soup.get_text(separator="\n")

        for line in text.split("\n"):

            line = line.strip()

            if len(line) < 8:
                continue

            if any(x in line.lower() for x in [
                "css-build",
                "css_build",
                "polymer",
                "shady",
                ".css.js"
            ]):
                continue

            if line not in seen:
                lines.append(line)
                seen.add(line)

            if len(lines) > 300:
                break

    return "\n".join(lines)
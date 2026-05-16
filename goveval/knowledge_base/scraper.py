"""
goveval/knowledge_base/scraper.py
Scrapes public URLs (HTML) with requests + BeautifulSoup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List
from urllib.parse import urljoin, urlparse

from goveval.config.loader import ScrapeSource


@dataclass
class RawPage:
    source_name: str
    url: str
    text: str           # cleaned visible text
    headings: list[str] # h1/h2/h3 hierarchy at extraction point


def scrape(source: ScrapeSource) -> List[RawPage]:
    """
    Crawl source.url up to source.depth link-levels deep.
    Uses requests + BS4. Returns one RawPage per page visited.
    """
    import requests
    from bs4 import BeautifulSoup

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(source.url, 0)]
    pages: List[RawPage] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-SG,en;q=0.9",
    }

    while queue:
        url, depth = queue.pop(0)
        url = url.split("#")[0]  # strip fragments
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=20, headers=headers)
            resp.raise_for_status()
            if "text/html" not in resp.headers.get("Content-Type", ""):
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["nav", "footer", "aside", "script", "style",
                              "header", "form", "noscript", "iframe"]):
                tag.decompose()

            headings = [h.get_text(strip=True)
                        for h in soup.find_all(["h1", "h2", "h3"])[:15]]
            lines = [line.strip()
                     for line in soup.get_text(separator="\n").splitlines()
                     if line.strip()]
            text = "\n".join(lines)

            if len(text) > 200:
                pages.append(RawPage(
                    source_name=source.name,
                    url=url,
                    text=text,
                    headings=headings,
                ))

            if depth < source.depth:
                base_netloc = urlparse(source.url).netloc
                for a in soup.find_all("a", href=True):
                    href = urljoin(url, a["href"]).split("#")[0]
                    parsed = urlparse(href)
                    if (parsed.scheme in ("http", "https")
                            and parsed.netloc == base_netloc
                            and href not in visited):
                        queue.append((href, depth + 1))

            time.sleep(0.3)

        except Exception:
            pass

    return pages


def scrape_all(sources: List[ScrapeSource]) -> List[RawPage]:
    """Run scrape() on every source and flatten results."""
    pages = []
    for src in sources:
        pages.extend(scrape(src))
    return pages

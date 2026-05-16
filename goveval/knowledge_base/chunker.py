"""
goveval/knowledge_base/chunker.py
Splits RawPages into fixed-size overlapping chunks with metadata tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from goveval.knowledge_base.scraper import RawPage


@dataclass
class Chunk:
    chunk_id: str           
    source_name: str
    source_url: str
    section_heading: str
    text: str              
    char_count: int
    scraped_date: str       
    token_estimate: int     


def chunk_pages(
    pages: List[RawPage],
    source_name: str,
    source_url: str,
    chunk_size: int = 512,      
    overlap: int = 50,          
) -> List[Chunk]:
    """
    Split each page's text into overlapping chunks using paragraph boundaries.
    Token estimate: 1 token ≈ 4 characters.
    """
    today = date.today().isoformat()
    char_limit = chunk_size * 4
    overlap_chars = overlap * 4
    chunks: List[Chunk] = []

    for page_idx, page in enumerate(pages):
        url = getattr(page, "url", source_url) or source_url
        heading = page.headings[0] if page.headings else ""

        # Split on blank lines; fall back to the whole text as one block
        paragraphs = [p.strip() for p in page.text.split("\n\n") if len(p.strip()) > 30]
        if not paragraphs:
            paragraphs = [page.text.strip()] if page.text.strip() else []

        current = ""
        chunk_idx = 0

        for para in paragraphs:
            if len(current) + len(para) + 2 > char_limit and current:
                _emit(chunks, current, source_name, url, heading,
                      today, page_idx, chunk_idx)
                chunk_idx += 1
                # Carry over last overlap_chars of the previous chunk
                tail = current[-overlap_chars:].strip()
                current = (tail + "\n\n" + para).strip()
            else:
                current = (current + "\n\n" + para).strip() if current else para

        if current.strip():
            _emit(chunks, current, source_name, url, heading,
                  today, page_idx, chunk_idx)

    return chunks


def _emit(chunks, text, source_name, url, heading, today, page_idx, chunk_idx):
    chunks.append(Chunk(
        chunk_id=f"{source_name}_{page_idx}_{chunk_idx}",
        source_name=source_name,
        source_url=url,
        section_heading=heading,
        text=text.strip(),
        char_count=len(text),
        scraped_date=today,
        token_estimate=len(text) // 4,
    ))


def chunk_all(pages: List[RawPage], source_name: str, source_url: str) -> List[Chunk]:
    return chunk_pages(pages, source_name, source_url)


def flag_stale(chunks: List[Chunk], max_age_days: int = 30) -> List[Chunk]:
    """Return chunks whose scraped_date is older than max_age_days."""
    today = date.today()
    stale = []
    for c in chunks:
        try:
            scraped = date.fromisoformat(c.scraped_date)
            if (today - scraped).days > max_age_days:
                stale.append(c)
        except ValueError:
            pass
    return stale

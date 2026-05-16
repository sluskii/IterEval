"""
goveval/knowledge_base/embedder.py
Embeds chunks via sentence-transformers and upserts into PostgreSQL (pgvector).

Requires:
  pip install psycopg2-binary sentence-transformers
  PostgreSQL with pgvector extension installed.

"""

from __future__ import annotations

import os
from typing import List

from goveval.knowledge_base.chunker import Chunk

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
TABLE = "kb_chunks"


def _vec_str(arr) -> str:
    """Format a numpy/list array as a pgvector literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.8f}" for x in arr) + "]"


def _create_table(cur) -> None:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            chunk_id        TEXT PRIMARY KEY,
            source_name     TEXT NOT NULL,
            source_url      TEXT,
            section_heading TEXT,
            text            TEXT NOT NULL,
            char_count      INTEGER,
            scraped_date    TEXT,
            token_estimate  INTEGER,
            embedding       vector({EMBEDDING_DIM})
        )
    """)


def _create_index(cur) -> None:
    # IVFFlat index for approximate nearest-neighbour cosine search.
    # Created after data load so pgvector can build centroids from real data.
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {TABLE}_embedding_idx
        ON {TABLE} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """)


def embed_and_store(chunks: List[Chunk], dsn: str = "") -> int:
    """
    Embed all chunks with sentence-transformers and upsert into PostgreSQL.

    Steps:
      1. Create kb_chunks table and enable pgvector extension if not present
      2. Embed chunks in batches of 100 using all-MiniLM-L6-v2
      3. Upsert rows (ON CONFLICT chunk_id DO UPDATE)
      4. Create IVFFlat index after data load
      5. Return total chunk count in table

    Args:
        chunks: list of Chunk dataclasses from chunker.py
        dsn: PostgreSQL connection string; falls back to GOVEVAL_PG_DSN env var
    """
    import psycopg2
    from psycopg2.extras import execute_values
    from sentence_transformers import SentenceTransformer

    dsn = dsn or os.environ.get("GOVEVAL_PG_DSN", "postgresql://localhost/goveval")
    model = SentenceTransformer(EMBEDDING_MODEL)

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            _create_table(cur)
        conn.commit()

        BATCH = 100
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            texts = [c.text for c in batch]
            embeddings = model.encode(texts, normalize_embeddings=True)

            rows = [
                (
                    c.chunk_id,
                    c.source_name,
                    c.source_url,
                    c.section_heading,
                    c.text,
                    c.char_count,
                    c.scraped_date,
                    c.token_estimate,
                    _vec_str(emb),
                )
                for c, emb in zip(batch, embeddings)
            ]

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {TABLE} (
                        chunk_id, source_name, source_url, section_heading,
                        text, char_count, scraped_date, token_estimate, embedding
                    ) VALUES %s
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        source_name     = EXCLUDED.source_name,
                        source_url      = EXCLUDED.source_url,
                        section_heading = EXCLUDED.section_heading,
                        text            = EXCLUDED.text,
                        char_count      = EXCLUDED.char_count,
                        scraped_date    = EXCLUDED.scraped_date,
                        token_estimate  = EXCLUDED.token_estimate,
                        embedding       = EXCLUDED.embedding
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)",
                )
            conn.commit()

        with conn.cursor() as cur:
            _create_index(cur)
            conn.commit()
            cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
            return cur.fetchone()[0]

    finally:
        conn.close()


def get_connection(dsn: str = ""):
    """Return a live psycopg2 connection to the PostgreSQL database."""
    import psycopg2
    dsn = dsn or os.environ.get("GOVEVAL_PG_DSN", "postgresql://localhost/goveval")
    return psycopg2.connect(dsn)


from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_name: str
    source_url: str
    section_heading: str
    text: str
    scraped_date: str
    distance: float         # cosine distance — lower is more relevant

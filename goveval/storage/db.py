"""
goveval/storage/db.py
PostgreSQL backing store. Every eval run, question, response, verdict,
and improvement is logged here for full reproducibility.

"""

from __future__ import annotations

import json
import os
from datetime import datetime


class DB:
    def __init__(self, path: str = ""):
        import psycopg2

        dsn = path or os.environ.get("GOVEVAL_PG_DSN", "postgresql://localhost/goveval")
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = False
        self._init_schema()

    def _cursor(self):
        import psycopg2.extras
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def _init_schema(self) -> None:
        with self._cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id      TEXT PRIMARY KEY,
                    target_name TEXT,
                    created_at  TEXT,
                    config_json TEXT,
                    status      TEXT DEFAULT 'running'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    question_id   TEXT PRIMARY KEY,
                    run_id        TEXT,
                    category      TEXT,
                    language      TEXT,
                    text          TEXT,
                    ground_truth  TEXT,
                    gt_source     TEXT,
                    is_held_out   INTEGER DEFAULT 0,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    response_id   TEXT PRIMARY KEY,
                    run_id        TEXT,
                    question_id   TEXT,
                    iteration     INTEGER,
                    response_text TEXT,
                    latency_ms    REAL,
                    timestamp     TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS verdicts (
                    verdict_id    TEXT PRIMARY KEY,
                    response_id   TEXT,
                    metric        TEXT,
                    score         REAL,
                    detail_json   TEXT,
                    FOREIGN KEY(response_id) REFERENCES responses(response_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    improvement_id  TEXT PRIMARY KEY,
                    run_id          TEXT,
                    iteration       INTEGER,
                    path            TEXT,
                    description     TEXT,
                    before_json     TEXT,
                    after_json      TEXT,
                    applied         INTEGER DEFAULT 0,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS iterations (
                    id           SERIAL PRIMARY KEY,
                    run_id       TEXT,
                    iteration    INTEGER,
                    metrics_json TEXT,
                    timestamp    TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
            """)
        self._conn.commit()

    # ── Run management ────────────────────────────────────────────────────────

    def create_run(self, run_id: str, target_name: str, config: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (run_id, target_name, created_at, config_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, target_name, datetime.now().isoformat(), json.dumps(config)),
            )
        self._conn.commit()

    def complete_run(self, run_id: str) -> None:
        with self._cursor() as cur:
            cur.execute("UPDATE runs SET status='complete' WHERE run_id=%s", (run_id,))
        self._conn.commit()

    def get_runs(self) -> list[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM runs ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    def delete_run(self, run_id: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM verdicts WHERE response_id IN "
                "(SELECT response_id FROM responses WHERE run_id=%s)", (run_id,)
            )
            cur.execute("DELETE FROM responses WHERE run_id=%s", (run_id,))
            cur.execute("DELETE FROM questions WHERE run_id=%s", (run_id,))
            cur.execute("DELETE FROM improvements WHERE run_id=%s", (run_id,))
            cur.execute("DELETE FROM iterations WHERE run_id=%s", (run_id,))
            cur.execute("DELETE FROM runs WHERE run_id=%s", (run_id,))
        self._conn.commit()

    # ── Questions ─────────────────────────────────────────────────────────────

    def save_questions(self, questions: list[dict]) -> None:
        with self._cursor() as cur:
            for q in questions:
                cur.execute(
                    """
                    INSERT INTO questions
                        (question_id, run_id, category, language, text,
                         ground_truth, gt_source, is_held_out)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (question_id) DO UPDATE SET
                        category     = EXCLUDED.category,
                        language     = EXCLUDED.language,
                        text         = EXCLUDED.text,
                        ground_truth = EXCLUDED.ground_truth,
                        gt_source    = EXCLUDED.gt_source,
                        is_held_out  = EXCLUDED.is_held_out
                    """,
                    (
                        q["question_id"], q["run_id"], q["category"],
                        q.get("language", "en"), q["text"],
                        q.get("ground_truth", ""), q.get("gt_source", ""),
                        int(q.get("is_held_out", False)),
                    ),
                )
        self._conn.commit()

    def get_questions(self, run_id: str, held_out: bool = False) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM questions WHERE run_id=%s AND is_held_out=%s",
                (run_id, int(held_out)),
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Responses ─────────────────────────────────────────────────────────────

    def save_response(self, r: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO responses
                    (response_id, run_id, question_id, iteration,
                     response_text, latency_ms, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (response_id) DO UPDATE SET
                    response_text = EXCLUDED.response_text,
                    latency_ms    = EXCLUDED.latency_ms,
                    timestamp     = EXCLUDED.timestamp
                """,
                (
                    r["response_id"], r["run_id"], r["question_id"], r["iteration"],
                    r["response_text"], r.get("latency_ms"),
                    r.get("timestamp", datetime.now().isoformat()),
                ),
            )
        self._conn.commit()

    def get_responses(self, run_id: str, iteration: int) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM responses WHERE run_id=%s AND iteration=%s",
                (run_id, iteration),
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Verdicts ──────────────────────────────────────────────────────────────

    def save_verdict(self, v: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO verdicts (verdict_id, response_id, metric, score, detail_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (verdict_id) DO UPDATE SET
                    score       = EXCLUDED.score,
                    detail_json = EXCLUDED.detail_json
                """,
                (
                    v["verdict_id"], v["response_id"], v["metric"],
                    v.get("score"), json.dumps(v.get("detail", {})),
                ),
            )
        self._conn.commit()

    def get_verdicts(self, response_id: str) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM verdicts WHERE response_id=%s", (response_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Metrics snapshots ─────────────────────────────────────────────────────

    def save_iteration_metrics(self, run_id: str, iteration: int, metrics: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO iterations (run_id, iteration, metrics_json, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (run_id, iteration, json.dumps(metrics), datetime.now().isoformat()),
            )
        self._conn.commit()

    def get_all_iteration_metrics(self, run_id: str) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM iterations WHERE run_id=%s ORDER BY iteration",
                (run_id,),
            )
            return [
                {"iteration": r["iteration"], **json.loads(r["metrics_json"])}
                for r in cur.fetchall()
            ]

    # ── Generic query ─────────────────────────────────────────────────────────

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()

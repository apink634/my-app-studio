"""SQLite tables for sources, chunks, graph edges and question traces."""

from array import array
import json
import time
import uuid

from app import database
from app.settings import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    permission TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES rag_sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    embed_model TEXT NOT NULL,
    UNIQUE (source_id, position)
);
CREATE TABLE IF NOT EXISTS rag_edges (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    relation TEXT NOT NULL,
    object TEXT NOT NULL,
    chunk_id TEXT NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
    evidence TEXT NOT NULL,
    extract_model TEXT NOT NULL,
    UNIQUE (subject, relation, object, chunk_id)
);
CREATE TABLE IF NOT EXISTS rag_graph_runs (
    chunk_id TEXT PRIMARY KEY REFERENCES rag_chunks(id) ON DELETE CASCADE,
    kept INTEGER NOT NULL,
    rejected INTEGER NOT NULL,
    extract_model TEXT NOT NULL,
    ran_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_queries (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    question TEXT NOT NULL,
    outcome TEXT NOT NULL,
    trace TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rag_queries_user ON rag_queries(user_id, created_at);
"""


def initialize(settings: Settings) -> None:
    """Create the RAG tables next to the existing account tables."""
    with database.connect(settings) as connection:
        connection.executescript(SCHEMA)


def pack(vector: list[float]) -> bytes:
    """Store an embedding compactly as 32-bit floats."""
    return array("f", vector).tobytes()


def unpack(blob: bytes) -> list[float]:
    """Read a stored embedding back into a list."""
    values = array("f")
    values.frombytes(blob)
    return values.tolist()


def source_hash(settings: Settings, source_id: str) -> str | None:
    """Return the stored content hash for a source, or None if it is new."""
    with database.connect(settings) as connection:
        row = connection.execute(
            "SELECT content_hash FROM rag_sources WHERE id = ?", (source_id,)
        ).fetchone()
    return row["content_hash"] if row else None


def replace_source(settings: Settings, source: dict, rows: list[dict]) -> None:
    """Swap one source and its chunks in a single transaction.

    Deleting the old source cascades to its chunks and graph edges, so a changed
    page never leaves stale passages behind.
    """
    with database.connect(settings) as connection:
        connection.execute("DELETE FROM rag_sources WHERE id = ?", (source["id"],))
        connection.execute(
            "INSERT INTO rag_sources (id, title, url, permission, content_hash,"
            " fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                source["id"],
                source["title"],
                source["url"],
                source["permission"],
                source["content_hash"],
                int(time.time()),
            ),
        )
        connection.executemany(
            "INSERT INTO rag_chunks (id, source_id, position, text, embedding,"
            " embed_model) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    chunk["id"],
                    source["id"],
                    chunk["position"],
                    chunk["text"],
                    pack(chunk["embedding"]),
                    chunk["embed_model"],
                )
                for chunk in rows
            ],
        )


def chunks(settings: Settings) -> list[dict]:
    """All chunks with their source title and link."""
    with database.connect(settings) as connection:
        rows = connection.execute(
            "SELECT c.id, c.source_id, c.position, c.text, c.embedding, c.embed_model,"
            " s.title, s.url FROM rag_chunks c JOIN rag_sources s"
            " ON s.id = c.source_id ORDER BY c.source_id, c.position"
        ).fetchall()
    return [{**dict(row), "embedding": unpack(row["embedding"])} for row in rows]


def chunks_without_graph(settings: Settings) -> list[dict]:
    """Chunks that have not been through graph extraction yet."""
    with database.connect(settings) as connection:
        rows = connection.execute(
            "SELECT c.id, c.text FROM rag_chunks c LEFT JOIN rag_graph_runs g"
            " ON g.chunk_id = c.id WHERE g.chunk_id IS NULL ORDER BY c.id"
        ).fetchall()
    return [dict(row) for row in rows]


def save_edges(
    settings: Settings, chunk_id: str, kept: list[dict], rejected: int, model: str
) -> None:
    """Store the kept relationships for one chunk and record the run."""
    with database.connect(settings) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO rag_edges (id, subject, relation, object, chunk_id,"
            " evidence, extract_model) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    uuid.uuid4().hex,
                    edge["subject"],
                    edge["relation"],
                    edge["object"],
                    chunk_id,
                    edge["evidence"],
                    model,
                )
                for edge in kept
            ],
        )
        connection.execute(
            "INSERT OR REPLACE INTO rag_graph_runs (chunk_id, kept, rejected,"
            " extract_model, ran_at) VALUES (?, ?, ?, ?, ?)",
            (chunk_id, len(kept), rejected, model, int(time.time())),
        )


def edges(settings: Settings) -> list[dict]:
    """All graph edges with the source each one came from."""
    with database.connect(settings) as connection:
        rows = connection.execute(
            "SELECT e.id, e.subject, e.relation, e.object, e.chunk_id, e.evidence,"
            " s.title, s.url FROM rag_edges e JOIN rag_chunks c ON c.id = e.chunk_id"
            " JOIN rag_sources s ON s.id = c.source_id ORDER BY e.subject, e.relation"
        ).fetchall()
    return [dict(row) for row in rows]


def summary(settings: Settings) -> list[dict]:
    """Per-source counts for the public import record."""
    with database.connect(settings) as connection:
        rows = connection.execute(
            "SELECT s.id, s.title, s.url, s.permission, s.content_hash, s.fetched_at,"
            " (SELECT COUNT(*) FROM rag_chunks c WHERE c.source_id = s.id) AS chunks,"
            " (SELECT COUNT(*) FROM rag_edges e JOIN rag_chunks c ON c.id = e.chunk_id"
            "  WHERE c.source_id = s.id) AS edges,"
            " (SELECT COALESCE(SUM(g.rejected), 0) FROM rag_graph_runs g"
            "  JOIN rag_chunks c ON c.id = g.chunk_id WHERE c.source_id = s.id)"
            "  AS rejected_edges"
            " FROM rag_sources s ORDER BY s.id"
        ).fetchall()
    return [dict(row) for row in rows]


def save_query(settings: Settings, record: dict) -> str:
    """Keep the full trace of one question so its answer can be checked later.

    ``record`` holds user_id, question, outcome, trace and answer.
    """
    query_id = uuid.uuid4().hex
    with database.connect(settings) as connection:
        connection.execute(
            "INSERT INTO rag_queries (id, user_id, question, outcome, trace, answer,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                query_id,
                record["user_id"],
                record["question"],
                record["outcome"],
                json.dumps(record["trace"]),
                record["answer"],
                int(time.time()),
            ),
        )
    return query_id


def query(settings: Settings, query_id: str) -> dict | None:
    """Load one saved question and its trace."""
    with database.connect(settings) as connection:
        row = connection.execute(
            "SELECT * FROM rag_queries WHERE id = ?", (query_id,)
        ).fetchone()
    if row is None:
        return None
    return {**dict(row), "trace": json.loads(row["trace"])}


def recent_count(settings: Settings, user_id: str, seconds: int) -> int:
    """How many questions this user asked in the last ``seconds``."""
    with database.connect(settings) as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM rag_queries WHERE user_id = ?"
            " AND created_at > ?",
            (user_id, int(time.time()) - seconds),
        ).fetchone()
    return row["n"]

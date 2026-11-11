"""Store documents and retrieve the nearest passages in the local workspace."""

import os

import psycopg
from psycopg.rows import dict_row

WORKSPACE_ID = "local"


def connect():
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://knowflow:knowflow@127.0.0.1:5433/knowflow",
    )
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def find_document(digest: str, embedding_model: str):
    with connect() as connection:
        return connection.execute(
            "SELECT id FROM documents WHERE workspace_id = %s AND sha256 = %s AND embedding_model = %s",
            (WORKSPACE_ID, digest, embedding_model),
        ).fetchone()


def save_document(title: str, digest: str, embedding_model: str, passages, embeddings) -> tuple[int, bool]:
    with connect() as connection:
        row = connection.execute(
            """
            INSERT INTO documents (workspace_id, title, sha256, embedding_model)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (workspace_id, sha256, embedding_model) DO NOTHING
            RETURNING id
            """,
            (WORKSPACE_ID, title, digest, embedding_model),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                "SELECT id FROM documents WHERE workspace_id = %s AND sha256 = %s AND embedding_model = %s",
                (WORKSPACE_ID, digest, embedding_model),
            ).fetchone()
            return existing["id"], False

        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO chunks (document_id, page_number, text, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                [
                    (row["id"], page, text, str(embedding))
                    for (page, text), embedding in zip(passages, embeddings, strict=True)
                ],
            )
        return row["id"], True


def search(embedding: list[float], embedding_model: str, limit: int):
    with connect() as connection:
        return connection.execute(
            """
            SELECT c.id AS chunk_id, d.id AS document_id, d.title,
                   c.page_number, c.text,
                   c.embedding <=> %s::vector AS distance
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = %s AND d.embedding_model = %s
            ORDER BY distance, c.id
            LIMIT %s
            """,
            (str(embedding), WORKSPACE_ID, embedding_model, limit),
        ).fetchall()

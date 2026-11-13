"""Store documents and retrieve the nearest passages in the authenticated workspace."""

import os

import psycopg
from psycopg.rows import dict_row


def connect():
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://knowflow:knowflow@127.0.0.1:5433/knowflow",
    )
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def list_documents(workspace_id: str, embedding_model: str):
    with connect() as connection:
        return connection.execute(
            """
            SELECT id, title, searchable
            FROM (
                SELECT DISTINCT ON (sha256) id, title, embedding_model = %s AS searchable
                FROM documents
                WHERE workspace_id = %s
                ORDER BY sha256, searchable DESC, id DESC
            ) AS library
            ORDER BY id DESC
            """,
            (embedding_model, workspace_id),
        ).fetchall()


def delete_document(workspace_id: str, document_id: int) -> bool:
    with connect() as connection:
        deleted = connection.execute(
            """
            DELETE FROM documents AS candidate
            USING documents AS selected
            WHERE selected.workspace_id = %s AND selected.id = %s
              AND candidate.workspace_id = selected.workspace_id
              AND candidate.sha256 = selected.sha256
            """,
            (workspace_id, document_id),
        )
        return deleted.rowcount > 0


def has_documents(workspace_id: str, embedding_model: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM documents WHERE workspace_id = %s AND embedding_model = %s
            ) AS has_documents
            """,
            (workspace_id, embedding_model),
        ).fetchone()
    return row["has_documents"]


def find_document(workspace_id: str, digest: str, embedding_model: str):
    with connect() as connection:
        return connection.execute(
            "SELECT id FROM documents WHERE workspace_id = %s AND sha256 = %s AND embedding_model = %s",
            (workspace_id, digest, embedding_model),
        ).fetchone()


def save_document(workspace_id: str, title: str, digest: str, embedding_model: str, passages, embeddings) -> tuple[int, bool]:
    with connect() as connection:
        row = connection.execute(
            """
            INSERT INTO documents (workspace_id, title, sha256, embedding_model)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (workspace_id, sha256, embedding_model) DO NOTHING
            RETURNING id
            """,
            (workspace_id, title, digest, embedding_model),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                "SELECT id FROM documents WHERE workspace_id = %s AND sha256 = %s AND embedding_model = %s",
                (workspace_id, digest, embedding_model),
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


def search(workspace_id: str, embedding: list[float], embedding_model: str, limit: int):
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
            (str(embedding), workspace_id, embedding_model, limit),
        ).fetchall()

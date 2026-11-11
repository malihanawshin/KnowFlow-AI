CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id text NOT NULL,
    title text NOT NULL,
    sha256 text NOT NULL,
    embedding_model text NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number integer NOT NULL CHECK (page_number > 0),
    text text NOT NULL,
    embedding vector NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS documents_workspace_hash_model_idx
    ON documents (workspace_id, sha256, embedding_model);

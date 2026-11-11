BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS embedding_model text NOT NULL DEFAULT 'text-embedding-3-small';
ALTER TABLE documents
    ALTER COLUMN embedding_model DROP DEFAULT,
    DROP CONSTRAINT IF EXISTS documents_workspace_id_sha256_key;

ALTER TABLE chunks ALTER COLUMN embedding TYPE vector;

CREATE UNIQUE INDEX IF NOT EXISTS documents_workspace_hash_model_idx
    ON documents (workspace_id, sha256, embedding_model);

COMMIT;

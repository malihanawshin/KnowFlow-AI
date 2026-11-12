CREATE TABLE IF NOT EXISTS workspaces (
    id text PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_salt bytea NOT NULL,
    password_hash bytea NOT NULL,
    workspace_id text NOT NULL REFERENCES workspaces(id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash bytea PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);

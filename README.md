# KnowFlow AI

A Next.js workspace and FastAPI backend for uploading text-based PDFs, searching passages with pgvector, and answering questions with page-level citations.

## Run locally

From the project root, with Python 3.11+ and a running Docker daemon:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
docker compose up -d --wait db
```

Add `OPENROUTER_API_KEY` to the ignored `backend/.env` file, then start the API:

```bash
uvicorn backend.main:app --reload --env-file backend/.env
```

The database defaults to port 5433. Set `DATABASE_URL` to use a different database and apply `backend/schema.sql` there. Compose applies the schema when it creates the database volume. OpenRouter defaults to the free `liquid/lfm-2.5-embedding-350m:free` embedding model and `openrouter/free` for answers. Set `OPENROUTER_EMBEDDING_MODEL` or `OPENROUTER_ANSWER_MODEL` to override them. The answer model must support Chat Completions JSON mode. Re-upload documents after changing embedding models so search uses the matching vectors. To use OpenAI directly, set `OPENAI_API_KEY` and optionally `OPENAI_ANSWER_MODEL`. OpenRouter takes precedence when both keys are set.

If you already created the database with the original fixed-dimension schema, apply the migration before starting the API:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U knowflow -d knowflow < backend/migrate_embedding_models.sql
```

## Create an account

On an existing database volume, apply the additive sign-in schema once before using the updated API. Fresh volumes apply it automatically.

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U knowflow -d knowflow < backend/schema_auth.sql
```

Choose **Sign up** in the browser workspace to create an account. KnowFlow creates a private workspace for it and signs you in.

For existing documents uploaded before sign-in, an administrator can still provision an account in the original `local` workspace. From the project root, with the backend environment activated:

```bash
python -m backend.create_user reader@example.test local
```

The command prompts for a password without echoing it. Each account belongs to one workspace. A new browser sign-up starts with an empty workspace.

Sign-in uses an eight-hour, revocable HTTP-only cookie. For HTTPS, set `KNOWFLOW_SECURE_COOKIE=1` in `backend/.env`.

## Open the browser workspace

With the backend running, start the frontend from the project root in a second terminal. Use Node.js 20.9 or newer.

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open [localhost:3000](http://localhost:3000) and sign up or sign in. Choose `fixtures/employee-handbook.pdf`, select **Upload PDF**, then ask the suggested parental leave question. The answer should cite page 2 and show the supporting passage.

The frontend proxies requests to FastAPI at `http://127.0.0.1:8000`. If the backend uses a different address, set `KNOWFLOW_API_URL` when starting the frontend. Keep model credentials in `backend/.env`.

## Try the handbook through the API

Use the interactive [FastAPI docs](http://localhost:8000/docs). Send your credentials to `POST /login` to establish the session cookie, then call `/documents`, `/search`, or `/ask` in the same browser. To inspect PDF extraction independently:

```bash
python backend/parse_pdf.py fixtures/employee-handbook.pdf
```

Upload sends extracted text to your configured model provider for embeddings. Asking a question sends the question and retrieved passages for answer generation. Use the fictional fixture for testing.

## Evaluate retrieval and answers

With FastAPI running and the backend environment activated, run:

```bash
python evaluation/run.py --email reader@example.test
```

The runner signs in and uploads the fictional handbook if needed, then checks five questions. It reports whether the expected passage appears in the top five search results, whether the answer contains the expected fact, whether a citation contains the expected passage on the correct page, and whether the uncovered equipment allowance question returns insufficient evidence with no citations.

Use a workspace containing only the handbook for a comparable baseline. To also confirm that a second, empty workspace cannot retrieve or cite the handbook, add `--other-email reviewer@example.test`. The runner prompts for each password. It exits with status `1` for failed checks and `2` for API or setup errors. Use `--base-url` if FastAPI runs on another port.

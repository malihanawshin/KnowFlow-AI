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

## Open the browser workspace

With the backend running, start the frontend from the project root in a second terminal. Use Node.js 20.9 or newer.

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open [localhost:3000](http://localhost:3000). Choose `fixtures/employee-handbook.pdf`, select **Upload PDF**, then ask the suggested parental leave question. The answer should cite page 2 and show the supporting passage. The equipment allowance question should return insufficient evidence.

The frontend proxies uploads and questions to FastAPI at `http://127.0.0.1:8000`. If the backend uses a different address, set `KNOWFLOW_API_URL` when starting the frontend. Keep model credentials in `backend/.env`.

## Try the handbook through the API

Use the interactive API docs at [localhost:8000/docs](http://127.0.0.1:8000/docs) or run:

```bash
curl -f -F 'file=@fixtures/employee-handbook.pdf' http://127.0.0.1:8000/documents

curl -f http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"What paid leave do I get after adopting a child?"}'

curl -f http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many paid parental leave days do employees receive?"}'

curl -f http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the annual home office equipment allowance?"}'
```

Expect the parental leave answer to cite page 2 and the equipment question to return insufficient evidence. Re-uploading the same file returns its existing document ID. To inspect PDF extraction independently:

```bash
python backend/parse_pdf.py fixtures/employee-handbook.pdf
```

This demo uses one local workspace. Upload sends extracted text to your configured model provider for embeddings, and asking a question sends the question and retrieved passages for answer generation. Use the fictional fixture for testing.

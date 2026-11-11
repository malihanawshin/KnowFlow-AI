# KnowFlow AI

A local FastAPI backend for uploading text-based PDFs, searching passages with pgvector, and answering questions with page-level citations.

## Run locally

From the project root, with Python 3.11+ and a running Docker daemon:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
docker compose up -d --wait db
```

Set `OPENAI_API_KEY` in your shell, then start the API:

```bash
uvicorn backend.main:app --reload
```

The database defaults to port 5433. Set `DATABASE_URL` to use a different database and apply `backend/schema.sql` there. Compose applies the schema when it creates the database volume. OpenAI provides embeddings via `text-embedding-3-small` and generates answers with `gpt-4.1-mini` by default. Set `OPENAI_ANSWER_MODEL` to choose another model that supports Chat Completions JSON mode.

## Try the handbook

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

This demo uses one local workspace. Upload sends extracted text to OpenAI for embeddings, and asking a question sends the question and retrieved passages for answer generation. Use the fictional fixture for testing.

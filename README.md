# QueryGuard

QueryGuard is a guarded Text-to-SQL application that turns natural-language questions into read-only PostgreSQL queries using a local CSV-to-database workflow, a LanceDB retrieval layer, and an OpenRouter-backed SQL generator.

It is designed for analytics over CSV datasets: every CSV in `data/` is loaded as a PostgreSQL table unless it is the example dataset (`spider_text_sql.csv`), which is used as retrieval context for few-shot prompting. Generated SQL is checked before execution to block destructive operations and enforce a safe row limit.

## What is included

- CSV ingestion into PostgreSQL with table names derived from filenames.
- Schema extraction from the loaded tables.
- RAG over question/SQL examples with a persistent local LanceDB index.
- OpenRouter LLM generation with structured JSON output.
- SQL guardrails: SELECT-only, single statement, destructive keyword blocking, subquery depth limit, automatic LIMIT.
- Result execution, confidence scoring, and query history in memory.
- Streamlit UI for running questions, inspecting generated SQL, and submitting feedback/corrections.

## Project structure

- `app/config.py`: environment configuration and settings.
- `app/data_source.py`: loads `data/*.csv` into PostgreSQL tables.
- `app/schema.py`: database schema introspection for prompt grounding.
- `app/rag.py`: local LanceDB retriever with deterministic hash embeddings and feedback persistence.
- `app/generator.py`: SQL generation against the live schema and retrieved examples.
- `app/guardrails.py`: SQL validation and safety checks.
- `app/service.py`: orchestration for generation, validation, execution, feedback, and history.
- `app/main.py`: FastAPI application exposing the HTTP endpoints.
- `streamlit_app.py`: browser interface.
- `tests/`: app-level checks for API, generator, guardrails, and RAG behavior.

## Requirements

- Python 3.11+
- PostgreSQL (local or via Docker)
- OpenRouter-compatible API key (or the legacy `GEMINI_API_KEY` alias still works in config)
- Optional: Docker Compose for a ready-made local stack

## Quick start

1. Create a virtual environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a `.env` file and set the required variables:

```env
DATABASE_URL=postgresql://text2sql:text2sql@localhost:5432/text2sql
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

The config also accepts `GEMINI_API_KEY` and `GEMINI_MODEL` as aliases, so older setups still work.

3. Place your source CSV files in `data/`.

Each `*.csv` in `data/` becomes a PostgreSQL table when the app starts, except for `spider_text_sql.csv`, which is treated as the retrieval/example dataset. For example:

- `head.csv` -> `head`
- `department.csv` -> `department`
- `management.csv` -> `management`

4. Start PostgreSQL locally or through Docker.

5. Run the API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Run the Streamlit UI in another terminal:

```powershell
$env:API_URL = "http://localhost:8000"
streamlit run streamlit_app.py
```

Then open:

- API docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501

## Docker Compose

The repository includes a ready-made local stack:

```powershell
docker compose up --build
```

This starts:

- FastAPI API on http://localhost:8000
- Streamlit app on http://localhost:8501
- PostgreSQL database on the internal Docker network

The Compose file also persists LanceDB data and Postgres data in Docker volumes.

## How the app works

### Data loading

`CsvWarehouse` scans the `data/` directory at startup and imports each CSV into PostgreSQL. It drops and recreates each table if it exists, so the in-memory database stays synchronized with the CSV files.

The example CSV (`data/spider_text_sql.csv`) is intentionally excluded from table creation because it contains prompt/SQL pairs rather than source data.

### Schema grounding

`extract_schema` inspects the database tables and exposes a minimal schema description to the generator so the model works from the actual live schema rather than guessing table names.

### Retrieval and generation

`LanceDBRAGRetriever` stores historical example questions and SQL pairs in a local LanceDB collection. It uses deterministic hash-based embeddings and LangChain splitters so retrieval remains local and reproducible.

`QueryGenerator` retrieves the most relevant examples, builds a prompt with the live schema, and asks the LLM to return JSON containing:

- `sql`
- `explanation`
- `tables`
- `confidence`
- `notes`

### Guardrails

`check_query` validates the generated SQL before it is executed:

- only `SELECT` statements are allowed
- multiple statements are rejected
- destructive keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, and `CREATE` are blocked
- subqueries are capped to a maximum nesting depth
- a `LIMIT` clause is automatically added if the SQL does not already include one

The default row cap is 1000, configurable through `MAX_ROWS` in the settings.

### Execution

`QueryService.run` executes the guarded SQL against PostgreSQL, packs the result rows, calculates a simple confidence score, and stores the last 50 queries in memory.

## API

### `GET /health`

Returns service health:

```json
{"status": "ok"}
```

### `POST /v1/query`

Request:

```json
{ "question": "Show the top 10 departments by budget" }
```

The response contains:

- `query_id`
- `question`
- `sql`
- `explanation`
- `rows`
- `row_count`
- `execution_ms`
- `confidence`
- `confidence_breakdown`
- `guardrail_warnings`
- `validation_notes`
- `tables`
- `blocked`
- `retrieved_examples`
- `provider`

### `GET /v1/schema`

Returns the live database schema as JSON.

### `GET /v1/history`

Returns the recent in-memory query history.

### `POST /v1/feedback`

Stores feedback and optional corrected SQL for future retrieval. Payload example:

```json
{
  "query_id": "abc123",
  "correct": false,
  "note": "The query missed the filtering condition",
  "corrected_sql": "SELECT ... LIMIT 1000",
  "question": "Show departments with budget above 5M",
  "original_sql": "SELECT * FROM department"
}
```

## UI features

The Streamlit app includes:

- sidebar question examples
- automatic SQL generation and execution
- result table rendering
- confidence meter and signal breakdown
- generated SQL preview
- thumbs-up / thumbs-down feedback
- corrected-SQL submission back into the retrieval corpus

## Notes and limitations

- The app requires a valid OpenRouter API key to generate SQL.
- The RAG layer still works without the API key for retrieval, but generation fails if the key is missing.
- Query history is stored in memory only and resets when the FastAPI process restarts.
- The default safeguard is a read-only, LIMITed SELECT path; the service will not execute any destructive SQL.

## Example environment variables

```env
DATABASE_URL=postgresql://text2sql:text2sql@localhost:5432/text2sql
DATA_DIR=data
EXAMPLES_CSV=data/spider_text_sql.csv
MAX_ROWS=1000
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
RAG_TOP_K=5
RAG_DATABASE_PATH=data/lancedb
```

This repo is intentionally lightweight and local-first: the main source of truth is your CSV data, and the database schema plus Retrieval-Augmented Generation are built around that data automatically.

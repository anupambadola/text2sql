# QueryGuard: Text-to-SQL with Guardrails

A portfolio-ready Text-to-SQL interface built with FastAPI, Streamlit, DuckDB, ChromaDB RAG, Gemini, SQL parsing guardrails, and confidence signals. It retrieves approved question-to-SQL examples from CSV, grounds Gemini generation with those examples and the live schema, blocks destructive operations, enforces a row limit, and exposes the reasoning signals behind each answer.

## Run locally

```powershell
py -3.11 -m venv virtualenv
.\virtualenv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your Gemini key to `.env`:

```powershell
GEMINI_API_KEY=your-key-here
```

Then initialize the database:

Start the API in one terminal:

```powershell
uvicorn app.main:app --reload
```

Start Streamlit in another:

```powershell
streamlit run streamlit_app.py
```

Open `http://localhost:8501`. API docs are at `http://localhost:8000/docs`.

## Docker

```powershell
docker compose up --build
```

The API runs on port 8000 and Streamlit on port 8501.

## API

- `POST /v1/query` with `{ "question": "Show the top customers by revenue" }`
- `GET /v1/schema`
- `GET /v1/history`
- `POST /v1/feedback`

## Architecture

- `app/data_source.py`: enterprise CSV catalog that loads user CSV files into DuckDB tables; the question/SQL CSV is excluded from analytical tables.
- `app/schema.py`: database schema introspection over the loaded CSV tables.
- `app/rag.py`: LangChain chunking plus ChromaDB persistent vector index over CSV question-to-SQL examples.
- `app/generator.py`: Gemini structured-output generation grounded by retrieved examples, with an offline fallback.
- `app/guardrails.py`: SELECT-only enforcement, destructive keyword blocking, single-statement validation, subquery depth check, and automatic `LIMIT`.
- `app/service.py`: execution, result packaging, confidence scoring, and in-memory audit history.
- `streamlit_app.py`: query interface with SQL, results, warnings, and confidence breakdown.

Place the source-table CSV files in `data/`. Each filename becomes a table name, for example `head.csv` becomes `head`. The supplied `spider_text_sql.csv` is a RAG training/example set and is excluded from SQL tables because it contains questions and SQL pairs, not source rows. Add the corresponding `head.csv`, `department.csv`, and `management.csv` files to execute those examples.

Without `GEMINI_API_KEY`, the app still starts using a local fallback generator; Chroma retrieval remains active and is reported in the API response.

# Backend (FastAPI)

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your Gemini key in `.env`:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_CHAT_MODEL=gemini-3-flash-preview
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

## Run API

```bash
uvicorn app.main:app --reload --port 8000
```

The chat response engine is grounding-first and explanation-first:
- `Direct Answer` to user intent
- `Explanation from Chopai` using retrieved context
- `Grounding` references

## Run Ingestion

```bash
python -m scripts.run_ingest
```

Or via API:

```bash
curl -X POST http://localhost:8000/api/ingest
```

## Tests

```bash
PYTHONPATH=. pytest -q
```

## Benchmark Eval

```bash
PYTHONPATH=. python -m scripts.eval_benchmark --input benchmarks/sample_queries.jsonl --top-k 3
```

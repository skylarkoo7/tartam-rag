# Backend (FastAPI)

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your OpenAI key in `.env`:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_CHAT_MODEL=gpt-5.2
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_VISION_MODEL=gpt-5.2
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

## Multilingual Validation Report

```bash
PYTHONPATH=. python -m scripts.generate_multilingual_report --api-base http://127.0.0.1:8000/api --output-dir reports
```

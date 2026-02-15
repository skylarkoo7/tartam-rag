# Tartam Multilingual RAG Chatbot

Local-first RAG chatbot for Tartam scripture corpus with:
- Grounded answers from Tartam PDFs (Hindi + Gujarati corpora)
- LLM-based explanations (not just retrieval snippets)
- Inline chopai cards in chat UI (with meaning + source metadata)
- Multilingual interaction support: Hindi, Gujarati, English, Hinglish (`kaise ho`), Gujarati-in-English (`kem cho`)

## Current Status

Implemented in this repository:
- `backend/` FastAPI API + ingestion + hybrid retrieval + Gemini integration
- `frontend/` Next.js chat app with filters, session history, inline citations
- `tartam/` sample PDF corpus (Hindi-arth + Gujarati-arth)

## Architecture

### Backend (FastAPI)
- PDF ingestion pipeline
  - Extract text from PDFs
  - Parse granth/prakran/chopai/meaning chunks
  - Store canonical chunks in SQLite
- Retrieval pipeline
  - SQLite FTS5 lexical search
  - Chroma vector search (if installed)
  - Reciprocal Rank Fusion (RRF)
- Chat generation
  - Uses retrieved citations as strict grounding context
  - LLM response format:
    - `Direct Answer`
    - `Explanation from Chopai`
    - `Grounding`
- Persistence
  - Chat history in SQLite by `session_id`
  - Session memory in SQLite (`summary_text` + `key_facts`) to preserve long-context continuity
  - Server-side session list API for persistent history drawer
  - Ingestion run logs

### Frontend (Next.js + Tailwind)
- Chat UI with smooth message flow
- Inline expandable citation cards below assistant responses
- Filters: language mode, granth, prakran
- Session history drawer (server-backed sessions + local current-session id)
- One-click ingestion trigger button

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   ├── scripts/
│   ├── tests/
│   ├── benchmarks/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   └── .env.example
└── tartam/
    ├── Shri Tartamsagar  (hindi-arth)/
    └── Shri Tartamsagar (guj-arth)/
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- Gemini API key (for full LLM reasoning and embeddings)

Optional for OCR fallback:
- Tesseract OCR
- `pdf2image` runtime dependencies

## Setup

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `/Users/skylark/Documents/github/tartam-rag/backend/.env`:

```env
GEMINI_API_KEY=your_key_here
```

Run API:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open: `http://localhost:3000`

The frontend calls backend at `NEXT_PUBLIC_API_BASE` (default: `http://localhost:8000/api`).

## Ingestion

You must ingest corpus before chatting.

Option A: API

```bash
curl -X POST http://localhost:8000/api/ingest
```

Option B: script

```bash
cd backend
python -m scripts.run_ingest
```

## API Endpoints

- `GET /api/health`
- `POST /api/ingest`
- `GET /api/filters`
- `GET /api/history/{session_id}`
- `GET /api/sessions`
- `POST /api/chat`

### `POST /api/chat` example

```json
{
  "session_id": "demo-session",
  "message": "mohajal kya batata hai?",
  "style_mode": "auto",
  "filters": {
    "granth": "",
    "prakran": ""
  },
  "top_k": 6
}
```

## Language Behavior

`style_mode` values:
- `auto`
- `hi`
- `gu`
- `en`
- `hi_latn`
- `gu_latn`

In `auto`, backend detects script/style and tries to mirror user style.

## Testing

```bash
cd backend
PYTHONPATH=. pytest -q
```

## Benchmark Script

```bash
cd backend
PYTHONPATH=. python -m scripts.eval_benchmark --input benchmarks/sample_queries.jsonl --top-k 3
```

## Makefile Shortcuts (from repo root)

```bash
make backend
make frontend
make ingest
make test
```

## Notes / Limitations

- Gujarati PDFs may require AES decryption support from `pycryptodome`.
- OCR fallback is optional and disabled by default.
- Without Gemini key, chat answering is disabled (agentic mode requires Gemini for reasoning).
- Retrieval quality depends on PDF extraction quality and parser heuristics.

## Frontend Status (answer to "what about frontend?")

Frontend is implemented and included in this repo under `/Users/skylark/Documents/github/tartam-rag/frontend` with:
- working chat page,
- filter bar,
- inline chopai citation cards,
- session drawer,
- backend API integration.

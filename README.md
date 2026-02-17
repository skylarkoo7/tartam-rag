# Tartam Multilingual RAG Chatbot

Local-first RAG chatbot for Tartam scripture corpus with:
- Grounded answers from Tartam PDFs (Hindi + Gujarati corpora)
- LLM-based explanations (not just retrieval snippets)
- Inline chopai cards in chat UI (with meaning + source metadata)
- Right-side `react-pdf` source viewer (page navigation + zoom for cited PDF page)
- PDF page API for citations (`GET /api/pdf/{citation_id}`)
- Multilingual interaction support: Hindi, Gujarati, English, Hinglish (`kaise ho`), Gujarati-in-English (`kem cho`)
- Structured query understanding for references like:
  - `singar granth prakran 14 to 19 summary and explanation`
  - `what did chaupai 4 of prakran 14 says`
  - `prakran 19 ma ketli chaupai che`
- Session context memory for granth/prakran/chopai continuity across follow-up turns
- One-click answer conversion options (Hindi/Gujarati/English + script variants)
- Relative chopai indexing inside each prakran (supports queries like `prakran 14 chaupai 4`)

## Current Status

Implemented in this repository:
- `backend/` FastAPI API + ingestion + hybrid retrieval + OpenAI integration
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
  - OpenAI-only pipeline (`gpt-5.2` + `text-embedding-3-large`)
  - Uses retrieved citations as strict grounding context
  - Applies deterministic reference constraints (granth/prakran/chopai) before generation
  - LLM response format:
    - `Direct Answer`
    - `Explanation from Chopai`
    - `Grounding`
- Persistence
  - Thread-wise chat history in SQLite by `session_id` (thread id)
  - Dedicated `chat_threads` table (title, updated_at, message_count)
  - Session memory in SQLite (`summary_text` + `key_facts`) to preserve long-context continuity
  - Session reference context in SQLite (`granth_name`, `prakran_number`, `chopai_number`, range)
  - Server-side session list API for persistent history drawer
  - Ingestion run logs

### Frontend (Next.js + Tailwind)
- Chat UI with smooth message flow
- Inline expandable citation cards below assistant responses
- Filters: language mode, granth, prakran
- Session history drawer (server-backed sessions + local current-session id)
- Thread creation/listing via API (`POST /api/threads`, `GET /api/threads`)
- Interactive citation cards that sync with right-side PDF viewer
- LLM runtime health badge (shows OpenAI availability/health)
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
- Node.js 20.9+ (Next.js 16 requirement)
- npm
- OpenAI API key (for LLM reasoning, embeddings, and OCR recovery)

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
OPENAI_API_KEY=your_key_here
OPENAI_CHAT_MODEL=gpt-5.2
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_VISION_MODEL=gpt-5.2
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
- `GET /api/threads`
- `POST /api/threads`
- `POST /api/chat`
- `POST /api/convert`
- `GET /api/pdf/{citation_id}`

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

Answer conversion endpoint (`POST /api/convert`) supports:
- `en`, `hi`, `gu`, `hi_latn`, `gu_latn`
- `en_deva` (English words in Devanagari script)
- `en_gu` (English words in Gujarati script)

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
- OCR fallback is enabled by default and can be tuned via `.env`.
- Without `OPENAI_API_KEY`, chat reasoning is disabled (retrieval-only context still available).
- Retrieval quality depends on PDF extraction quality and parser heuristics.
- OpenAI keys can fail due quota/auth/rate limits; UI/API surfaces this explicitly via `/api/health` and chat debug payload.

Recommended OCR settings (already enabled in sample env):
- `ENABLE_OCR_FALLBACK=true`
- `OCR_QUALITY_THRESHOLD=0.22`
- `OCR_FORCE_ON_GARBLED=true`
- `INGEST_OPENAI_OCR_MAX_PAGES=200`
- `ALLOW_OPENAI_PAGE_OCR_RECOVERY=true`

## Frontend Status (answer to "what about frontend?")

Frontend is implemented and included in this repo under `/Users/skylark/Documents/github/tartam-rag/frontend` with:
- working chat page,
- filter bar,
- inline chopai citation cards,
- session drawer,
- backend API integration.

## Version Baseline (checked on February 17, 2026)

- Frontend:
  - `next@16.1.6`
  - `react@19.2.4`
  - `react-dom@19.2.4`
  - `react-pdf@10.3.0`
- Backend:
  - `fastapi==0.129.0`
  - `uvicorn==0.41.0`
  - `pydantic==2.12.5`
  - `chromadb==1.5.0`
  - `pypdf==6.7.0`
  - `openai==2.21.0`
  - default chat model: `gpt-5.2`
  - default embedding model: `text-embedding-3-large`

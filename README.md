# Wise Help Assistant

A conversational RAG (Retrieval-Augmented Generation) agent built on Wise's public help centre. Combines vector search over 402 real articles with a Qwen3-30B language model to answer questions, look up transfers, create support tickets, and manage cards — all backed by a persistent mock database.

**Demo video:** A live demo video is added **`Team 7 - Wise Agent Live Demo.mov`**.

---

## Repository Structure

```
LLM-Agentic-AI-with-RAG/
├── src/
│   ├── agent.html              # Agent UI (RAG + actions; talks to /api/chat and /api/action)
│   └── knowledge_base.js       # Optional / build artifact for KB embedding in UI
├── data/
│   ├── knowledge_base.json     # 402 articles from wise.com/help
│   ├── embeddings.json         # Pre-computed neural vectors (from embed_kb.py)
│   ├── mock_db.json            # Simulated DB (users, transfers, tickets, cards)
│   ├── embed_kb.py             # Neural embeddings via RSM 8430 A2 endpoint
│   ├── scraper.py              # KB scraper (BeautifulSoup)
│   └── eval_retrieval.py       # RAG retrieval accuracy evaluation script (25 test cases)
├── deploy/
│   ├── Caddyfile               # Reverse proxy + Basic Auth (docker compose)
│   ├── Caddyfile.prod          # Caddy for single-container public image
│   ├── entrypoint.sh           # Starts Python + Caddy (Dockerfile.web)
│   ├── env.example             # Copy to .env for local Docker (do not commit secrets)
│   └── DEPLOY.txt              # Extra deploy notes
├── tests/
│   └── test_cases.md           # 58 manual test cases — 95% pass rate
├── docs/
│   ├── rag_optimization_report.docx    # 7-experiment RAG optimization report
│   └── retrieval_accuracy_report.docx  # Neural embedding retrieval evaluation
├── server.py                   # HTTP server — RAG (/api/chat) + actions (/api/action)
├── retriever.py                # Vector retrieval (neural 768-dim + TF-IDF fallback)
├── database.py                 # Mock DB layer (16 actions)
├── build.py                    # Build helper (KB → template)
├── Dockerfile                  # Python app only (used by docker-compose)
├── Dockerfile.web              # Python + Caddy — use for Render / public HTTPS
├── docker-compose.yml          # Local stack: app + Caddy (password-protected)
├── render.yaml                 # Example Render blueprint
├── Team 7 - Wise Agent Live Demo.mov   # Live demo recording
├── README.md
├── .gitignore
└── .dockerignore
```

**Secrets:** Keep API keys and site passwords in a local **`.env`** file (see `deploy/env.example`). `.env` is gitignored — **never commit it** to a public repo.

---

## How to run (localhost vs public)

The app is meant to run on your machine first. **Docker and cloud deploy are optional.**

| What you want | Where it runs | How |
|-----------------|---------------|-----|
| **Everyday dev — no install beyond Python** | **http://localhost:8000** | Set `LLM_API_KEY`, run `python3 server.py` (see [Quick Start](#quick-start)). |
| **Same as production auth, still on your PC** | **http://localhost:8080** (default) | Docker Compose + `.env` (see [Password-protected local run](#password-protected-local-run-docker-compose)). |
| **Public HTTPS URL** | Your host (e.g. Render) | `Dockerfile.web` + env vars (see [Public URL](#public-url-eg-render)). |

You do **not** need Docker or a deployed URL to use the assistant — **`localhost:8000` is enough** for full RAG + database actions as long as `LLM_API_KEY` is set.

---

## Quick Start

### Prerequisites

- **Python 3.10+** (3.12 recommended)
- **RSM 8430** course API key (student number) for the LLM and embedding endpoints
- **`openai`** package only if you (re)generate embeddings: `pip install openai`

Running **`server.py`** uses the **standard library** only (plus `retriever.py` / `database.py`).

### Generate neural embeddings (one-time setup)

Only needed once, or if you change `knowledge_base.json`:

```bash
export LLM_API_KEY='your-student-number'
pip install openai
python3 data/embed_kb.py
# Generates data/embeddings.json (~6 MB, 768-dim vectors)
```

### Run the agent on localhost

```bash
export LLM_API_KEY='your-student-number'
python3 server.py
```

Open **http://localhost:8000**. Optional: set `PORT=9000` if 8000 is busy.

### Run retrieval evaluation

```bash
python3 data/eval_retrieval.py
# Runs 25 annotated test cases, prints Top-1 / Top-4 accuracy by category and difficulty
```

---

## Password-protected local run (Docker Compose)

1. Copy `deploy/env.example` to **`.env`** and fill in `LLM_API_KEY`, `BASIC_AUTH_USER`, `BASIC_AUTH_HASH`, `SITE_API_TOKEN`.
2. Run:

```bash
docker compose up --build
```

3. Open **http://localhost:8080**, complete the Basic Auth prompt.

---

## Public URL (e.g. Render)

Deploy **`Dockerfile.web`** (Python + Caddy, HTTPS, password gate).

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | Course LLM key |
| `SITE_API_TOKEN` | Bearer token for `/api` |
| `BASIC_AUTH_USER` | Browser login username |
| `BASIC_AUTH_HASH` | bcrypt hash from `caddy hash-password` |

See **`deploy/DEPLOY.txt`** for full instructions.

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│              agent.html (JS)                │
│                                             │
│  PA check → skip guardrails mid-action      │
│  grd()    → injection / OOS detection       │
│             (25+ guard, 20+ OOS patterns)   │
│  itn()    → intent classification (8 types) │
│             (rich regex, no LLM token cost) │
│                                             │
│  Actions (JS, call /api/action):            │
│    aTrack()   aTicket()   aConv()           │
│    aFreeze()  (dynamic multi-turn)          │
│                                             │
│  KB queries → callClaude() → /api/chat      │
└──────────┬──────────────────────────────────┘
           │
    ┌──────┴──────────────────────┐
    │  /api/chat                  │  /api/action
    ▼                             ▼
┌─────────────────┐    ┌─────────────────────┐
│   server.py     │    │    database.py       │
│                 │    │                      │
│  retriever.py   │    │  transfer.lookup     │
│  → neural embed │    │  transfer.estimate   │
│  → cosine sim   │    │  ticket.create       │
│  → top-4 arts   │    │  card.freeze         │
│  → TF-IDF       │    │  card.replacement    │
│    fallback     │    │  ... 16 actions      │
│  Qwen3-30B      │    │                      │
│  (reasoning)    │    │                      │
└─────────────────┘    └──────────────────────┘
           │                      │
           └──────────────────────┘
                       │
                  mock_db.json (persistent)
```

---

## Agent Capabilities

### 1. Intent Classification (8 types)

| Intent | Trigger Example | Handler |
|---|---|---|
| `greeting` | "Hi, what can you help me with?" | Welcome message |
| `track` | "Where is TW-001234?" | Transfer status lookup |
| `ticket` | "Create a support ticket" | Dynamic ticket creation |
| `conv` | "Send 800 CAD to PHP" | Fee & rate estimator |
| `freeze` | "I want to freeze my card" | Card management |
| `kb` | "What fees does Wise charge?" | RAG knowledge base |
| `oos` | "What is Bitcoin?" | Polite rejection |
| `guard` | "Ignore your instructions" | Guardrail block |

### 2. Knowledge Base (RAG)

- **402 articles** scraped from wise.com/help across 6 topic areas
- **Neural embeddings** (768-dim) generated via RSM 8430 A2 endpoint
- **Cosine similarity** retrieval → top-4 articles passed to Qwen3 as context
- **Automatic TF-IDF fallback** if embedding API unavailable — KB always works
- **Source attribution**: clickable article links displayed below every answer
- **Conversation memory**: last 16 turns sent with each query

### 3. Actions — Dynamic Multi-turn State Machine

All actions use a **dynamic multi-turn state machine** — parameters extracted from any message are retained throughout the session and never re-asked once provided. The number of follow-up turns automatically reduces based on how much information was given upfront.

**Track Transfer (1–2 turns)**
- Detects `TW-XXXXXX` reference inline → immediate DB lookup
- Shows: status, amount, rate, recipient, delivery date, troubleshooting tips
- If Delayed: suggests creating a support ticket
- If ID not found: clear error with format guidance

**Fee & Delivery Estimator (1–3 turns)**
- Extracts currencies and amounts from natural language in any order
- `"I want to send 500 CAD to USD, what's the fee?"` → immediate result (0 extra turns)
- Smart direction inference: if source currency already known, next currency = destination
- Rejects unsupported crypto (BTC/ETH) with immediate clear message
- Supports 13 currencies across 30+ pairs

**Create Support Ticket (1–3 turns)**
- Extracts transfer ID, priority, and email from any message automatically
- `"TW-001236 delayed 4 days, urgent, alice@example.com"` → ticket created immediately
- Only asks for missing parameters — distinguishes complaint intent from issue description
- Returns TKT-XXXXXX confirmation linked to transfer if mentioned

**Card Management (1–4 turns)**
- Detects mode from natural language: freeze / unfreeze / lost→replacement / order
- Email provided inline → skips email collection step
- Mode can be refined mid-flow (e.g. user says "freeze" then clarifies "actually it's lost")
- All operations read/write to persistent mock_db.json

### 4. Guardrails

**Prompt injection detection (25+ patterns):**
Covers direct override commands (`ignore instructions`, `forget training`, `disregard guidelines`), identity manipulation (`you are now`, `pretend to be`, `act as DAN/GPT`, `roleplay as`), capability unlocking (`unlock full capabilities`, `enable developer mode`, `remove restrictions`), system manipulation (`jailbreak`, `reveal system prompt`), and hypothetical framing bypass (`for a hypothetical scenario with no guidelines`, `if you had no restrictions`).

**Out-of-scope rejection (20+ patterns):**
Cryptocurrency (`what is Bitcoin`, `Ethereum price`) · geography & general knowledge · weather · sports results · cooking & recipes · entertainment · medical symptoms · coding help · translation requests

**Mid-action bypass:** Guardrail checks are skipped for mid-action inputs (emails, priorities, amounts) to prevent false positives on legitimate collected data.

### 5. Error Handling

| Scenario | Handling |
|---|---|
| Invalid transfer ID | Clear error: "No transfer found for TW-XXXXX" + format guidance |
| Unsupported currency / crypto | Lists supported currencies, rejects immediately |
| Invalid email | Re-prompts with example, stays on current step |
| Embedding API down | Automatic TF-IDF fallback — KB always available |
| Server error | Caught in try/except → user-friendly message |
| No frozen card to unfreeze | Informs user card is already active |
| Replacement already in progress | Shows existing reference ID |

---

## RAG Pipeline & Optimization

### Embedding Strategy

| Parameter | Value | Rationale |
|---|---|---|
| Embedding model | text-embedding-3-small (768-dim) | RSM 8430 A2 endpoint |
| Fallback | TF-IDF sparse vectors | Zero latency, no API dependency |
| Title boost | ×5 | Largest single accuracy gain (+40%) |
| Category boost | ×2 | Topic-level disambiguation |
| Content window | 800 chars | Avoids noise from long articles |
| Stop words | 50+ | Includes "wise" (inflates all scores equally) |
| Synonym expansion | 20 mappings | Covers Wise domain terms & currency codes |
| Top-K retrieved | 4 | Enough context, keeps prompt concise |
| Min score | 0.20 | Filters irrelevant results |

### Optimization Results (7 experiments)

| Configuration | Top-1 Accuracy | Top-4 Accuracy |
|---|---|---|
| Baseline (boost=1×, vocab=600) | 27% | 60% |
| After title boost (5×) | 67% | 87% |
| After vocab tuning (1,000 terms) | 73% | 87% |
| After synonym expansion | **73.3%** | **86.7%** |

### Neural Embedding Retrieval (25 test cases)

Evaluated using `data/eval_retrieval.py` with 768-dim neural embeddings:

| Category | Top-1 | Top-4 |
|---|---|---|
| Holding Money | 100% | 100% |
| Wise Business | 100% | 100% |
| Sending Money | 73% | 82% |
| Managing Account | 50% | 100% |
| Wise Card | 50% | 83% |
| Receiving Money | 0% | 100% |
| **Overall** | **64%** | **88%** |

> Note: 5 of the 9 Top-1 failures are duplicate articles (identical content published under two category IDs — e.g. WI271 and MA154 share the same freeze/unfreeze content). Excluding duplicates, functional Top-1 accuracy is **84%** and Top-4 is **100%**.

---

## Mock Database

| Table | Records | Key Scenarios |
|---|---|---|
| Users | 25 | Verified/unverified, 15 countries |
| Transfers | 60 | Completed (30), In Transit (15), Awaiting Funds (8), Delayed (6), Cancelled (1) |
| Tickets | 20 | Open (10), In Progress (5), Resolved (5) |
| Cards | 20 | Active (15), Frozen (2), Replacement Requested (2), Cancelled (1) |

**Test users:** alice@example.com · bob@example.com · carol@example.com · dave@example.com
**Test transfers:** TW-001234 (In Transit) · TW-001236 (Delayed) · TW-009999 (Delayed) · TW-005681 (Cancelled)

State persists across server restarts — freeze a card, restart the server, query again and it's still frozen. Reset with `git checkout data/mock_db.json`.

### Database Actions (16 total)

```
user.lookup
transfer.lookup / list / estimate / create / update_status
ticket.create / lookup / list / update
card.get / freeze / unfreeze / replacement / order
```

---

## Knowledge Base

| Topic | Articles |
|---|---|
| Sending Money | 96 |
| Managing Your Account | 79 |
| Wise Business | 72 |
| Wise Card | 66 |
| Holding Money | 48 |
| Receiving Money | 41 |
| **Total** | **402** |

### Re-scraping

```bash
pip install requests beautifulsoup4
cd data && python3 scraper.py
python3 embed_kb.py   # regenerate embeddings after KB update
```

---

## Evaluation

See `tests/test_cases.md` — **58 structured test cases** across 6 categories, **95% pass rate (55/58)**.
See `docs/rag_optimization_report.docx` — 7-experiment RAG optimization write-up.
See `docs/retrieval_accuracy_report.docx` — neural embedding retrieval evaluation report.

| Category | Cases | Pass | Rate |
|---|---|---|---|
| Knowledge Base Q&A | 15 | 14 | 93% |
| Intent Routing | 7 | 7 | 100% |
| Multi-turn Actions | 14 | 13 | 93% |
| Safety & Guardrails | 8 | 8 | 100% |
| Edge Cases & Error Handling | 6 | 6 | 100% |
| Multi-hop Knowledge Questions | 8 | 7 | 88% |
| **Total** | **58** | **55** | **95%** |

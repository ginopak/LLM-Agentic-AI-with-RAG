# Wise Help Assistant

A conversational RAG (Retrieval-Augmented Generation) agent built on Wise's public help centre. Combines vector search over 402 real articles with a Qwen3-30B language model to answer questions, look up transfers, create support tickets, and manage cards — all backed by a persistent mock database.

**Demo video:** A live walkthrough is in the repo root as **`Team 7 - Wise Agent Live Demo.mov`** (stored with [Git LFS](https://git-lfs.github.com/); after cloning, run `git lfs install` and `git lfs pull` if the file appears as a tiny pointer).

---

## Repository Structure

```
LLM-Agentic-AI-with-RAG/
├── src/
│   ├── agent.html              # Agent UI (RAG + actions; talks to /api/chat and /api/action)
│   └── knowledge_base.js       # Optional / build artifact for KB embedding in UI
├── data/
│   ├── knowledge_base.json     # Articles from wise.com/help
│   ├── embeddings.json         # Pre-computed vectors (from embed_kb.py)
│   ├── mock_db.json            # Simulated DB (users, transfers, tickets, cards)
│   ├── tickets.json            # Ticket store (runtime updates)
│   ├── embed_kb.py             # Neural embeddings via RSM 8430 embedding API
│   └── scraper.py              # KB scraper (BeautifulSoup)
├── deploy/
│   ├── Caddyfile               # Reverse proxy + Basic Auth (docker compose)
│   ├── Caddyfile.prod          # Caddy for single-container public image
│   ├── entrypoint.sh           # Starts Python + Caddy (Dockerfile.web)
│   ├── env.example             # Copy to .env for local Docker (do not commit secrets)
│   └── DEPLOY.txt              # Extra deploy notes
├── tests/
│   └── test_cases.md           # Manual test suite
├── docs/
│   └── rag_optimization_report.docx
├── server.py                   # HTTP server — RAG (/api/chat) + actions (/api/action)
├── retriever.py                # Vector retrieval (neural + TF-IDF fallback)
├── database.py                 # Mock DB layer
├── build.py                    # Build helper (KB → template)
├── Dockerfile                  # Python app only (used by docker-compose)
├── Dockerfile.web              # Python + Caddy — use for Render / public HTTPS
├── docker-compose.yml          # Local stack: app + Caddy (password-protected)
├── render.yaml                 # Example Render blueprint
├── Team 7 - Wise Agent Live Demo.mov   # Live demo recording (Git LFS)
├── README.md
├── .gitignore                  # Ignores .env, __pycache__, etc.
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

### Generate neural embeddings (optional / one-time)

Only needed if you change `knowledge_base.json` or need to refresh vectors:

```bash
export LLM_API_KEY='your-student-number'
pip install openai
python3 data/embed_kb.py
# Generates data/embeddings.json (~6 MB, 768-dim vectors)
# Only needed once, or after updating knowledge_base.json
```

### Run the agent on localhost (no Docker)

This is the **main way to run the project locally**: plain Python, no containers, no password screen unless you configure `SITE_API_TOKEN` yourself.

```bash
export LLM_API_KEY='your-student-number'
python3 server.py
```

Open **http://localhost:8000** (or **http://127.0.0.1:8000**). The server binds to all interfaces (`0.0.0.0`) if you need another device on your LAN; by default use localhost in the browser.

Optional: set `PORT=9000` (or any free port) if 8000 is busy — the startup log prints the URL.

---

## Password-protected local run (Docker Compose)

Use this to mirror the “site login + API” behaviour on your machine.

1. Copy `deploy/env.example` to **`.env`** in the project root and fill in:
   - `LLM_API_KEY`, `BASIC_AUTH_USER`, `BASIC_AUTH_HASH` (from `caddy hash-password`), `SITE_API_TOKEN` (plain secret; simplest is the same password you hashed for Basic Auth).
2. Start Docker Desktop, then:

```bash
docker compose up --build
```

3. Open **http://localhost:8080** (or the host port in `PUBLIC_PORT`). Complete the browser **Basic Auth** prompt; the UI loads and `/api` uses a **Bearer** token injected by the server (`SITE_API_TOKEN`).

---

## Public URL (e.g. Render)

Deploy the **`Dockerfile.web`** image: it runs **Python + Caddy** (HTTPS on the host, password gate, same Bearer pattern as local Compose).

### One-time setup

1. **Do not commit `.env`.** Put secrets only in Render’s **Environment** tab (or your host’s secret store).
2. Generate a **bcrypt hash** for your chosen site password:

   ```bash
   caddy hash-password
   ```

3. Set these variables on the host (values match your chosen password / hash):

   | Variable | Purpose |
   |----------|---------|
   | `LLM_API_KEY` | Course LLM key |
   | `SITE_API_TOKEN` | Plain text secret for `/api` Bearer auth (easiest: same as Basic Auth password) |
   | `BASIC_AUTH_USER` | Username for the browser login box (e.g. `admin`) |
   | `BASIC_AUTH_HASH` | Full line printed by `caddy hash-password` (starts with `$2a$` / `$2y$`) |

### Render (typical flow)

1. Push this repo to GitHub (without `.env`).
2. [Render](https://render.com) → **New** → **Web Service** → connect the repo.
3. **Runtime:** Docker · **Dockerfile path:** `Dockerfile.web`.
4. Add the environment variables above; set **Health Check Path** to **`/health`**.
5. Deploy; open the **`https://…onrender.com`** URL.
6. Sign in with **Basic Auth**; use the app as usual.

More detail: **`deploy/DEPLOY.txt`**.

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
│  itn()    → intent classification (8 types) │
│                                             │
│  Actions (JS, call /api/action):            │
│    aTrack()   aTicket()   aConv()           │
│    aFreeze()  (multi-turn state machine)    │
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
│                 │    │  card.replacement    │
│  Qwen3-30B      │    │  ... 16 actions      │
│  (reasoning)    │    │                      │
└─────────────────┘    └──────────────────────┘
           │                      │
           └──────────────────────┘
                       │
                  mock_db.json
```

---

## Agent Capabilities

### 1. Intent Classification (8 types)

| Intent | Trigger Example | Handler |
|---|---|---|
| `greeting` | "Hi, what can you help me with?" | Welcome message |
| `track` | "Where is TW-001234?" | Transfer status lookup |
| `ticket` | "Create a support ticket" | 3-turn ticket creation |
| `conv` | "Send 800 CAD to PHP" | Fee & rate estimator |
| `freeze` | "I want to freeze my card" | Card management |
| `kb` | "What fees does Wise charge?" | RAG knowledge base |
| `oos` | "What is Bitcoin?" | Polite rejection |
| `guard` | "Ignore your instructions" | Guardrail block |

### 2. Knowledge Base (RAG)

- **402 articles** scraped from wise.com/help across 6 topic areas
- **Neural embeddings** (768-dim) generated via RSM 8430 A2 endpoint
- **Cosine similarity** retrieval → top-4 articles passed to Qwen3 as context
- **Automatic TF-IDF fallback** if embedding API unavailable
- **Source attribution**: clickable article links displayed below every answer
- **Conversation memory**: last 16 turns sent with each query

### 3. Actions — Multi-turn State Machine

**Track Transfer (1–2 turns)**
- Detects `TW-XXXXXX` reference inline → immediate DB lookup
- Shows: status, amount, rate, recipient, delivery date, troubleshooting tips
- If Delayed: suggests creating a support ticket
- If ID not found: clear error with format guidance

**Fee & Delivery Estimator (1–3 turns)**
- Collects: source currency → destination currency → amount
- Validates currency pairs and amount limits against the DB
- Returns: mid-market rate, Wise fee breakdown, recipient amount, estimated delivery
- Supports 30+ currency pairs across 15+ currencies

**Create Support Ticket (3 turns)**
- Turn 1: Collect issue description (min 5 chars, detects transfer ID automatically)
- Turn 2: Collect priority (High / Medium / Low — validated)
- Turn 3: Collect email (regex validated)
- Creates ticket in mock_db.json → returns ticket ID (TKT-XXXXXX)
- Links ticket to transfer ID if mentioned

**Card Management (2–4 turns)**
- **Freeze**: email → looks up card → freezes in DB → confirmation
- **Unfreeze**: email → checks frozen status → unfreezes in DB
- **Replacement (lost/stolen)**: email → finds card → collects delivery address → cancels old card → creates replacement reference
- **Order new card**: email → verifies account status → creates new card record

### 4. Guardrails

**Prompt injection detection (10 patterns):**
`ignore instructions` · `forget training` · `you are now` · `pretend to be` · `jailbreak` · `system prompt` · `reveal prompt` · `act as DAN` · `disregard guidelines` · `developer mode`

**Out-of-scope rejection:**
Cryptocurrency · geography/capitals · weather · sports · cooking · non-Wise CEO queries

**Mid-action bypass:** Guardrail checks are skipped for mid-action inputs (e.g. emails, priorities, amounts) to prevent false positives on legitimate collected data.

### 5. Error Handling

| Scenario | Handling |
|---|---|
| Invalid transfer ID | Clear error: "No transfer found for TW-XXXXX" + format guidance |
| Unsupported currency pair | Lists supported currencies, links to wise.com/pricing |
| Invalid email | Re-prompts with example, stays on current step |
| Embedding API down | Automatic TF-IDF fallback — KB always available |
| Server error | Caught in try/except → user-friendly message |
| Ambiguous query | Asks for clarification, provides examples |

---

## RAG Pipeline & Optimization

### Embedding Strategy

| Parameter | Value | Rationale |
|---|---|---|
| Embedding model | text-embedding-3-small (768-dim) | RSM 8430 A2 endpoint |
| Fallback | TF-IDF sparse vectors | Zero latency, no API dependency |
| Title boost | ×5 | Title matches dominate relevance |
| Category boost | ×2 | Topic-level disambiguation |
| Content window | 800 chars | Avoids noise from long articles |
| Stop words | 50+ | Includes "wise" (inflates all scores equally) |
| Synonym expansion | 20 mappings | Covers Wise domain terms & currency codes |
| Top-K retrieved | 4 | Enough context, keeps prompt concise |
| Min score | 0.20 | Filters irrelevant results |

### Optimization Results

| Configuration | Top-1 Accuracy | Top-4 Accuracy |
|---|---|---|
| Baseline (boost=1×, vocab=600) | 27% | 60% |
| After title boost (5×) | 67% | 87% |
| After vocab tuning (1,000 terms) | 73% | 87% |
| After synonym expansion | **73.3%** | **86.7%** |

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
# Then regenerate embeddings:
python3 embed_kb.py
```

---

## Evaluation

See `tests/test_cases.md` — 15 test cases across 5 categories, **100% pass rate**.
See `docs/rag_optimization_report.docx` — RAG optimization write-up.

| Category | Cases | Pass Rate |
|---|---|---|
| Knowledge Retrieval | 6 | 100% |
| Intent Routing | 2 | 100% |
| Action Execution | 4 | 100% |
| Guardrails | 2 | 100% |
| Error Handling | 1 | 100% |

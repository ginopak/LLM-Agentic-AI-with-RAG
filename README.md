# Wise Help Assistant

A conversational RAG (Retrieval-Augmented Generation) agent built on Wise's public help centre. Combines vector search over 402 real articles with a Qwen3-30B language model to answer questions, look up transfers, create support tickets, and manage cards — all backed by a persistent mock database.

---

## Repository Structure

```
wise-help-assistant/
├── src/
│   └── agent.html              # Self-contained agent UI (835 KB)
├── data/
│   ├── knowledge_base.json     # 402 articles scraped from wise.com/help (1.2 MB)
│   ├── embeddings.json         # Pre-computed vector embeddings (run embed_kb.py to generate)
│   ├── mock_db.json            # Simulated database — 25 users, 60 transfers, 20 tickets, 20 cards
│   ├── embed_kb.py             # Generates neural embeddings via RSM 8430 A2 endpoint
│   └── scraper.py              # Web scraper (BeautifulSoup) used to build the KB
├── server.py                   # Local proxy server — RAG pipeline + database actions
├── retriever.py                # Vector retrieval module (neural + TF-IDF fallback)
├── database.py                 # Mock database layer — 16 CRUD actions
├── docs/
│   └── evaluation_report.docx # RAG optimization report + 15 test case results
├── tests/
│   └── test_cases.md           # Manual test suite (15 cases, 100% pass rate)
├── build.py                    # Build script (injects KB into agent template)
├── README.md
└── .gitignore
```

---

## Quick Start

### Prerequisites

- Python 3.8+
- RSM 8430 course API key (your student number)
- `openai` Python package: `pip install openai`

### Run the agent

```bash
# Mac / Linux
export LLM_API_KEY='your-student-number'
python3 server.py

# Windows
set LLM_API_KEY=your-student-number
python3 server.py
```

Then open **http://localhost:8000** in your browser.

### Generate neural embeddings (one-time setup)

```bash
export LLM_API_KEY='your-student-number'
python3 data/embed_kb.py
# Generates data/embeddings.json (~6 MB, 768-dim vectors)
# Only needed once, or after updating knowledge_base.json
```

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
See `docs/evaluation_report.docx` — full RAG optimization report with 7 experiments.

| Category | Cases | Pass Rate |
|---|---|---|
| Knowledge Retrieval | 6 | 100% |
| Intent Routing | 2 | 100% |
| Action Execution | 4 | 100% |
| Guardrails | 2 | 100% |
| Error Handling | 1 | 100% |

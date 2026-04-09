#!/usr/bin/env python3
"""
server.py — Wise Help Assistant Local Server
=============================================
Usage:
  export LLM_API_KEY='your-student-number'
  python3 server.py
  open http://localhost:8000

Endpoints:
  GET  /              → serves agent.html
  POST /api/chat      → RAG pipeline: retriever + Qwen3 LLM (kb intent)
  POST /api/action    → database actions (transfer/ticket/card)
"""

import http.server
import json
import os
import ssl
import urllib.request
import urllib.error
import socketserver
import sys
from pathlib import Path

# Import local modules
sys.path.insert(0, str(Path(__file__).parent))
from retriever import Retriever
import database as db

PORT            = 8000
LLM_API_KEY     = os.environ.get("LLM_API_KEY", "")
LLM_API_URL     = os.environ.get("LLM_API_URL", "https://rsm-8430-finalproject.bjlkeng.io/v1/chat/completions")
LLM_MODEL       = os.environ.get("LLM_MODEL", "qwen3-30b-a3b-fp8")
LLM_HTTP_TIMEOUT = int(os.environ.get("LLM_HTTP_TIMEOUT", "120"))
LLM_ENABLE_THINKING = os.environ.get("LLM_ENABLE_THINKING", "1").strip().lower() not in ("0","false","no")

BASE_DIR  = Path(__file__).parent
HTML_FILE = BASE_DIR / "src" / "agent.html"

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

# ── Load retriever once at startup ────────────────────────────────────────
print("Loading retriever...")
_retriever = Retriever()
print(f"Retriever ready — {len(_retriever._articles)} articles ({_retriever.embedding_type} embeddings)")


# ── LLM helpers ──────────────────────────────────────────────────────────

def _call_llm(messages: list, max_tokens: int = 1024) -> str:
    """Call the course LLM endpoint. Returns assistant text."""
    body = {
        "model": LLM_MODEL,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if LLM_ENABLE_THINKING:
        body["chat_template_kwargs"] = {"enable_thinking": True}

    req_data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        LLM_API_URL,
        data=req_data,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
            "User-Agent":    "WiseHelpAssistant/1.0",
            "Accept":        "application/json",
        },
        method="POST",
    )
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode    = ssl.CERT_NONE

    with urllib.request.urlopen(req, timeout=LLM_HTTP_TIMEOUT, context=ssl_ctx) as resp:
        data = json.loads(resp.read().decode())

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Empty choices from LLM")
    msg = choices[0].get("message") or {}
    content = msg.get("content", "")
    if isinstance(content, list):
        content = "".join(b.get("text","") for b in content if isinstance(b,dict))
    return content.strip()


def _to_anthropic_shape(text: str) -> dict:
    """Wrap text in Anthropic-style response so agent.html can parse it."""
    return {"content": [{"type": "text", "text": text}]}


# ── RAG: KB query handler ─────────────────────────────────────────────────

def handle_kb_query(payload: dict) -> dict:
    """
    Full RAG pipeline for kb intent queries.
    1. Extract user query from conversation history
    2. Run retriever (vector search)
    3. Build augmented system prompt with retrieved articles
    4. Call Qwen3
    5. Return Anthropic-shaped response
    """
    # Get the latest user message
    messages_raw = payload.get("messages", [])
    user_query = ""
    for m in reversed(messages_raw):
        if m.get("role") == "user":
            user_query = m.get("content", "")
            break

    # Retrieve relevant articles
    # Retrieval: try neural (embedding API) first, fallback to TF-IDF
    EMB_KEY = os.environ.get("EMB_API_KEY", LLM_API_KEY)
    try:
        result = _retriever.retrieve_with_key(user_query, EMB_KEY, top_k=4)
    except Exception as emb_err:
        print(f"  Embedding failed ({emb_err}), using TF-IDF fallback")
        result = _retriever.retrieve(user_query, top_k=4)

    if result.status == "guard":
        return _to_anthropic_shape(
            "<p>I cannot process that request. I answer questions about Wise products only.</p>"
        )
    if result.status == "oos":
        return _to_anthropic_shape(
            "<p>That topic is outside my scope. I specialise in Wise — transfers, fees, "
            "cards, verification, and account management. What can I help you with?</p>"
        )

    # Build RAG system prompt
    if result.status in ("ok", "ambiguous") and result.results:
        context = _retriever.format_context(result.results)
        citations = _retriever.format_citations(result.results)
        citation_links = "".join(
            f'<a href="{c["url"]}" target="_blank" style="display:inline-flex;align-items:center;'
            f'gap:3px;background:#E0FAF7;color:#009B89;border-radius:4px;padding:2px 8px;'
            f'font-size:11px;font-weight:500;margin:2px;text-decoration:none;border:1px solid #b2e8e2">'
            f'&#128196; {c["title"]}</a>'
            for c in citations
        )
        source_html = f'<div style="display:flex;flex-wrap:wrap;margin-top:8px;gap:3px">{citation_links}</div>'

        system_prompt = (
            "You are the Wise Help Assistant — an expert on Wise (wise.com) products.\n"
            "Answer questions using ONLY the knowledge base articles provided below.\n\n"
            "FORMATTING RULES (strictly follow these):\n"
            "1. Output clean HTML only — no Markdown asterisks, no # headings, no bullet dashes.\n"
            "2. Use <p> for paragraphs, <strong> for key terms.\n"
            "3. For lists: use <ul><li> for items. For nested categories, use:\n"
            "   <p><strong>Category name:</strong></p><ul><li>item 1</li><li>item 2</li></ul>\n"
            "4. For step-by-step instructions: use <ol><li>Step 1</li><li>Step 2</li></ol>.\n"
            "5. Always end with: <p><em>Source: [article title]</em></p>\n"
            "6. If not in the articles, say so and direct to wise.com/help.\n"
            "7. Keep answers 100-250 words. Never invent information.\n"
            "8. For fees/rates/limits: note these may change and user should check wise.com.\n"
            "9. Use conversation history for context (follow-up questions, pronouns).\n\n"
            f"KNOWLEDGE BASE:\n{context}"
        )
    else:
        # No relevant articles found
        system_prompt = (
            "You are the Wise Help Assistant. "
            "The knowledge base does not contain a relevant article for this query. "
            "Politely tell the user you couldn't find specific information and "
            "direct them to wise.com/help. Keep it brief (2-3 sentences)."
        )
        source_html = ""

    # Build messages for LLM (with full conversation history for memory)
    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in messages_raw:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            llm_messages.append({"role": role, "content": content})

    answer = _call_llm(llm_messages)
    return _to_anthropic_shape(answer + source_html)


# ── Action handler ────────────────────────────────────────────────────────

def handle_action(payload: dict) -> dict:
    """
    Route action requests to database.py functions.
    payload: { "action": str, "params": dict }

    Supported actions:
      user.lookup
      transfer.lookup, transfer.list, transfer.estimate, transfer.create, transfer.update_status
      ticket.create, ticket.lookup, ticket.list, ticket.update
      card.get, card.freeze, card.unfreeze, card.replacement, card.order
    """
    action = payload.get("action", "")
    p      = payload.get("params", {})

    # ── User ──
    if action == "user.lookup":
        return db.lookup_user(p.get("email",""))

    # ── Transfer ──
    if action == "transfer.lookup":
        return db.lookup_transfer(p.get("transfer_id",""))

    if action == "transfer.list":
        return db.list_transfers(p.get("user_email",""), p.get("status"))

    if action == "transfer.estimate":
        return db.estimate_transfer(
            p.get("from_currency",""), p.get("to_currency",""),
            float(p.get("amount",0))
        )

    if action == "transfer.create":
        return db.create_transfer(p)

    if action == "transfer.update_status":
        return db.update_transfer_status(
            p.get("transfer_id",""), p.get("status",""), p.get("note","")
        )

    # ── Ticket ──
    if action == "ticket.create":
        return db.create_ticket(
            user_email=p.get("user_email",""),
            issue=p.get("issue",""),
            priority=p.get("priority","Medium"),
            related_transfer_id=p.get("related_transfer_id"),
        )

    if action == "ticket.lookup":
        return db.lookup_ticket(p.get("ticket_id",""))

    if action == "ticket.list":
        return db.list_tickets(p.get("user_email",""))

    if action == "ticket.update":
        return db.update_ticket(p.get("ticket_id",""), p)

    # ── Card ──
    if action == "card.get":
        return db.get_card(p.get("user_email",""))

    if action == "card.freeze":
        return db.freeze_card(p.get("user_email",""), p.get("last_four"))

    if action == "card.unfreeze":
        return db.unfreeze_card(p.get("user_email",""), p.get("last_four"))

    if action == "card.replacement":
        return db.request_replacement(
            user_email=p.get("user_email",""),
            reason=p.get("reason","lost"),
            delivery_address=p.get("delivery_address",""),
            last_four=p.get("last_four"),
        )

    if action == "card.order":
        return db.order_new_card(
            user_email=p.get("user_email",""),
            card_type=p.get("card_type","Physical"),
            delivery_address=p.get("delivery_address",""),
        )

    return {"error": f"Unknown action: '{action}'"}

    # ── Transfer actions ──
    if action == "transfer.lookup":
        return db.lookup_transfer(params.get("transfer_id", ""))

    if action == "transfer.estimate":
        return db.estimate_transfer(
            params.get("from_currency", ""),
            params.get("to_currency", ""),
            float(params.get("amount", 0)),
        )

    if action == "transfer.create":
        return db.create_transfer(params)

    # ── Ticket actions ──
    if action == "ticket.create":
        return db.create_ticket(
            user_email=params.get("user_email", ""),
            issue=params.get("issue", ""),
            priority=params.get("priority", "Medium"),
            related_transfer_id=params.get("related_transfer_id"),
        )

    if action == "ticket.update":
        return db.update_ticket(params.get("ticket_id", ""), params)

    if action == "ticket.lookup":
        return db.lookup_ticket(params.get("ticket_id", ""))

    # ── Card actions ──
    if action == "card.status":
        return db.get_card(params.get("user_email", ""))

    if action == "card.freeze":
        return db.freeze_card(
            params.get("user_email", ""),
            params.get("last_four"),
        )

    if action == "card.unfreeze":
        return db.unfreeze_card(
            params.get("user_email", ""),
            params.get("last_four"),
        )

    if action == "card.replacement":
        return db.request_replacement(
            user_email=params.get("user_email", ""),
            reason=params.get("reason", "lost"),
            delivery_address=params.get("delivery_address", ""),
            card_last_four=params.get("last_four"),
        )

    return {"error": f"Unknown action: '{action}'"}


# ── HTTP Handler ──────────────────────────────────────────────────────────

class WiseAgentHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR / "src"), **kwargs)

    def log_message(self, format, *args):
        print(f"  [{self.address_string()}] {format % args}")

    def send_cors_headers(self):
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/agent.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/chat":
            self._handle_chat()
        elif self.path == "/api/action":
            self._handle_action()
        else:
            self.send_error(404)

    def _read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_chat(self):
        try:
            payload = self._read_payload()
            if not LLM_API_KEY:
                self._send_json({"error": {"message": "LLM_API_KEY not set."}}, 500)
                return
            result = handle_kb_query(payload)
            self._send_json(result)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            print(f"  LLM error {e.code}: {err[:200]}")
            self._send_json({"error": {"message": f"LLM error: {err[:200]}"}}, e.code)
        except Exception as e:
            print(f"  Server error: {e}")
            self._send_json({"error": {"message": str(e)}}, 500)

    def _handle_action(self):
        try:
            payload  = self._read_payload()
            result   = handle_action(payload)
            self._send_json(result)
        except Exception as e:
            print(f"  Action error: {e}")
            self._send_json({"error": str(e)}, 500)


def main():
    if not LLM_API_KEY:
        print("Warning: LLM_API_KEY not set.")
        print("  Set with: export LLM_API_KEY='your-student-number'")
    else:
        print(f"LLM API key loaded (...{LLM_API_KEY[-4:]})")

    if not HTML_FILE.exists():
        print(f"Error: Cannot find {HTML_FILE}")
        sys.exit(1)

    print(f"Agent: {HTML_FILE} ({HTML_FILE.stat().st_size // 1024} KB)")
    print()
    print("Starting Wise Help Assistant...")
    print(f"  http://localhost:{PORT}")
    print("  Ctrl+C to stop")
    print()

    with socketserver.TCPServer(("", PORT), WiseAgentHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Build script for Wise Help Assistant
=====================================
Reads knowledge_base.json + embeddings.json and injects both into
src/agent.html to produce a self-contained dist/wise_agent.html.

Usage:
    # 1. Generate embeddings first (only needed once, or after KB update)
    python3 data/embed_kb.py

    # 2. Build the agent
    python3 build.py

Output:
    dist/wise_agent.html
"""

import json, os
from datetime import datetime

SRC_HTML      = os.path.join("src", "agent.html")
KB_JSON       = os.path.join("data", "knowledge_base.json")
EMB_JSON      = os.path.join("data", "embeddings.json")
OUT_DIR       = "dist"
OUT_HTML      = os.path.join(OUT_DIR, "wise_agent.html")
CONTENT_CHARS = 1200


def build():
    print("=" * 55)
    print("  Wise Help Assistant — Build Script")
    print("=" * 55)

    # Load KB
    print(f"\n[1/4] Loading {KB_JSON}...")
    with open(KB_JSON, encoding="utf-8") as f:
        articles = json.load(f)
    from collections import Counter
    cats = Counter(a["category"] for a in articles)
    print(f"      {len(articles)} articles:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"        • {cat}: {count}")

    # Compress KB
    print(f"\n[2/4] Compressing KB (content capped at {CONTENT_CHARS} chars)...")
    compressed = [{"id": a["id"], "t": a["title"], "c": a["category"],
                   "u": a["url"], "x": a["content"][:CONTENT_CHARS]}
                  for a in articles]
    kb_js = json.dumps(compressed, ensure_ascii=False, separators=(",", ":"))
    print(f"      KB size: {len(kb_js)/1024:.1f} KB")

    # Load embeddings
    print(f"\n[3/4] Loading {EMB_JSON}...")
    if not os.path.exists(EMB_JSON):
        print(f"      ERROR: {EMB_JSON} not found.")
        print(f"      Run first: python3 data/embed_kb.py")
        return False
    with open(EMB_JSON, encoding="utf-8") as f:
        emb = json.load(f)
    emb_js = json.dumps(emb, separators=(",", ":"))
    print(f"      {emb['n_docs']} doc vectors, vocab {emb['vocab_size']} terms")
    print(f"      Embeddings size: {len(emb_js)/1024:.1f} KB")

    # Inject into template
    print(f"\n[4/4] Building {OUT_HTML}...")
    with open(SRC_HTML, encoding="utf-8") as f:
        html = f.read()

    if "%%KBJSON%%" not in html:
        print("ERROR: %%KBJSON%% placeholder not found in src/agent.html")
        return False
    if "%%EMBSJSON%%" not in html:
        print("ERROR: %%EMBSJSON%% placeholder not found in src/agent.html")
        return False

    html = html.replace("%%KBJSON%%", kb_js).replace("%%EMBSJSON%%", emb_js)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUT_HTML) / 1024
    print(f"      Output: {OUT_HTML} ({size_kb:.1f} KB)")
    print(f"\n{'='*55}")
    print(f"  Build complete! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n  To run:")
    print(f"    export LLM_API_KEY='your-student-number'")
    print(f"    python3 server.py")
    print(f"    open http://localhost:8000")
    print(f"{'='*55}\n")
    return True


if __name__ == "__main__":
    exit(0 if build() else 1)

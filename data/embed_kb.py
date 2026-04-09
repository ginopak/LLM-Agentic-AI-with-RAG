#!/usr/bin/env python3
"""
embed_kb.py — Neural Embedding Generator for Wise Help Assistant
=================================================================
Uses the OpenAI client (same pattern as Lab 2) to call the RSM 8430
embedding API and generate dense vector embeddings for all 402 articles.

Usage:
    pip install openai
    export LLM_API_KEY='your-student-number'
    python3 data/embed_kb.py

    # Or pass key directly:
    python3 data/embed_kb.py 1012838770

Output:
    data/embeddings.json   (~3 MB, 1536-dim neural vectors)
"""

import json, math, os, sys, time
from datetime import datetime

KB_PATH   = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
OUT_PATH  = os.path.join(os.path.dirname(__file__), "embeddings.json")

EMB_BASE_URL = "https://rsm-8430-a2.bjlkeng.io"
EMB_MODEL    = "text-embedding-3-small"
BATCH_SIZE   = 20    # articles per API call
RETRY_MAX    = 3
RETRY_WAIT   = 5


def get_client(api_key: str):
    """Create OpenAI client pointing to the course embedding endpoint."""
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ openai package not found. Install it:")
        print("   pip install openai")
        sys.exit(1)

    return OpenAI(
        api_key=api_key,
        base_url=f"{EMB_BASE_URL}/v1",
    )


def embed_batch(client, texts: list) -> list:
    """Embed a batch of texts. Returns list of normalised vectors."""
    for attempt in range(1, RETRY_MAX + 1):
        try:
            response = client.embeddings.create(
                model=EMB_MODEL,
                input=texts,
            )
            # Sort by index to preserve order
            items = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in items]
        except Exception as e:
            print(f"    Error (attempt {attempt}/{RETRY_MAX}): {e}")
            if attempt < RETRY_MAX:
                time.sleep(RETRY_WAIT * attempt)
    raise RuntimeError(f"Embedding API failed after {RETRY_MAX} attempts.")


def norm(vec: list) -> list:
    """L2-normalise so cosine similarity = dot product."""
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec] if n > 0 else vec


def build_text(article: dict) -> str:
    """Title × 2 + category + first 800 chars of content."""
    return (
        article["title"] + ". " +
        article["title"] + ". " +
        article.get("category", "") + ". " +
        article["content"][:800]
    )


def main():
    # ── Get API key ────────────────────────────────────────────────────────
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1].strip()
    if not api_key:
        print("Error: provide your student number as LLM_API_KEY or first argument.")
        print("  export LLM_API_KEY='1012838770'  && python3 data/embed_kb.py")
        print("  python3 data/embed_kb.py 1012838770")
        sys.exit(1)

    print("=" * 60)
    print("  Wise Help Assistant — Neural Embedding Generator")
    print("=" * 60)
    print(f"  Endpoint: {EMB_BASE_URL}")
    print(f"  Model:    {EMB_MODEL}")
    print(f"  Key:      ...{api_key[-4:]}")
    print()

    # ── Create client (same pattern as Lab 2) ──────────────────────────────
    client = get_client(api_key)

    # ── Test connection ────────────────────────────────────────────────────
    print("Testing API connection...")
    try:
        test = embed_batch(client, ["connection test"])
        print(f"✅ Connected! Dimensions: {len(test[0])}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # ── Load KB ───────────────────────────────────────────────────────────
    print(f"\n[1/3] Loading {KB_PATH}...")
    with open(KB_PATH, encoding="utf-8") as f:
        articles = json.load(f)
    print(f"      {len(articles)} articles loaded")

    # ── Embed in batches ──────────────────────────────────────────────────
    texts    = [build_text(a) for a in articles]
    all_vecs = []
    n_batches = math.ceil(len(texts) / BATCH_SIZE)
    print(f"\n[2/3] Embedding {len(articles)} articles ({n_batches} batches of {BATCH_SIZE})...")

    for i in range(0, len(texts), BATCH_SIZE):
        batch   = texts[i: i + BATCH_SIZE]
        batch_n = i // BATCH_SIZE + 1
        print(f"  Batch {batch_n}/{n_batches}  (articles {i+1}–{min(i+len(batch), len(texts))})", end="", flush=True)
        vecs = embed_batch(client, batch)
        all_vecs.extend([norm(v) for v in vecs])
        print("  ✓")
        time.sleep(0.2)   # be polite

    dims = len(all_vecs[0])
    print(f"\n      Done — {len(all_vecs)} vectors, {dims} dimensions each")

    # ── Save ──────────────────────────────────────────────────────────────
    print(f"\n[3/3] Saving to {OUT_PATH}...")
    output = {
        "generated":  datetime.now().isoformat(),
        "model":      EMB_MODEL,
        "dimensions": dims,
        "n_docs":     len(articles),
        "type":       "neural",
        "docs": [
            {"id": articles[i]["id"], "vec": all_vecs[i]}
            for i in range(len(articles))
        ]
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_PATH) / 1024 / 1024
    print(f"      Saved — {size_mb:.1f} MB")
    print(f"\n{'='*60}")
    print(f"  Done! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {len(articles)} articles × {dims} dims → {size_mb:.1f} MB")
    print(f"\n  Next: python3 server.py")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

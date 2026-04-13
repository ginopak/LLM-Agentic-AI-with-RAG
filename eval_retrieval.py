#!/usr/bin/env python3
"""
eval_retrieval.py — RAG Retrieval Accuracy Evaluation
======================================================
Evaluates Top-1 and Top-4 retrieval accuracy for the Wise Help Assistant.

Usage:
    python3 eval_retrieval.py                    # run all 25 test cases
    python3 eval_retrieval.py --json             # output raw JSON results
    python3 eval_retrieval.py --category card    # filter by category

Output: prints a detailed report; pass --json to get machine-readable output.
"""

import sys, os, json, math, time, argparse
sys.path.insert(0, os.path.dirname(__file__))

from retriever import Retriever

# ── Test cases ─────────────────────────────────────────────────────────────
# Each entry: (query, expected_article_id, category, difficulty)
# Difficulty: easy (direct keyword match) | medium | hard (semantic, no keywords)
EVAL = [
    # ── Sending Money ──────────────────────────────────────────────────────
    ("What fees apply when sending money abroad?",
     "SE090", "Sending Money", "easy"),

    ("How long does a transfer to the Philippines take?",
     "SE002", "Sending Money", "medium"),

    ("How do I cancel my transfer?",
     "SE022", "Sending Money", "easy"),

    ("What is the mid-market exchange rate and how do live rate transfers work?",
     "SE093", "Sending Money", "medium"),

    ("My transfer is delayed, how long will the additional checks take?",
     "SE067", "Sending Money", "hard"),

    ("How do I send money with Wise?",
     "SE001", "Sending Money", "easy"),

    ("Are there limits on how much I can send with Wise?",
     "SE074", "Sending Money", "easy"),

    ("I entered the wrong bank details for my recipient, what should I do?",
     "SE087", "Sending Money", "hard"),

    ("How can I check my transfer status?",
     "SE010", "Sending Money", "easy"),

    ("I want to send the exact amount that my recipient will receive",
     "SE003", "Sending Money", "medium"),

    # ── Managing Your Account ──────────────────────────────────────────────
    ("Why do I need to verify my identity with Wise?",
     "MA101", "Managing Account", "easy"),

    ("What documents do I need to get verified on Wise?",
     "MA100", "Managing Account", "medium"),

    # ── Wise Card ─────────────────────────────────────────────────────────
    ("How do I freeze or unfreeze my Wise card?",
     "WI271", "Wise Card", "easy"),

    ("My card was lost or stolen, what should I do?",
     "WI270", "Wise Card", "easy"),

    ("What are the spending limits on my Wise card?",
     "WI232", "Wise Card", "easy"),

    ("What fees does the Wise card charge?",
     "WI230", "Wise Card", "easy"),

    ("How do I get started with the Wise card?",
     "WI224", "Wise Card", "medium"),

    # ── Receiving Money ────────────────────────────────────────────────────
    ("How do I receive money from PayPal into Wise?",
     "RE326", "Receiving Money", "medium"),

    ("How do I open account details to receive money?",
     "RE291", "Receiving Money", "easy"),

    # ── Holding Money ─────────────────────────────────────────────────────
    ("What are Wise Jars and how do they work?",
     "HO181", "Holding Money", "easy"),

    ("How can I convert money between currencies in my Wise account?",
     "HO179", "Holding Money", "medium"),

    # ── Wise Business ─────────────────────────────────────────────────────
    ("How does Wise verify my business?",
     "WI351", "Wise Business", "easy"),

    ("What are the fees for using Wise Business?",
     "WI333", "Wise Business", "easy"),

    # ── Hard / Semantic ────────────────────────────────────────────────────
    ("My recipient says they haven't received the money yet",
     "SE067", "Sending Money", "hard"),

    ("I can't find my Wise card and I'm worried someone might use it",
     "WI270", "Wise Card", "hard"),
]


def run_eval(retriever, top_k=4):
    results = []
    for idx, (query, expected_id, category, difficulty) in enumerate(EVAL, 1):
        print(f"  [{idx}/{len(EVAL)}] {query[:60]}...", flush=True)
        t0 = time.time()
        hits = retriever.query(query, top_k=top_k)
        elapsed = time.time() - t0

        ids    = [h["id"] for h in hits]
        top1   = hits[0]["id"] if hits else None
        score1 = hits[0]["score"] if hits else 0.0

        in_top1 = (top1 == expected_id)
        in_topk = (expected_id in ids)

        results.append({
            "query":       query,
            "expected":    expected_id,
            "category":    category,
            "difficulty":  difficulty,
            "top1_id":     top1,
            "top1_title":  hits[0]["title"][:55] if hits else "—",
            "top1_score":  round(score1, 4),
            "in_top1":     in_top1,
            "in_topk":     in_topk,
            "retrieved":   ids,
            "latency_ms":  round(elapsed * 1000, 1),
        })
    return results


def print_report(results, top_k=4):
    n = len(results)
    t1  = sum(1 for r in results if r["in_top1"])
    t4  = sum(1 for r in results if r["in_topk"])
    avg_lat = sum(r["latency_ms"] for r in results) / n

    # Per-category
    from collections import defaultdict
    cat_stats = defaultdict(lambda: {"t1":0,"tk":0,"n":0})
    for r in results:
        c = r["category"]
        cat_stats[c]["n"]  += 1
        cat_stats[c]["t1"] += int(r["in_top1"])
        cat_stats[c]["tk"] += int(r["in_topk"])

    # Per-difficulty
    diff_stats = defaultdict(lambda: {"t1":0,"tk":0,"n":0})
    for r in results:
        d = r["difficulty"]
        diff_stats[d]["n"]  += 1
        diff_stats[d]["t1"] += int(r["in_top1"])
        diff_stats[d]["tk"] += int(r["in_topk"])

    W = 100
    print("=" * W)
    print("  WISE HELP ASSISTANT — RAG RETRIEVAL ACCURACY EVALUATION")
    print("=" * W)
    print(f"  Test cases : {n}")
    print(f"  Top-K      : {top_k}")
    print(f"  Avg latency: {avg_lat:.1f} ms")
    print()

    # Per-case table
    print(f"  {'#':<3} {'Category':<18} {'Diff':<7} {'Expected':<8} "
          f"{'Top-1 Result':<58} {'Score':<7} {'T1':<4} {'T{k}'.replace('{k}', str(top_k))}")
    print(f"  {'-'*3} {'-'*18} {'-'*7} {'-'*8} {'-'*58} {'-'*7} {'-'*4} {'-'*4}")

    for i, r in enumerate(results, 1):
        mark1 = "✅" if r["in_top1"] else ("⚠️ " if r["in_topk"] else "❌")
        markk = "✅" if r["in_topk"] else "❌"
        top1_str = f"[{r['top1_id']}] {r['top1_title']}"
        print(f"  {i:<3} {r['category']:<18} {r['difficulty']:<7} {r['expected']:<8} "
              f"{top1_str:<58} {r['top1_score']:<7.3f} {mark1:<4} {markk}")

    # Summary
    print()
    print("  OVERALL RESULTS")
    print(f"  {'─'*40}")
    print(f"  Top-1 Accuracy : {t1}/{n} = {t1/n*100:.1f}%")
    print(f"  Top-{top_k} Accuracy : {t4}/{n} = {t4/n*100:.1f}%")
    print(f"  {'─'*40}")

    # By category
    print()
    print("  BY CATEGORY")
    print(f"  {'Category':<22} {'Top-1':>8} {'Top-'+str(top_k):>8} {'Cases':>7}")
    print(f"  {'─'*22} {'─'*8} {'─'*8} {'─'*7}")
    for cat in sorted(cat_stats):
        s = cat_stats[cat]
        print(f"  {cat:<22} {s['t1']}/{s['n']} ({s['t1']/s['n']*100:4.0f}%)  "
              f"{s['tk']}/{s['n']} ({s['tk']/s['n']*100:4.0f}%)  {s['n']:>5}")

    # By difficulty
    print()
    print("  BY DIFFICULTY")
    print(f"  {'Difficulty':<12} {'Top-1':>8} {'Top-'+str(top_k):>8} {'Cases':>7}")
    print(f"  {'─'*12} {'─'*8} {'─'*8} {'─'*7}")
    for diff in ["easy","medium","hard"]:
        if diff in diff_stats:
            s = diff_stats[diff]
            print(f"  {diff:<12} {s['t1']}/{s['n']} ({s['t1']/s['n']*100:4.0f}%)  "
                  f"{s['tk']}/{s['n']} ({s['tk']/s['n']*100:4.0f}%)  {s['n']:>5}")

    # Failures
    failures = [r for r in results if not r["in_top1"]]
    if failures:
        print()
        print("  FAILURES (not in Top-1)")
        print(f"  {'─'*90}")
        for r in failures:
            status = "⚠️  in Top-K" if r["in_topk"] else "❌ not found"
            print(f"  [{status}] Expected {r['expected']}")
            print(f"    Query   : {r['query']}")
            print(f"    Got     : [{r['top1_id']}] {r['top1_title']} (score {r['top1_score']:.3f})")
            print()

    print("=" * W)
    print()


def main():
    parser = argparse.ArgumentParser(description="RAG retrieval accuracy eval")
    parser.add_argument("--json",     action="store_true", help="Output raw JSON")
    parser.add_argument("--topk",     type=int, default=4, help="Top-K (default 4)")
    parser.add_argument("--category", type=str, default="",  help="Filter by category keyword")
    args = parser.parse_args()

    print("Loading retriever...", flush=True)
    r = Retriever()
    print(f"Ready — {len(r._articles)} articles ({r.embedding_type} embeddings)\n", flush=True)

    eval_cases = EVAL
    if args.category:
        eval_cases = [(q,e,c,d) for q,e,c,d in EVAL if args.category.lower() in c.lower()]
        print(f"Filtered to {len(eval_cases)} cases matching '{args.category}'\n")

    results = run_eval(r, top_k=args.topk)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_report(results, top_k=args.topk)


if __name__ == "__main__":
    main()

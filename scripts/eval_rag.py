"""Step 5 - evaluate the RAG retriever with questions whose correct source document is known.

Metrics: hit@1 / hit@3 / hit@5 and MRR (document level), per question type,
plus an abstention test using out-of-scope questions (should refuse) and in-scope questions (should answer).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import RAG_EVAL_PATH, SEED  # noqa: E402
from app.rag import ABSTAIN_THRESHOLD, RagIndex  # noqa: E402

OUT_OF_SCOPE = [
    "What is the capital of France?", "How do I bake sourdough bread?", "Who won the football world cup?",
    "Explain how photosynthesis works", "What is the best programming language to learn?",
    "How tall is Mount Everest?", "Write a poem about the ocean", "What is the boiling point of water?",
    "Recommend a good laptop for gaming", "Who painted the Mona Lisa?",
]


def main():
    idx = RagIndex()
    rng = np.random.default_rng(SEED)
    qs = []
    docs = idx.manifest
    leases = [d for d in docs if d["doc_type"] == "Lease abstract"]
    markets = [d for d in docs if d["doc_type"] == "Market report"]
    props = [d for d in docs if d["doc_type"] == "Property report"]

    for d in rng.choice(leases, size=30, replace=False):
        t = ["What renewal option does {tenant} have at {property} in {market}?",
             "How much annual rent escalation applies to the {tenant} lease at {property}, {market}?",
             "When does the lease for {tenant} at {property} expire?"][int(rng.integers(0, 3))]
        qs.append(("lease", t.format(**d), d["doc_id"]))
    for d in markets:
        t = ["What is the vacancy rate in the {market} market?", "What is the average asking rent in {market}?",
             "What is driving leasing demand in {market}?"][int(rng.integers(0, 3))]
        qs.append(("market", t.format(**d), d["doc_id"]))
    for d in props:
        t = ["How much space expires within 24 months at {property} in {market}?",
             "How does the rent at {property} in {market} compare with the market median?"][int(rng.integers(0, 2))]
        qs.append(("property", t.format(**d), d["doc_id"]))

    ranks, by_type = [], {}
    wrong_abstain = 0
    failures = []
    for typ, q, gold in qs:
        hits = idx.search(q, 10)
        docs_ranked = []
        for h in hits:
            if h["doc_id"] not in docs_ranked:
                docs_ranked.append(h["doc_id"])
        r = docs_ranked.index(gold) + 1 if gold in docs_ranked else None
        ranks.append(r)
        by_type.setdefault(typ, []).append(r)
        if hits[0]["score"] < ABSTAIN_THRESHOLD:
            wrong_abstain += 1
        if r is None or r > 1:
            failures.append({"type": typ, "question": q, "expected": gold, "got": docs_ranked[:3], "rank": r})

    def summ(rs):
        a = np.array([r if r else 0 for r in rs])
        return {"n": len(rs), "hit@1": float(np.mean((a == 1))), "hit@3": float(np.mean((a >= 1) & (a <= 3))),
                "hit@5": float(np.mean((a >= 1) & (a <= 5))), "mrr": float(np.mean([1 / r if r else 0 for r in rs]))}

    refused = sum(1 for q in OUT_OF_SCOPE if idx.search(q, 1)[0]["score"] < ABSTAIN_THRESHOLD)
    out = {"overall": summ(ranks), "by_type": {k: summ(v) for k, v in by_type.items()},
           "abstention": {"threshold": ABSTAIN_THRESHOLD, "out_of_scope_n": len(OUT_OF_SCOPE), "out_of_scope_refused": refused,
                          "in_scope_n": len(qs), "in_scope_wrongly_refused": wrong_abstain},
           "n_documents": len(docs), "n_chunks": len(idx.chunks), "failures": failures[:8],
           "method": "TF-IDF (1-2 grams) retrieval over section-level chunks; questions generated from templates with a known gold document.",
           "caveat": ("Templated questions name the tenant/property/market explicitly, so keyword retrieval finds them easily; near-perfect scores "
                      "are an upper bound. Paraphrased or multi-document questions (e.g. 'which leases expire soonest?') will score lower and "
                      "would need embeddings, a re-ranker and a hand-written question set to measure properly.")}
    RAG_EVAL_PATH.write_text(json.dumps(out, indent=1))
    o = out["overall"]
    print(f"[rag] {len(qs)} questions | hit@1={o['hit@1']:.2f} hit@3={o['hit@3']:.2f} hit@5={o['hit@5']:.2f} MRR={o['mrr']:.2f} "
          f"| refused {refused}/{len(OUT_OF_SCOPE)} out-of-scope, wrongly refused {wrong_abstain}/{len(qs)} in-scope | chunks={len(idx.chunks)}")


if __name__ == "__main__":
    main()

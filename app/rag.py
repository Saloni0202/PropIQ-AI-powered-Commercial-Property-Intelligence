"""Retrieval-augmented question answering over lease abstracts, market reports and property reports.

Retrieval : TF-IDF (1-2 grams, sublinear tf) + cosine similarity  -> dependency-light, deterministic, fast.
            (Swap `RagIndex._vectorise` for sentence-transformers / an embedding API for semantic search.)
Generation: 1) extractive answer built from the best-matching sentences (always available), or
            2) an LLM answer grounded ONLY in the retrieved chunks, if ANTHROPIC_API_KEY is set.
Safety    : abstains when the best retrieval score is below a threshold (no evidence -> no answer).
"""
import json
import math
import os
import re

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from .config import DOCS_DIR, DOCS_MANIFEST_PATH

ABSTAIN_THRESHOLD = 0.12
TOKEN = re.compile(r"[a-z0-9$%.]+")


class RagIndex:
    def __init__(self):
        self.manifest = json.loads(DOCS_MANIFEST_PATH.read_text())
        self.docs = {m["doc_id"]: m for m in self.manifest}
        self.chunks = []
        for m in self.manifest:
            text = (DOCS_DIR / m["file"]).read_text(encoding="utf-8")
            parts = re.split(r"^## ", text, flags=re.M)
            header = parts[0].strip()
            title = header.split("\n")[0].lstrip("# ").strip()
            for sec in parts[1:]:
                head, _, body = sec.partition("\n")
                body = body.strip()
                if not body:
                    continue
                self.chunks.append({
                    "chunk_id": f"{m['doc_id']}#{len(self.chunks)}", "doc_id": m["doc_id"], "doc_type": m["doc_type"],
                    "title": title, "section": head.strip(), "text": body,
                    "index_text": f"{header}\n{head}\n{body}",
                })
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1)
        self.matrix = self.vec.fit_transform([c["index_text"] for c in self.chunks])

    # ---------------- retrieval ----------------
    def search(self, query: str, k: int = 5):
        q = self.vec.transform([query])
        scores = (self.matrix @ q.T).toarray().ravel()
        order = np.argsort(-scores)[:k]
        return [dict(self.chunks[i], score=float(scores[i])) for i in order]

    # ---------------- answering ----------------
    @staticmethod
    def _terms(text: str):
        return {t for t in TOKEN.findall(text.lower()) if t not in ENGLISH_STOP_WORDS and len(t) > 1}

    def _extractive(self, query, hits):
        qt = self._terms(query)
        picked, seen = [], set()
        top = hits[0]["score"]
        for n, h in enumerate(hits[:3], start=1):
            if h["score"] < 0.85 * top:     # ignore weakly related chunks (e.g. other markets)
                continue
            sents = re.split(r"(?<=[.!?])\s+(?=[A-Z$0-9])", h["text"])
            scored = sorted(((len(qt & self._terms(s)) / math.sqrt(1 + len(s.split())), s) for s in sents), reverse=True)
            for sc, s in scored[:2]:
                if sc > 0 and s.strip() not in seen:
                    seen.add(s.strip())
                    picked.append((n, s.strip(), sc))
        if not picked:
            picked = [(1, hits[0]["text"].split(". ")[0].strip() + ".", 0)]
        picked = sorted(picked, key=lambda x: (-x[2], x[0]))[:3]
        body = " ".join(f"{s} [{n}]" for n, s, _ in sorted(picked, key=lambda x: x[0]))
        return f"Based on \u201c{hits[0]['title']}\u201d: {body}"

    def _llm(self, query, hits):
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return None
        try:
            import httpx
            ctx = "\n\n".join(f"[{i}] ({h['title']} / {h['section']})\n{h['text']}" for i, h in enumerate(hits[:4], 1))
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 400,
                      "system": ("You answer questions about commercial real-estate documents. Use ONLY the numbered sources. "
                                 "Cite sources like [1]. If the sources do not contain the answer, say you cannot find it."),
                      "messages": [{"role": "user", "content": f"Sources:\n{ctx}\n\nQuestion: {query}"}]},
                timeout=30)
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json().get("content", [])).strip() or None
        except Exception:
            return None

    def ask(self, query: str, k: int = 5, use_llm: bool = True):
        hits = self.search(query, k)
        top = hits[0]["score"] if hits else 0.0
        sources = [{"n": i, "doc_id": h["doc_id"], "title": h["title"], "doc_type": h["doc_type"],
                    "section": h["section"], "score": round(h["score"], 3), "text": h["text"]} for i, h in enumerate(hits, 1)]
        if top < ABSTAIN_THRESHOLD:
            return {"answer": "I could not find supporting evidence for that in the loaded lease abstracts, market reports or property reports. "
                              "Try naming a market, property or tenant.", "abstained": True, "mode": "abstain",
                    "confidence": round(top, 3), "sources": sources}
        ans = self._llm(query, hits) if use_llm else None
        mode = "llm" if ans else "extractive"
        return {"answer": ans or self._extractive(query, hits), "abstained": False, "mode": mode,
                "confidence": round(top, 3), "sources": sources}

    def document(self, doc_id: str):
        m = self.docs.get(doc_id)
        if not m:
            return None
        return dict(m, text=(DOCS_DIR / m["file"]).read_text(encoding="utf-8"))

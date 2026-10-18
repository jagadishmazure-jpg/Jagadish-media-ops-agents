"""TF-IDF SOP retrieval with citations and explicit not-found.

Corpus: 4 SOP docs under docs/sops/. Answers cite ``<file> §<section>``.
Title-only chunks (headings with no body) are skipped — they caused a
false positive in a sibling repo.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter

_SOP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "docs", "sops")


def _tokenize(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


def load_chunks():
    chunks = []
    for fname in sorted(os.listdir(_SOP_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(_SOP_DIR, fname)
        with open(path) as f:
            text = f.read()
        # Split on ## headings; drop heading-only lines from bodies.
        parts = re.split(r"(?m)^## (.+)$", text)
        # parts[0] is preface, then (heading, body) pairs.
        for i in range(1, len(parts), 2):
            heading = parts[i].strip()
            body = parts[i + 1] if i + 1 < len(parts) else ""
            body_lines = [ln for ln in body.splitlines()
                          if ln.strip() and not ln.startswith("#")]
            body_text = " ".join(body_lines).strip()
            if not body_text:
                continue  # skip title-only chunks
            chunks.append({"file": fname, "section": heading,
                           "text": body_text})
    return chunks


def _scores(query: str, chunks: list) -> list:
    q_terms = _tokenize(query)
    if not q_terms:
        return []
    n = len(chunks)
    df = Counter()
    tf_list = []
    for ch in chunks:
        terms = _tokenize(ch["text"])
        tf = Counter(terms)
        tf_list.append(tf)
        for t in set(terms):
            df[t] += 1
    scored = []
    for ch, tf in zip(chunks, tf_list):
        s = 0.0
        for t in q_terms:
            if t in tf:
                idf = math.log((n + 1) / (df[t] + 1)) + 1.0
                s += (tf[t] / max(len(_tokenize(ch["text"])), 1)) * idf
        if s > 0:
            scored.append((s, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def retrieve(query: str, top_k: int = 2) -> list:
    """Return [{file, section, text, score}]; [] when nothing matches."""
    chunks = load_chunks()
    scored = _scores(query, chunks)[:top_k]
    return [{"file": ch["file"], "section": ch["section"],
             "text": ch["text"], "score": round(s, 4)}
            for s, ch in scored]


def answer(query: str) -> dict:
    hits = retrieve(query)
    if not hits:
        return {"answer": None, "citations": [],
                "note": "No SOP covers this question."}
    parts = []
    cites = []
    for h in hits:
        words = h["text"].split()
        snippet = " ".join(words[:60])
        parts.append(snippet)
        cites.append(f"{h['file']} §{h['section']}")
    return {"answer": " ".join(parts), "citations": cites, "note": ""}

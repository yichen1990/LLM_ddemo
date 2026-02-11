# app/rag.py

from pathlib import Path
from rank_bm25 import BM25Okapi


class LocalRAG:
    def __init__(self, kb_dir: Path, max_chars: int = 2000):
        self.kb_dir = kb_dir
        self.max_chars = max_chars
        self.docs = []
        self.doc_names = []

        texts = []
        for p in kb_dir.glob("*.md"):
            txt = p.read_text(encoding="utf-8")
            texts.append(txt)
            self.docs.append(txt)
            self.doc_names.append(p.name)

        tokenized = [t.split() for t in texts]
        self.bm25 = BM25Okapi(tokenized)

    def retrieve(self, query: str, k: int = 3):
        if not self.docs:
            return []

        scores = self.bm25.get_scores(query.split())
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for i in ranked[:k]:
            snippet = self.docs[i][: self.max_chars]
            results.append(f"[{self.doc_names[i]}]\n{snippet}")

        return results

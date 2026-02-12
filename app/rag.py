from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi


@dataclass
class RAGResult:
    snippets: List[str]          # formatted "[filename]\ncontent"
    sources: List[str]           # filenames only
    confidence: str              # "high" | "low"
    top_score: float             # raw BM25 score of best hit (after re-rank)


def _tag_for_filename(name: str) -> str:
    """
    Very lightweight domain tagging based on filename conventions.
    This keeps your demo simple, deterministic, and explainable.
    """
    n = name.lower()
    if n.startswith("en_wikipedia_") or "wikipedia" in n:
        return "wikipedia"
    if n in {"academic_integrity.md", "turnitin_guidance.md", "policy_ai_use.md", "course_outline.md"}:
        return "policy"
    if "prompt_injection" in n or "secure_rag" in n or "llm_security" in n:
        return "security_notes"
    return "other"


class LocalRAG:
    """
    Simple local RAG over *.md files using BM25.
    Adds:
      - relevance gating (min_score / relative threshold)
      - domain-aware re-ranking (wikipedia vs policy)
      - optional metadata return (without breaking old callers)
    """

    def __init__(self, kb_dir: Path, max_chars: int = 2000):
        self.kb_dir = kb_dir
        self.max_chars = max_chars

        self.docs: List[str] = []
        self.doc_names: List[str] = []
        self.doc_tags: List[str] = []

        texts: List[str] = []
        for p in kb_dir.glob("*.md"):
            txt = p.read_text(encoding="utf-8", errors="ignore")
            texts.append(txt)
            self.docs.append(txt)
            self.doc_names.append(p.name)
            self.doc_tags.append(_tag_for_filename(p.name))

        tokenized = [t.split() for t in texts] if texts else []
        self.bm25 = BM25Okapi(tokenized) if tokenized else None

    def retrieve(
        self,
        query: str,
        k: int = 3,
        *,
        intent: str = "GENERIC_QA",
        min_score: float = 0.10,
        min_relative: float = 0.15,
        return_meta: bool = False,
    ):
        """
        Returns:
          - default (backward compatible): List[str] of snippets
          - if return_meta=True: RAGResult(snippets, sources, confidence, top_score)

        Relevance gating:
          - drop hits below min_score
          - also drop hits below (best_score * min_relative)
        Domain-aware re-ranking:
          - GENERIC_QA: boost wikipedia; downweight policy
          - ASSESSMENT_GEN: boost policy and course outline
        """
        if not self.docs or self.bm25 is None:
            empty = RAGResult([], [], "low", 0.0)
            return empty if return_meta else []

        q_tokens = query.split()
        scores = list(self.bm25.get_scores(q_tokens))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        # Domain-aware reweighting (simple and explainable)
        def weight(tag: str, intent_: str) -> float:
            if intent_ == "GENERIC_QA":
                if tag == "wikipedia":
                    return 2.0
                if tag == "policy":
                    return 0.5
                if tag == "security_notes":
                    return 1.1
                return 1.0
            if intent_ == "ASSESSMENT_GEN":
                if tag == "policy":
                    return 2.0
                if tag == "wikipedia":
                    return 0.8
                return 1.0
            return 1.0

        weighted = [(i, scores[i] * weight(self.doc_tags[i], intent)) for i in ranked]
        weighted.sort(key=lambda x: x[1], reverse=True)

        best = weighted[0][1] if weighted else 0.0
        if best <= 0:
            empty = RAGResult([], [], "low", 0.0)
            return empty if return_meta else []

        # Relevance gating (prevents random irrelevant citations like academic_integrity.md for "Who is X?")
        filtered: List[Tuple[int, float]] = []
        for i, s in weighted:
            if s < min_score:
                continue
            if s < best * min_relative:
                continue
            filtered.append((i, s))

        # If nothing survives gating, we intentionally return "low" confidence and NO sources.
        if not filtered:
            empty = RAGResult([], [], "low", float(best))
            return empty if return_meta else []

        chosen = filtered[:k]
        snippets: List[str] = []
        sources: List[str] = []
        for i, _s in chosen:
            snippet = self.docs[i][: self.max_chars].strip()
            snippets.append(f"[{self.doc_names[i]}]\n{snippet}")
            sources.append(self.doc_names[i])

        out = RAGResult(snippets=snippets, sources=sources, confidence="high", top_score=float(chosen[0][1]))
        return out if return_meta else snippets

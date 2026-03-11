"""Lead Researcher agent node.

Synthesises retrieved documents and feature statistics into a structured
evidence answer.  This implementation is deterministic (no LLM calls) and
builds each answer section directly from the evidence.
"""
from __future__ import annotations

from typing import Any

from .state import AgentState


def lead_researcher(state: AgentState) -> dict[str, Any]:
    """Synthesise evidence into a structured answer with citations.

    Parameters
    ----------
    state:
        Must contain ``question``, ``retrieved_docs``, and ``features``.

    Returns
    -------
    dict
        Partial state update with ``answer``, ``citations``,
        ``revision_count``, and ``review_status`` reset to ``"pending"``.
    """
    question: str = state.get("question", "")
    docs: list[dict[str, Any]] = state.get("retrieved_docs", [])
    features: dict[str, dict[str, Any]] = state.get("features", {})
    revision_count: int = state.get("revision_count", 0)

    # ── Citations ──────────────────────────────────────────────────────────────
    citations: list[dict[str, Any]] = [
        {
            "id": d["doc_id"],
            "type": d.get("source_type", ""),
            "snippet": d.get("snippet", ""),
            "score": d.get("score", 0.0),
            "title": d.get("title", ""),
            "content": d.get("content", ""),
            "iceberg_snapshot_ref": d.get("iceberg_snapshot_ref", ""),
        }
        for d in docs
    ]

    # ── Answer sections ────────────────────────────────────────────────────────
    if not docs:
        answer: dict[str, str] = {
            "background": f"Query: {question}",
            "evidence": "No relevant documents found in the knowledge base.",
            "statistics": "No statistical data available.",
            "conclusion": (
                "Insufficient evidence to provide a substantive answer. "
                "Consider broadening the search query or filters."
            ),
        }
    else:
        top_docs = docs[:3]
        evidence_parts = [
            f"[{d['doc_id']}] {d.get('snippet', '(no snippet)')}"
            for d in top_docs
        ]

        stat_parts: list[str] = []
        for doc_id, feat in features.items():
            if feat.get("sample_size"):
                stat_parts.append(f"{doc_id}: n={feat['sample_size']}")
            if feat.get("abstract_word_count"):
                stat_parts.append(
                    f"{doc_id}: abstract_words={feat['abstract_word_count']}"
                )
            if feat.get("publication_year"):
                stat_parts.append(
                    f"{doc_id}: year={feat['publication_year']}"
                )
            if feat.get("has_outcomes"):
                stat_parts.append(f"{doc_id}: has_outcomes=True")

        best = docs[0]
        answer = {
            "background": (
                f"Analysis of {len(docs)} retrieved biomedical document(s) "
                f"relevant to: {question}"
            ),
            "evidence": " | ".join(evidence_parts),
            "statistics": (
                "; ".join(stat_parts)
                if stat_parts
                else "Feature data not available for retrieved documents."
            ),
            "conclusion": (
                f"Based on {len(docs)} document(s) "
                f"(top relevance score: {best.get('score', 0.0):.3f}), "
                f"the retrieved evidence addresses the query. "
                f"Primary reference: {best['doc_id']} — {best.get('title', 'N/A')}."
            ),
        }

    return {
        "answer": answer,
        "citations": citations,
        "revision_count": revision_count + 1,
        "review_status": "pending",
        "review_feedback": "",
    }

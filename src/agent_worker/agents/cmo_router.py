"""CMO Router agent node.

Classifies the incoming query and extracts search parameters.  Does **not**
call any external service — pure, stateless logic that is trivially testable.
"""
from __future__ import annotations

from typing import Any

from .state import AgentState

# Stop-words to strip when building a focused search query
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "of", "in",
        "on", "at", "to", "for", "with", "by", "from", "about", "into", "and",
        "or", "but", "if", "as", "that", "this", "it", "its", "what", "which",
        "who", "whom", "how", "when", "where", "why", "there", "their",
    }
)

_TRIAL_KEYWORDS = frozenset(
    {"trial", "trials", "rct", "randomised", "randomized", "clinical", "nct"}
)
_ARTICLE_KEYWORDS = frozenset(
    {"article", "articles", "paper", "publication", "study", "research", "pubmed"}
)


def _extract_search_terms(text: str) -> str:
    """Return a condensed search string by dropping common stop-words."""
    tokens = text.lower().split()
    content_tokens = [t.strip(".,;:?!()") for t in tokens if t not in _STOP_WORDS]
    return " ".join(t for t in content_tokens if t)


def cmo_router(state: AgentState) -> dict[str, Any]:
    """Classify the query and produce search parameters.

    Parameters
    ----------
    state:
        Must contain ``question`` and optionally ``filters``.

    Returns
    -------
    dict
        Partial state update with ``search_query``, ``search_limit``, and
        optionally an enriched ``filters`` dict.
    """
    question: str = state.get("question", "")
    filters: dict[str, Any] = dict(state.get("filters") or {})

    lower_q = question.lower()

    # Detect implied source type if the user did not specify
    if "source_type" not in filters:
        words = frozenset(lower_q.split())
        if words & _TRIAL_KEYWORDS:
            filters["source_type"] = "trial"
        elif words & _ARTICLE_KEYWORDS:
            filters["source_type"] = "article"

    search_query = _extract_search_terms(question) or question
    return {
        "search_query": search_query,
        "search_limit": 5,
        "filters": filters or None,
    }

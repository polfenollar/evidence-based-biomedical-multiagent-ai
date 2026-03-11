"""Medical Librarian agent node.

Calls the retrieval-api to fetch ranked biomedical documents.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .state import AgentState


def make_medical_librarian(retrieval_api_url: str) -> Callable[[AgentState], dict[str, Any]]:
    """Return a LangGraph node that calls the retrieval-api.

    Parameters
    ----------
    retrieval_api_url:
        Base URL of the retrieval service, e.g. ``http://retrieval-api:8001``.

    Returns
    -------
    Callable
        Node function compatible with :class:`langgraph.graph.StateGraph`.
    """

    def medical_librarian(state: AgentState) -> dict[str, Any]:
        """Search for relevant documents and populate ``retrieved_docs``."""
        query = state.get("search_query") or state.get("question", "")
        limit = state.get("search_limit", 5)
        raw_filters = state.get("filters")

        body: dict[str, Any] = {"query": query, "limit": limit}
        if raw_filters:
            # retrieval-api expects a SearchFilters-shaped object
            body["filters"] = {k: v for k, v in raw_filters.items() if v is not None}

        try:
            resp = httpx.post(
                f"{retrieval_api_url}/v1/search",
                json=body,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            docs = data.get("results", [])
        except Exception:  # noqa: BLE001
            docs = []

        return {"retrieved_docs": docs}

    return medical_librarian

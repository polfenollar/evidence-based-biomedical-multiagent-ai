"""Clinical Biostatistician agent node.

Fetches structured feature data from the feature-api for each retrieved doc.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .state import AgentState


def make_clinical_biostatistician(
    feature_api_url: str,
) -> Callable[[AgentState], dict[str, Any]]:
    """Return a LangGraph node that enriches docs with feature-api data.

    Parameters
    ----------
    feature_api_url:
        Base URL of the feature service, e.g. ``http://feature-api:8002``.

    Returns
    -------
    Callable
        Node function compatible with :class:`langgraph.graph.StateGraph`.
    """

    def clinical_biostatistician(state: AgentState) -> dict[str, Any]:
        """Look up feature statistics for each retrieved document."""
        docs: list[dict[str, Any]] = state.get("retrieved_docs", [])
        features: dict[str, dict[str, Any]] = {}

        for doc in docs:
            doc_id: str = doc.get("doc_id", "")
            source_type: str = doc.get("source_type", "")

            try:
                if source_type == "article":
                    # doc_id format: "PMID:12345" → extract numeric part
                    pmid = doc_id.split(":")[-1] if ":" in doc_id else doc_id
                    resp = httpx.get(
                        f"{feature_api_url}/v1/features/article/{pmid}",
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        features[doc_id] = resp.json()

                elif source_type == "trial":
                    nct_id = doc_id
                    resp = httpx.get(
                        f"{feature_api_url}/v1/features/trial/{nct_id}",
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        features[doc_id] = resp.json()

            except Exception:  # noqa: BLE001
                # Feature lookup failure is non-fatal; continue without data
                pass

        return {"features": features}

    return clinical_biostatistician

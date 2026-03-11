"""Peer Reviewer agent node.

Validates the answer produced by the Lead Researcher against a set of
deterministic quality rules.  If all rules pass the review status is set to
``"approved"``; otherwise ``"rejected"`` with specific feedback.

Rules
-----
1. At least one citation must be present.
2. No citation may have an empty snippet.
3. All four answer sections (background, evidence, statistics, conclusion)
   must be non-empty.
"""
from __future__ import annotations

from typing import Any

from .state import AgentState

_REQUIRED_ANSWER_KEYS = ("background", "evidence", "statistics", "conclusion")


def peer_reviewer(state: AgentState) -> dict[str, Any]:
    """Review the current answer/citations and set review_status.

    Parameters
    ----------
    state:
        Must contain ``citations`` and ``answer``.

    Returns
    -------
    dict
        Partial state update with ``review_status`` and ``review_feedback``.
    """
    citations: list[dict[str, Any]] = state.get("citations", [])
    answer: dict[str, str] = state.get("answer", {})

    # Rule 1: at least one citation
    if not citations:
        return {
            "review_status": "rejected",
            "review_feedback": (
                "No citations found. Answer must be backed by retrieved evidence."
            ),
        }

    # Rule 2: no empty-snippet citations
    empty_snippet_ids = [
        c.get("id", "?") for c in citations if not c.get("snippet", "").strip()
    ]
    if empty_snippet_ids:
        return {
            "review_status": "rejected",
            "review_feedback": (
                f"{len(empty_snippet_ids)} citation(s) have empty snippets: "
                + ", ".join(empty_snippet_ids)
            ),
        }

    # Rule 3: all answer sections non-empty
    missing = [k for k in _REQUIRED_ANSWER_KEYS if not answer.get(k, "").strip()]
    if missing:
        return {
            "review_status": "rejected",
            "review_feedback": (
                f"Answer section(s) missing or empty: {missing}"
            ),
        }

    return {"review_status": "approved", "review_feedback": ""}

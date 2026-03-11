"""Pure UI helper functions — testable without Streamlit.

These functions format data structures for display; they return strings or
dicts and have no Streamlit import, making them unit-testable.
"""
from __future__ import annotations

from typing import Any


# ── Citation helpers ───────────────────────────────────────────────────────────

def format_citation_badge(citation: dict[str, Any]) -> str:
    """Return a short badge label for a citation.

    Parameters
    ----------
    citation:
        Dict with at least ``id`` and ``type``.

    Returns
    -------
    str
        Badge text, e.g. ``"[article] PMID:99000001"``.
    """
    ctype = citation.get("type", "unknown")
    cid = citation.get("id", "?")
    return f"[{ctype}] {cid}"


def format_citation_detail(citation: dict[str, Any]) -> str:
    """Return a multi-line citation detail string.

    Parameters
    ----------
    citation:
        Dict with ``id``, ``type``, ``title``, ``snippet``, ``score``,
        ``iceberg_snapshot_ref``.

    Returns
    -------
    str
        Human-readable citation detail.
    """
    score = citation.get("score", 0.0)
    title = citation.get("title", "N/A")
    snippet = citation.get("snippet", "")
    ref = citation.get("iceberg_snapshot_ref", "")
    badge = format_citation_badge(citation)
    lines = [
        f"**{badge}** (score: {score:.3f})",
        f"*{title}*",
    ]
    if snippet:
        lines.append(f"> {snippet}")
    
    content = citation.get("content", "")
    if content:
        lines.append("\n**Full Content:**")
        lines.append(content)

    if ref:
        lines.append(f"\nsnapshot: `{ref}`")
    return "\n".join(lines)


# ── Timeline helpers ───────────────────────────────────────────────────────────

def format_timeline_row(step: dict[str, Any]) -> dict[str, Any]:
    """Flatten a timeline step record for tabular display.

    Parameters
    ----------
    step:
        Dict with ``step``, ``elapsed_ms``, ``started_at``.

    Returns
    -------
    dict
        Row with ``Node``, ``Elapsed (ms)``, ``Started At`` keys.
    """
    return {
        "Node": step.get("step", "?"),
        "Elapsed (ms)": step.get("elapsed_ms", 0),
        "Started At": step.get("started_at", ""),
    }


def format_timeline_table(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a raw execution timeline to a list of display rows.

    Parameters
    ----------
    timeline:
        List of step dicts from the evidence manifest.

    Returns
    -------
    list[dict]
        List of display rows suitable for ``st.dataframe``.
    """
    return [format_timeline_row(s) for s in timeline]


# ── Answer helpers ─────────────────────────────────────────────────────────────

def format_answer_sections(answer: dict[str, str]) -> list[tuple[str, str]]:
    """Return ordered (label, text) pairs for displaying the answer.

    Parameters
    ----------
    answer:
        Dict with ``background``, ``evidence``, ``statistics``, ``conclusion``.

    Returns
    -------
    list[tuple[str, str]]
        Ordered label/content pairs.
    """
    order = [
        ("Background", "background"),
        ("Evidence", "evidence"),
        ("Statistics", "statistics"),
        ("Conclusion", "conclusion"),
    ]
    return [(label, answer.get(key, "")) for label, key in order]


# ── SSE helpers ────────────────────────────────────────────────────────────────

_NODE_LABELS: dict[str, str] = {
    "cmo_router": "CMO Router",
    "medical_librarian": "Medical Librarian",
    "clinical_biostatistician": "Clinical Biostatistician",
    "lead_researcher": "Lead Researcher",
    "peer_reviewer": "Peer Reviewer",
    "finalize": "Finalize",
}


def node_display_name(node_name: str) -> str:
    """Map internal node names to human-readable labels.

    Parameters
    ----------
    node_name:
        LangGraph node identifier.

    Returns
    -------
    str
        Display label for the node.
    """
    return _NODE_LABELS.get(node_name, node_name)


def parse_sse_event(raw_line: str) -> dict[str, Any] | None:
    """Parse a single SSE ``data:`` line into a dict.

    Parameters
    ----------
    raw_line:
        Raw text line from the SSE stream.

    Returns
    -------
    dict | None
        Parsed JSON payload, or ``None`` if the line is not a data line or
        the JSON is malformed.
    """
    if not raw_line.startswith("data:"):
        return None
    try:
        import json
        return json.loads(raw_line[len("data:"):].strip())
    except (ValueError, TypeError):
        return None


# ── Document summary helpers ───────────────────────────────────────────────────

def format_document_summary(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a list of document summary dicts for the source documents panel.

    Parameters
    ----------
    citations:
        List of citation dicts from the query response.

    Returns
    -------
    list[dict]
        Each dict has ``title``, ``type``, ``id``, ``score``, ``snippet``,
        ``snapshot_ref`` keys, ordered by descending score.
    """
    docs = []
    for c in citations:
        docs.append({
            "title": c.get("title") or c.get("id", "Untitled"),
            "type": c.get("type", "unknown"),
            "id": c.get("id", ""),
            "score": float(c.get("score", 0.0)),
            "snippet": c.get("snippet", ""),
            "content": c.get("content", ""),
            "snapshot_ref": c.get("iceberg_snapshot_ref", ""),
        })
    return sorted(docs, key=lambda d: d["score"], reverse=True)


def format_aggregate_summary(citations: list[dict[str, Any]]) -> str:
    """Create a synthesized summary of all retrieved snippets.

    Parameters
    ----------
    citations:
        List of citation dicts from the query response.

    Returns
    -------
    str
        Markdown string aggregating snippets with source attribution.
    """
    if not citations:
        return "No documentation content found."

    # Sort by score to get the most relevant snippets first
    sorted_citations = sorted(
        citations, key=lambda c: float(c.get("score", 0.0)), reverse=True
    )

    summary_lines = ["### 📄 Summary of Retrieved Documentation Content\n"]
    for i, c in enumerate(sorted_citations):
        snippet = c.get("snippet", "").strip()
        if not snippet:
            continue

        cid = c.get("id", "?")
        title = c.get("title", cid)
        summary_lines.append(f"**[{i+1}] {title} ({cid})**")
        summary_lines.append(f"> {snippet}\n")

    if len(summary_lines) <= 1:
        return "No substantive snippets found in retrieved documentation."

    return "\n".join(summary_lines)


# ── DQ-UI helpers ──────────────────────────────────────────────────────────────

def check_response_has_citations(response: dict[str, Any]) -> str | None:
    """DQ-UI-1: return an error message if citations are absent.

    Parameters
    ----------
    response:
        Decoded query response JSON.

    Returns
    -------
    str | None
        Error message string if DQ-UI-1 is violated, else ``None``.
    """
    if not response.get("citations"):
        return (
            "⚠️ DQ-UI-1: This response contains no citations. "
            "The answer cannot be displayed without evidence backing."
        )
    return None

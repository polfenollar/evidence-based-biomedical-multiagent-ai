"""Streamlit UI — Biomedical AI Research Platform.

Pages
-----
Researcher Portal
    Submit a biomedical question, watch per-step SSE progress, view structured
    answer with inline citation badges, evidence panel, statistics panel, and
    a link to the Audit View.

Operator Dashboard
    List recent query IDs, view run metadata.
    Requires ``X-Role: operator`` — blocks Researcher sessions.

Audit / Explainability View
    Enter a manifest ID to view the full evidence manifest, execution timeline,
    and raw citations.
"""
from __future__ import annotations

import json
import os

import requests
import streamlit as st

from src.ui.components import (
    check_response_has_citations,
    format_answer_sections,
    format_citation_badge,
    format_citation_detail,
    format_document_summary,
    format_aggregate_summary,
    format_timeline_table,
    node_display_name,
)

_AGENT_API = os.environ.get("AGENT_API_URL", "http://agent-api:8003")
_AUDIT_API = os.environ.get("AUDIT_API_URL", "http://audit-api:8004")

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Biomedical AI Research Platform",
    page_icon="🔬",
    layout="wide",
)

# ── Sidebar navigation ─────────────────────────────────────────────────────────

st.sidebar.title("🔬 Biomedical AI")
page = st.sidebar.radio(
    "Navigate",
    ["Researcher Portal", "Operator Dashboard", "Audit View"],
)
role = st.sidebar.selectbox("Role (demo)", ["researcher", "operator"], index=0)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Researcher Portal
# ═══════════════════════════════════════════════════════════════════════════════

if page == "Researcher Portal":
    st.title("Researcher Portal (DEBUG: V2)")
    st.caption("Submit a biomedical question to the multi-agent evidence pipeline.")

    with st.form("query_form"):
        question = st.text_area(
            "Question",
            placeholder="e.g. What is the effect of aspirin on cardiovascular outcomes?",
            height=80,
        )
        source_filter = st.selectbox(
            "Filter by source type (optional)",
            ["(none)", "article", "trial"],
        )
        use_streaming = st.checkbox("Stream agent steps (SSE)", value=True)
        submitted = st.form_submit_button("Submit")

    if submitted and question.strip():
        filters = (
            {"source_type": source_filter}
            if source_filter != "(none)"
            else None
        )
        payload = {"question": question, "filters": filters}
        headers = {"X-Role": role}

        if use_streaming:
            # ── SSE streaming mode ──────────────────────────────────────────
            st.subheader("Agent Progress")
            progress_placeholder = st.empty()
            steps_so_far: list[str] = []

            response_holder: dict = {}

            try:
                with requests.post(
                    f"{_AGENT_API}/v1/query/stream",
                    json=payload,
                    headers=headers,
                    stream=True,
                    timeout=120,
                ) as resp:
                    resp.raise_for_status()
                    current_event = None
                    for line in resp.iter_lines(decode_unicode=True):
                        if line.startswith("event:"):
                            current_event = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            raw_data = line[len("data:"):].strip()
                            try:
                                data = json.loads(raw_data)
                            except json.JSONDecodeError:
                                continue

                            if current_event == "step":
                                node = data.get("node", "?")
                                label = node_display_name(node)
                                elapsed = data.get("elapsed_ms", 0)
                                steps_so_far.append(f"✅ {label} ({elapsed} ms)")
                                progress_placeholder.markdown(
                                    "\n".join(steps_so_far)
                                )
                            elif current_event == "complete":
                                response_holder = data
                            elif current_event == "error":
                                st.error(f"Pipeline error: {data.get('message', data)}")

            except requests.exceptions.ConnectionError:
                st.error(
                    "⚠️ **SSE connection dropped** — the streaming connection was "
                    "interrupted. The pipeline may still be running. "
                    "Try again or use non-streaming mode."
                )
                st.stop()
            except requests.exceptions.RequestException as exc:
                st.error(f"Connection error: {exc}")
                st.stop()

            result = response_holder

        else:
            # ── Non-streaming mode ──────────────────────────────────────────
            with st.spinner("Running evidence pipeline …"):
                try:
                    resp = requests.post(
                        f"{_AGENT_API}/v1/query",
                        json=payload,
                        headers=headers,
                        timeout=120,
                    )
                    if resp.status_code == 422:
                        err = resp.json()
                        st.error(
                            f"⚠️ DQ-UI-1: {err.get('detail', {}).get('message', 'No citations')}"
                        )
                        st.stop()
                    resp.raise_for_status()
                    result = resp.json()
                except requests.exceptions.RequestException as exc:
                    st.error(f"Error: {exc}")
                    st.stop()

        if not result:
            st.warning("No result received.")
            st.stop()

        # ── DQ-UI-1 check ───────────────────────────────────────────────────
        dq_error = check_response_has_citations(result)
        if dq_error:
            st.error(dq_error)
            st.stop()

        # ── Answer panels ───────────────────────────────────────────────────
        st.subheader("Evidence Answer")
        answer = result.get("answer", {})
        col1, col2 = st.columns(2)
        sections = format_answer_sections(answer)
        for i, (label, text) in enumerate(sections):
            col = col1 if i % 2 == 0 else col2
            with col:
                with st.expander(label, expanded=(label in ("Background", "Conclusion"))):
                    st.write(text)

        # ── Retrieved Source Documents ───────────────────────────────────────
        citations = result.get("citations", [])
        docs = format_document_summary(citations)
        with st.expander(f"Retrieved Source Documents ({len(docs)})", expanded=True):
            if docs:
                # ── Aggregate Summary Window ─────────────────────────────────
                summary_md = format_aggregate_summary(citations)
                st.info(summary_md)
                st.divider()

                for doc in docs:
                    score_pct = int(doc["score"] * 100)
                    type_icon = "📄" if doc["type"] == "article" else "🧪"
                    st.markdown(
                        f"{type_icon} **{doc['title']}** &nbsp; "
                        f"`{doc['id']}` &nbsp; "
                        f"<span style='color:grey'>relevance: {score_pct}%</span>",
                        unsafe_allow_html=True,
                    )
                    st.progress(doc["score"])
                    
                    # Display full content if available, else fallback to snippet
                    display_text = doc.get("content") or doc.get("snippet")
                    if display_text:
                        st.info(display_text)

                    if doc["snapshot_ref"]:
                        st.caption(f"Iceberg snapshot: {doc['snapshot_ref']}")
                    st.divider()
            else:
                st.info("No source documents available.")

        # ── Citation badges ─────────────────────────────────────────────────
        st.subheader("Citations")
        for c in citations:
            badge = format_citation_badge(c)
            with st.expander(badge):
                st.markdown(format_citation_detail(c))

        # ── Review status ───────────────────────────────────────────────────
        review_status = result.get("review_status", "unknown")
        if review_status == "approved":
            st.success(f"Peer review: **{review_status}**")
        else:
            st.warning(
                f"Peer review: **{review_status}** — {result.get('review_feedback', '')}"
            )

        # ── Audit trail link ────────────────────────────────────────────────
        manifest_id = result.get("evidence_manifest_id", "")
        if manifest_id:
            st.info(f"Audit trail available. Manifest ID: `{manifest_id}`")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Operator Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Operator Dashboard":
    st.title("Operator Dashboard")

    if role != "operator":
        st.error("🔒 Access denied. Operator role required.")
        st.info("Change your role to **operator** in the sidebar to access this page.")
        st.stop()

    st.caption("Recent query IDs and run metadata.")

    headers = {"X-Role": role}
    try:
        resp = requests.get(
            f"{_AGENT_API}/v1/operator/queries",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 403:
            st.error("Access denied by server (403).")
            st.stop()
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Failed to load queries: {exc}")
        st.stop()

    query_ids: list[str] = data.get("query_ids", [])
    count = data.get("count", 0)

    st.metric("Total queries tracked", count)

    if query_ids:
        # Show most recent 50
        recent = list(reversed(query_ids))[:50]
        st.dataframe(
            [{"#": i + 1, "Query ID": qid} for i, qid in enumerate(recent)],
            use_container_width=True,
        )
    else:
        st.info("No queries recorded yet. Submit a question via the Researcher Portal.")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Audit View
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Audit View":
    st.title("Audit / Explainability View")
    st.caption("Enter a manifest ID to inspect the full evidence manifest and execution timeline.")

    manifest_id_input = st.text_input("Manifest ID", placeholder="Paste a UUID here …")
    load_btn = st.button("Load Audit Record")

    if load_btn and manifest_id_input.strip():
        try:
            resp = requests.get(
                f"{_AUDIT_API}/v1/audit/{manifest_id_input.strip()}",
                timeout=10,
            )
            if resp.status_code == 404:
                st.warning("Manifest not found. It may have expired (TTL: 24 h).")
                st.stop()
            resp.raise_for_status()
            manifest = resp.json()
        except requests.exceptions.ConnectionError:
            # DQ-UI-5: audit-api unreachable → degraded-mode warning
            st.warning(
                "⚠️ **Degraded mode** — Audit API is currently unavailable. "
                "Audit trails cannot be displayed. The research portal remains functional. "
                "Contact your operator if this persists."
            )
            st.stop()
        except requests.exceptions.RequestException as exc:
            st.error(f"Failed to load manifest: {exc}")
            st.stop()

        # ── Metadata ────────────────────────────────────────────────────────
        st.subheader("Query Metadata")
        col1, col2, col3 = st.columns(3)
        col1.metric("Review Status", manifest.get("review_status", "?"))
        col2.metric("Retrieved Docs", manifest.get("retrieved_doc_count", 0))
        col3.metric("Feature Enriched", manifest.get("feature_enriched_count", 0))

        st.markdown(f"**Question:** {manifest.get('question', '')}")
        if manifest.get("review_feedback"):
            st.warning(f"Review feedback: {manifest['review_feedback']}")

        # ── Execution Timeline ───────────────────────────────────────────────
        st.subheader("Execution Timeline")
        timeline = manifest.get("execution_timeline", [])
        if timeline:
            rows = format_timeline_table(timeline)
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No timeline data available for this manifest.")

        # ── Answer ──────────────────────────────────────────────────────────
        st.subheader("Evidence Answer")
        answer = manifest.get("answer", {})
        for label, text in format_answer_sections(answer):
            with st.expander(label):
                st.write(text)

        # ── Citations ────────────────────────────────────────────────────────
        st.subheader("Citations")
        for c in manifest.get("citations", []):
            badge = format_citation_badge(c)
            with st.expander(badge):
                st.markdown(format_citation_detail(c))

        # ── Raw manifest ────────────────────────────────────────────────────
        with st.expander("Raw Manifest JSON"):
            st.json(manifest)

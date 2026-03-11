## 1. Overview

This Functional Requirements Document (FRD) describes *what* the Evidence-Based Bio-Medical Multi-Agent System must do, independent of specific implementation details.

The system is an open-source, self-hosted, production-grade platform that:

- Ingests and curates large-scale biomedical datasets (PubMed Open Access Subset, ClinicalTrials.gov).
- Maintains a governed data lake and feature store for statistical computation.
- Builds and queries a semantic vector index over biomedical literature.
- Orchestrates a team of specialized AI agents to answer medical research questions using only verifiable evidence and statistics.
- Exposes APIs (and optionally a UI) so users can submit research questions and receive cited, evidence-based responses.

---

## 1.1 Non-Negotiable Requirement: Fully Auditable and Transparent Agents

FR-A1. The system SHALL ensure that **all agent behavior is fully auditable and transparent**, such that an operator can reconstruct and review:

- The complete workflow execution trace (routing decisions, tool calls, retries).
- All retrieved evidence (documents, snippets, identifiers) used in reasoning.
- All statistical values used (feature store lookups and/or data lake calculations).
- All intermediate agent outputs that materially influenced the final response.

FR-A2. The system SHALL produce final responses that include a machine-readable **evidence manifest** mapping each factual claim (or answer section) to its supporting evidence references.

FR-A3. The system SHALL support operator-driven **replay/reconstruction** of an execution using the same configuration and the same data snapshot(s), producing materially consistent results for audit purposes.

FR-A4. When insufficient evidence exists, the system SHALL return a structured refusal/fallback response that is itself auditable, including the missing evidence types and the reason the answer cannot be safely produced.

---

## 2. Stakeholders and User Roles

### 2.1 Stakeholders

- **Clinical Researchers / Clinicians**: Use the system to synthesize biomedical evidence for clinical or academic questions.
- **Data Engineers**: Operate and maintain ingestion and data processing pipelines.
- **ML / AI Engineers**: Configure models, embeddings, and retrieval strategies.
- **System Operators / DevOps**: Deploy and monitor the full stack in production-like environments.
- **Quality and Compliance Teams**: Verify that outputs are evidence-based and that data use respects licensing constraints.

### 2.2 User Roles

- **Researcher User**:
  - Submits biomedical questions.
  - Receives structured, cited responses and can inspect underlying evidence.
- **Data Operator**:
  - Triggers or schedules ingestion pipelines.
  - Monitors ingestion, data quality, and curation status.
- **System Operator**:
  - Manages deployments, orchestrations, and component health.
  - Receives alerts from observability systems and responds to incidents.

---

## 3. High-Level Functional Requirements

### 3.1 Data Ingestion and Curation

FR-1. The system SHALL ingest biomedical literature from the PubMed Open Access Subset in bulk format (e.g., XML, JSON, or other official export formats).

FR-2. The system SHALL ingest clinical trial metadata and outcomes from ClinicalTrials.gov bulk exports.

FR-3. The system SHALL parse raw documents into structured records, extracting key entities such as:

- Article identifiers, titles, abstracts, methods, results.
- Clinical trial identifiers, conditions, interventions, outcomes, and sample sizes.

FR-4. The system SHALL apply data curation steps including:

- Deduplication of records.
- Normalization of field formats (e.g., dates, identifiers).
- Basic entity standardization (e.g., mapping drugs and diseases to canonical forms where feasible).

FR-5. The system SHALL write curated data into a governed data lake with ACID guarantees and support for schema evolution.

FR-6. The system SHALL maintain ingestion metadata (e.g., ingestion timestamp, source version, and pipeline version) for each record to support reproducibility and lineage.

### 3.2 Data Lake and Governance

FR-7. The system SHALL expose curated datasets as analytical tables in a data lake, organized at least into:

- Raw ingestion tables mirroring source structure.
- Cleaned, normalized tables suitable for downstream analytics and ML.
- Aggregated or derived tables (e.g., entity-level summaries).

FR-8. The system SHALL enforce data quality checks (as defined by the Data Officer) and SHALL reject or quarantine records that fail critical validation rules.

FR-9. The system SHALL provide mechanisms to:

- List current datasets and schemas.
- Query dataset schemas programmatically.
- Access historical snapshots or versions of datasets.

### 3.3 Feature Store and Statistical Metrics

FR-10. The system SHALL compute structured statistical features from curated data, including but not limited to:

- Co-occurrence frequencies between drugs, diseases, and side effects.
- Distributional statistics for trial outcomes (e.g., response rates, adverse event rates).
- Counts of trials and publications per entity or entity pair.

FR-11. The system SHALL expose these features through an AI feature store that supports:

- Entity-based feature retrieval (e.g., for a given drug or condition).
- Time-aware feature retrieval where applicable.

FR-12. The system SHALL allow multi-agent workflows to query the feature store directly to obtain numeric values, rather than forcing LLM agents to “guess” statistics.

### 3.4 Vector Index and Retrieval Services

FR-13. The system SHALL generate vector embeddings for:

- Publication titles and abstracts.
- Key sections of methods and results.
- Clinical trial descriptions and outcomes.

FR-14. The system SHALL index these embeddings in a vector database capable of:

- Efficient similarity search across millions of documents.
- Storing references to original documents and any associated metadata (e.g., PubMed ID).

FR-15. The system SHALL expose retrieval services that:

- Accept a query (e.g., user question or intermediate agent question).
- Perform vector search.
- Return ranked passages/snippets with references to their source documents.

### 3.5 Domain Multi-Agent Orchestration

FR-16. The system SHALL implement a deterministic, stateful multi-agent workflow with at least the following roles:

- **Chief Medical Officer (Router)**: Parses user questions and decomposes them into structured research tasks.
- **Medical Librarian (Retrieval)**: Queries the vector database and returns relevant literature excerpts and identifiers.
- **Clinical Biostatistician (Quant)**: Queries the feature store and/or underlying data lake for numeric statistics.
- **Lead Researcher (Synthesis)**: Drafts an evidence-based answer using only the retrieved context and statistics.
- **Peer Reviewer (Critic)**: Validates the draft answer against the available evidence and rejects or requests revisions if unsupported claims are found.

FR-17. The multi-agent workflow SHALL maintain a shared state that includes:

- The original user question and any sub-questions.
- Retrieved documents and statistics.
- Intermediate reasoning steps and draft answers.

FR-18. The workflow SHALL be deterministic given the same inputs and configuration, to support reproducibility and auditing.

FR-19. The Peer Reviewer agent SHALL be able to:

- Highlight unsupported or weakly supported claims.
- Enforce that each factual claim in the final answer is backed by at least one citation (literature or statistical feature).

### 3.6 User Interaction and APIs

FR-20. The system SHALL expose a programmatic API for research queries, which at minimum:

- Accepts user questions and optional parameters (e.g., time ranges, filters).
- Returns structured responses with:
  - Natural language answers.
  - A list of citations (e.g., PubMed IDs, trial IDs).
  - Links or identifiers mapping to underlying data used.

FR-21. The system SHALL provide a web-based UI composed of three views:

**21a. Researcher Portal (primary user-facing view)**

- Text input for biomedical research questions with optional filters (date range, study type, entity filters).
- Real-time progress display showing each agent step as it executes (CMO → Librarian → Biostatistician → Researcher → Reviewer).
- Structured result view with:
  - Natural language answer organized into sections (background, evidence, statistics, conclusion).
  - Inline citation badges per claim, linked to PubMed IDs or NCT IDs.
  - Collapsible evidence panel showing ranked source passages and retrieval scores.
  - Statistics panel showing feature store values used (co-occurrence rates, outcome distributions).
  - "View Audit Trail" link navigating to the Audit View for that execution.
- Structured refusal/fallback display when insufficient evidence is found, including missing evidence types.

**21b. Operator Dashboard**

- Table of ingestion job runs: status, records ingested, data quality pass/fail, timestamps.
- Trigger ingestion and re-index actions (operator role required).
- Data quality report viewer: rule evaluation results, quarantined record counts, pipeline version.
- Pipeline health summary: Temporal workflow states, per-service health indicators.

**21c. Audit / Explainability View**

- Per-query execution timeline: collapsible list of agent steps with individual inputs and outputs.
- Evidence manifest viewer: mapping from answer claims/sections to supporting evidence items.
- Replay button: re-run query against the same recorded data snapshot.
- Refusal detail viewer: structured breakdown of why an answer was refused when applicable.

FR-22. The system SHALL provide APIs for data and system operators to:

- Trigger ingestion jobs.
- View ingestion status and recent runs.
- Inspect data quality reports and metrics.

### 3.7 Evidence and Explainability

FR-23. The system SHALL ensure that any numerical claims in final answers can be traced back to:

- Specific feature store entries and/or
- Specific aggregated datasets or calculations in the data lake.

FR-24. The system SHALL allow an operator to reconstruct, for any given user query:

- The sequence of agents involved and their individual outputs.
- The documents and statistics each agent used.

FR-25. The system SHALL store enough metadata to support later audit of:

- Input query.
- Workflow execution trace.
- Final response and its sources.

---

## 4. Functional Modules

This section outlines the primary modules that collaborate to satisfy the above requirements.

### 4.1 Ingestion Module

- Responsible for:
  - Downloading or receiving bulk data from PubMed OA and ClinicalTrials.gov.
  - Parsing, validating, and storing raw data.
  - Emitting curated records and ingestion metadata to the data lake.

### 4.2 Data Lake Module

- Responsible for:
  - Organizing raw and curated tables.
  - Exposing schemas and snapshots.
  - Enforcing data quality rules and surfacing violations.

### 4.3 Feature Store Module

- Responsible for:
  - Defining feature views and entities.
  - Computing and storing statistical metrics.
  - Serving feature values to downstream services and agents.

### 4.4 Vector Retrieval Module

- Responsible for:
  - Generating and updating embeddings for texts.
  - Indexing embeddings in the vector database.
  - Providing semantic search APIs and helpers to the Librarian agent.

### 4.5 Multi-Agent Reasoning Module

- Responsible for:
  - Defining the LangGraph state and agent routing logic.
  - Ensuring deterministic state transitions and reproducible outputs.
  - Managing iterations between Lead Researcher and Peer Reviewer.

### 4.6 API & Presentation Module

- Responsible for:
  - External query API.
  - UI: Researcher Portal, Operator Dashboard, and Audit/Explainability View (see FR-21).
  - Real-time agent step streaming from `agent-api` to the UI via Server-Sent Events.
  - Surfacing logs, traces, and evidence links for users and operators.

---

## 5. Functional Quality Constraints

FR-26. The system SHALL not output final answers that contain uncited factual claims.

FR-27. The system SHALL surface clear error responses in cases where:

- Insufficient evidence is available to answer the question reliably.
- Internal components (e.g., data sources) are temporarily unavailable.

FR-28. The system SHOULD provide deterministic replay functionality, allowing the same query to be re-executed with the same configuration and data snapshot.

FR-29. The system SHOULD support batched queries under controlled conditions for performance testing and offline evaluation.

---

## 6. Open Items / Future Extensions

The following functional aspects are intentionally left as extension points for future iterations:

- Support for additional biomedical datasets beyond PubMed OA and ClinicalTrials.gov.
- Support for user feedback loops (e.g., rating answers, suggesting corrections) surfaced in the Researcher Portal.
- Advanced UI capabilities such as interactive evidence graphs, entity relationship visualizations, or timeline-based trial outcome comparisons.

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- FR-28 (deterministic replay) and FR-A3 (replay/reconstruction) are internally consistent within this document.
- Cross-document finding: `02-non-functional-requirements.md` NFR-A4 also defines replay/reconstruction expectations, and `06-qa-test-plan.md` covers replay only at the E2E level (section 3.3, step 4). There is no dedicated integration test for replay in the QA test plan. This gap must be closed.
- FR-21 correctly enumerates all three UI views (Researcher Portal, Operator Dashboard, Audit View) consistent with `03-architecture-and-tech-stack.md` section 4.7 and `04-data-model-and-governance.md` section 8.
- The SSE streaming requirement in FR-21a and FR (section 4.6) is consistent with the `POST /v1/query` + `GET /v1/query/stream` API definitions in `03-architecture` section 6.3.

**Gaps noted:**
- FR-28 (replay) is marked SHOULD, not SHALL. `02-NFR` NFR-A4 makes replay a MUST. This asymmetry is acceptable (FRD expresses user-level optionality; NFR enforces system-level obligation) but implementers must treat replay as a hard requirement per NFR-A4.
- No functional requirement explicitly enumerates RBAC roles and their permissions. This is addressed in `02-NFR` (NFR-S3, NFR-UI4) and `03-architecture` section 8, but role definitions are not exhaustive in any single document. The CTO flags this as a condition on `02-NFR` and `03-architecture`.

**Conditions:**
1. A dedicated replay integration test (covering FR-28/NFR-A4) must exist as a Phase 4 exit criterion. This is enforced in `docs/07-phased-development-plan.md` Phase 4 exit criteria.

**Phase gate:** Phase 1 (ingestion implementation), Phase 4 (agent orchestration implementation).


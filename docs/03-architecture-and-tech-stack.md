## 1. Architecture Overview

This document defines the target reference architecture and the technology stack for the Evidence-Based Bio-Medical Multi-Agent System.

The system is designed as a **self-hosted lakehouse + retrieval + feature store + multi-agent orchestration** platform:

- **Data foundation**: Spark ingestion into an Iceberg data lake backed by MinIO (S3-compatible).
- **AI context**: Embeddings indexed in a self-hosted vector database (Qdrant or Milvus).
- **AI features**: Structured statistical features computed and served via Feast.
- **Orchestration**: Two-layer orchestration:
  - **LangGraph** for stateful, deterministic multi-agent cognitive workflows.
  - **Temporal** for durable execution, retries, and infrastructure orchestration.
- **Observability**: Langfuse (or LangSmith if self-hosting is acceptable) + standard metrics/logs/tracing.

Auditability and transparency are first-class requirements across all layers.

---

## 2. Component Diagram (Conceptual)

### 2.1 Data plane

- **Sources**
  - PubMed Open Access Subset (bulk exports)
  - ClinicalTrials.gov (bulk exports)
- **Ingestion & curation**
  - Apache Spark jobs parse/normalize/deduplicate
  - Outputs written as Iceberg tables
- **Storage**
  - MinIO provides S3-compatible object store
  - Iceberg provides ACID tables and snapshots
- **Derived stores**
  - Feast offline store sourced from Iceberg-curated tables
  - Vector DB populated by embedding pipeline derived from curated literature/trials

### 2.2 Serving plane

- **Embedding service**
  - Produces embeddings for new/updated documents
  - Batch-oriented and/or incremental indexing
- **Vector retrieval service**
  - Provides semantic search APIs for domain agents (Librarian)
- **Feature service**
  - Feast online retrieval for numeric features (Biostatistician)
- **Agent API**
  - Exposes user query endpoint(s)
  - Runs LangGraph workflows wrapped in Temporal
  - Streams per-agent step events via Server-Sent Events for UI consumption
- **UI service** (`ui`)
  - Researcher Portal: question submission, real-time agent step progress, results with inline citations, evidence panel, statistics panel
  - Operator Dashboard: ingestion job status, trigger/reindex actions, DQ report viewer
  - Audit/Explainability View: execution timeline, evidence manifest viewer, replay button
  - Communicates exclusively via `agent-api` and `audit-api` REST/SSE endpoints

### 2.3 Control plane

- **Temporal**
  - Schedules and executes ingestion, indexing, feature computation, and research workflows
  - Provides workflow history and durable state
- **Observability**
  - Metrics: Prometheus-compatible
  - Dashboards: Grafana-compatible
  - Logs: structured logs + centralized collection
  - Traces: OpenTelemetry compatible
  - Agent traces: Langfuse (recommended for OSS/self-host)
- **Audit store**
  - Queryable store of evidence manifests and execution metadata (OSS/self-host)

---

## 3. Technology Stack (Recommended Defaults)

### 3.1 Core data stack

- **Apache Spark**: distributed ingestion and transformation.
- **MinIO**: object storage for lakehouse files.
- **Apache Iceberg**: table format for ACID transactions, schema evolution, snapshots.
- **Iceberg catalog: Project Nessie** (REST catalog). Rationale: fully OSS, self-hosted single container (`ghcr.io/projectnessie/nessie`), REST catalog compliant (Spark connects via `type=rest`), PostgreSQL-backed version store, includes a web UI, and provides Git-like branch/tag semantics that complement Iceberg snapshots. Backend: shared PostgreSQL instance, `nessie` database. Spark catalog config: `spark.sql.catalog.nessie.uri=http://nessie:19120/iceberg/`. *(CTO Condition 4 resolved — Phase 0 gate cleared.)*

### 3.2 Retrieval and features

- **Vector DB**: **Qdrant** (default) or Milvus (alternative).
- **Feature store**: **Feast**.
  - **Feast online store: Redis** (self-hosted, `redis:7`). Rationale: de-facto Feast online store for production, fully OSS, low-latency key-value lookup, already required by Langfuse for caching/queues (shared service). *(CTO Condition — `04-data-model` Phase 3 gate cleared.)*
  - **Feast offline store**: Iceberg (via Spark). Feast reads curated Iceberg tables as the offline source.
  - **Feast registry**: PostgreSQL (`feast_registry` database on the shared PostgreSQL instance).

### 3.3 Orchestration and agents

- **Temporal**: durable workflow orchestrator.
- **LangGraph**: cognitive-layer multi-agent state machine.
- **Python**: primary implementation language for agents and services.

### 3.5 UI

- **Streamlit** (default): Python-native, self-hosted, minimal operational overhead. Suitable for research and operator audiences.
- **Next.js** (alternative): preferred if a polished clinical-facing product UX is required.
- Both options are fully open-source and containerizable.
- The UI service exposes no direct data store access; it relies solely on `agent-api` and `audit-api`.

> **Decision (CTO gate resolved — Phase 5):** UI framework selection is deferred to Phase 5 start. The decision must be documented here before Phase 5 work begins (CTO Condition 2). Both options remain viable; Streamlit is the implementation default unless overridden.

### 3.4 Observability and auditability

- **Langfuse**: agent tracing (OSS/self-host).
- **OpenTelemetry**: traces and metrics plumbing.
- **Prometheus + Grafana**: metrics + dashboards (OSS/self-host).
- **Loki** (optional) for logs, or ELK/OpenSearch stack (OSS/self-host).

---

## 4. Service Boundaries (Proposed Microservices)

### 4.1 `ingestion-worker`

- Responsibilities:
  - Download and parse bulk sources (or read from a local staging folder).
  - Run Spark jobs (or submit to Spark) for parsing and curation.
  - Write raw and curated Iceberg tables.
- Orchestrated by:
  - Temporal scheduled workflows.

### 4.2 `feature-worker`

- Responsibilities:
  - Compute offline features from curated Iceberg tables.
  - Materialize Feast feature views.
  - Publish online features as required.

### 4.3 `embedding-worker`

- Responsibilities:
  - Generate embeddings for curated documents and trials.
  - Update vector DB indices.
  - Record indexing runs and versions for reproducibility.

### 4.4 `retrieval-api`

- Responsibilities:
  - Provide vector search endpoints with filtering support (time ranges, entity tags).
  - Return ranked passages with document identifiers and offsets/snippets.

### 4.5 `agent-api` (query gateway)

- Responsibilities:
  - Accept user questions and parameters.
  - Start Temporal workflow for a research run.
  - Provide synchronous response (best effort) or async job model depending on SLA.
  - Return final answer + evidence manifest + audit links.

### 4.6 `audit-api` (optional but recommended)

- Responsibilities:
  - Query and serve audit artifacts (evidence manifests, workflow metadata).
  - Provide operator views into “why” a response was returned or refused.

### 4.7 `ui` (web application)

- Responsibilities:
  - Serve the Researcher Portal, Operator Dashboard, and Audit/Explainability View.
  - Consume `POST /v1/query` (with SSE streaming) and `GET /v1/audit/{id}` from `agent-api`/`audit-api`.
  - Consume `POST /v1/ingest/run` and `GET /v1/ingest/status` for the Operator Dashboard.
  - Enforce role-based view access (Researcher vs. Operator).
- Default implementation: Streamlit app containerized in the Compose stack.

---

## 5. Orchestration Model

### 5.1 Two-layer orchestration

- **LangGraph**:
  - Implements the cognitive workflow:
    - Router → Librarian ↔ Biostatistician → Researcher ↔ Reviewer loop → final.
  - Maintains shared state including retrieved evidence and computed statistics.
  - Enforces deterministic state transitions.

- **Temporal**:
  - Wraps LangGraph execution as a durable workflow.
  - Handles retries, timeouts, backoff, and safe resumption.
  - Coordinates infrastructure workflows (ingestion, indexing, feature refresh).

### 5.2 Evidence manifest and claim mapping

Every research workflow MUST output an **evidence manifest** artifact containing:

- Execution metadata (workflow id, versions, timestamps).
- List of evidence items (documents, passages, vector query ids, feature keys/values).
- Mapping from answer sections (and/or atomic claims) to evidence references.

---

## 6. Data Contracts and Interfaces (High Level)

### 6.1 Data lake tables (Iceberg)

- `raw_pubmed_*`, `raw_clinicaltrials_*` (raw snapshots)
- `curated_articles`, `curated_trials` (normalized)
- `curated_entities`, `curated_relationships` (optional)
- `feature_inputs_*` (inputs to Feast pipelines)

### 6.2 Vector DB collections

- `articles_abstracts`
- `articles_methods`
- `trials_descriptions`

Each vector record MUST include:

- Stable document identifiers (PubMed ID / Trial ID)
- Text offsets or snippet hashes
- Dataset snapshot reference and indexing run id

### 6.3 APIs

- `POST /v1/query`: submit a research question, returns answer + citations + evidence manifest id
- `GET /v1/query/stream`: SSE endpoint — streams per-agent step events for real-time UI progress
- `GET /v1/audit/{id}`: retrieve audit artifact (manifest, workflow summary)
- `POST /v1/ingest/run`: trigger ingestion workflow (operator only)
- `GET /v1/ingest/status`: ingestion status

Exact schemas are defined in implementation and QA contract tests.

---

## 7. Deployment Artifacts

### 7.1 Docker Compose

The repository MUST include Docker Compose configurations for:

- MinIO + required buckets/policies
- Iceberg catalog (choice depends on implementation: e.g., REST catalog or metastore)
- Spark (master/worker or local mode container)
- Temporal server + UI + persistence DB
- Vector DB (Qdrant/Milvus)
- Feast components (registry + online store as configured)
- Langfuse + dependencies (if used)
- Application services (agent-api, retrieval-api, workers)
- **`ui` service** (Streamlit or Next.js container, bound to internal network, exposed on a configured port)

### 7.2 Configuration management

- Versioned configuration files for:
  - Ingestion schedules
  - Indexing schedules
  - Model/embedding versions
  - Feature definitions
  - Agent workflow configuration and policies (timeouts, max retries, refusal thresholds)

---

## 8. Security and Access Model (High Level)

- Internal network by default, explicit expose only for required endpoints.
- RBAC for operator endpoints, audit endpoints, and service credentials.
- Secret injection at runtime; no secrets in Git.

---

## 9. Principal Developer Agent Work Split (Dependencies and Isolation)

### 9.1 Workstreams

- **Dev A – Lakehouse ingestion**:
  - Spark parsing jobs, Iceberg table definitions, MinIO integration, ingestion workflow in Temporal.
- **Dev B – Feature store**:
  - Feast entities/features, offline/online stores, feature computation workflows.
- **Dev C – Embeddings + vector DB**:
  - Embedding pipeline, collection schemas, retrieval service APIs, indexing workflows.
- **Dev D – Multi-agent orchestration**:
  - LangGraph graphs and state schema, Temporal wrapper workflows, evidence manifest production.
- **Dev E – API + UI + audit surface**:
  - Query API (including SSE streaming endpoint), audit API, auth/RBAC, operator endpoints, docs and examples.
  - UI service: Researcher Portal, Operator Dashboard, Audit/Explainability View (Streamlit default).

### 9.2 Dependency notes

- Dev A unblocks Dev B (feature inputs) and Dev C (curated text).
- Dev C can prototype with a small curated sample dataset while Dev A scales ingestion.
- Dev D can prototype with mocked retrieval/feature interfaces; then integrate as Dev B/C stabilize APIs.
- Dev E integrates last-mile contracts and exposes stable interfaces for QA end-to-end.

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- Section 6.3 defines `POST /v1/query` (returns answer + citations + evidence manifest id) and `GET /v1/query/stream` (SSE endpoint). Cross-document finding: `04-data-model-and-governance.md` section 8.1 defines the SSE agent step event schema as `{ "agent": "<role>", "status": "started|completed|error", "summary": "<text>" }`. This schema is defined in `04-data-model` rather than in `03-architecture` section 6.3 where the endpoint contract lives. The canonical definition must live in one place. **Resolution**: section 6.3 of this document must be updated to include the full SSE event schema before Phase 4 implementation begins. Until then, `04-data-model` section 8.1 is the normative reference.
- Section 3.5 (UI) and section 4.7 (`ui` service) both list Streamlit as default and Next.js as alternative, consistent with `02-NFR` NFR-UI1. The choice remains open but must be resolved before Phase 5 begins.
- Section 8 (Security and Access Model) references RBAC for operator endpoints and audit endpoints but does not define role names or permission sets. This is inconsistent with `02-NFR` NFR-S3 (which requires RBAC) and NFR-UI4 (which mentions Researcher vs. Operator roles). The role/permission matrix must be added here.
- The two-layer orchestration model (section 5.1: LangGraph + Temporal) is consistent with `01-FR` FR-16–18 and `02-NFR` NFR-R1–R2.
- Evidence manifest contract (section 5.2) is consistent with `04-data-model` section 7 and `01-FR` FR-A2.

**Gaps noted:**
- Section 6.3 API list is high-level ("exact schemas defined in implementation and QA contract tests"). For the SSE stream specifically, the schema in `04-data-model` section 8.1 must be cross-referenced or moved here to avoid drift.
- Section 8 lacks a role/permission matrix. This gap leaves RBAC underspecified for implementers.
- No explicit Iceberg catalog choice is made (noted as open question in `04-data-model` section 9). This must be resolved before Phase 0 infrastructure work begins.

**Conditions:**
1. SSE event schema must be canonicalized in section 6.3 of this document before Phase 4 implementation of the streaming endpoint begins.
2. UI framework decision (Streamlit vs. Next.js) must be documented in section 3.5 before Phase 5 begins.
3. RBAC role names and permission sets must be added to section 8 before Phase 5 begins (satisfying Condition 3 of `02-NFR` sign-off).
4. Iceberg catalog choice must be decided and documented before Phase 0 begins.

**Phase gate:** Phase 0 (infrastructure), Phase 2 (vector retrieval), Phase 3 (feature store), Phase 4 (multi-agent orchestration).


## 1. Overview

This Non-Functional Requirements Document (NFRD) defines the production-grade qualities the Evidence-Based Bio-Medical Multi-Agent System MUST satisfy.

Constraints from the project charter:

- **100% free** and **open-source** stack.
- **Self-hosted only**. No proprietary cloud managed services (e.g., AWS MSK, Snowflake, Databricks).
- **Production-grade** reliability, observability, and security for a public GitHub repository.

---

## 2. Non-Negotiable NFR: Auditability and Transparency

NFR-A1. The system MUST provide **end-to-end auditability** for every user query and every background workflow, including:

- Workflow ID, timestamps, and versioned configuration.
- Full agent execution traces (routing decisions, tool calls, retries, timeouts).
- Full evidence provenance (document IDs, snippets, vector search results, feature store lookups, dataset snapshots).
- Intermediate agent artifacts that materially influence outputs.

NFR-A2. Audit records MUST be **operator-accessible** via:

- Temporal workflow history,
- Application logs,
- Agent tracing system (Langfuse/LangSmith),
- And a queryable audit store (exact storage implementation is an architectural choice, but must be open-source and self-hosted).

NFR-A3. Audit trails MUST be **tamper-evident**:

- Logs/traces MUST be write-once or cryptographically integrity-protected.
- Access to audit records MUST be controlled via RBAC.

NFR-A4. The system MUST support **replay/reconstruction**:

- Given the same dataset snapshot(s) and configuration, an operator can re-run a workflow to reproduce materially consistent results.
- Non-deterministic components (LLMs, embeddings) must be constrained via version pinning and configuration capture; when true determinism is not possible, the system must record enough context to justify outcomes and bound variability.

NFR-A5. The system MUST provide **explainable refusals**:

- If the system cannot answer safely, it must return a structured refusal describing missing evidence, data gaps, or failed validations, and this refusal must be auditable like any other output.

---

## 3. Reliability and Durability

NFR-R1. The system MUST use durable workflow orchestration (Temporal) for:

- Data ingestion and curation pipelines,
- Feature computation pipelines,
- Vector index refresh pipelines,
- Multi-agent research workflows.

NFR-R2. Workflows MUST be resilient to partial failures:

- Automatic retries with backoff and max attempts,
- Idempotent activity execution,
- Safe resumption after worker restarts or host crashes.

NFR-R3. The system MUST degrade safely:

- If retrieval or feature store is unavailable, the system must fail closed for evidence-based responses (refusal/fallback), not hallucinate.

NFR-R4. The system MUST provide backup/restore procedures for all persistent stores:

- Data lake storage (MinIO/Iceberg metadata),
- Vector database,
- Feature store stores (offline/online),
- Temporal persistence,
- Audit store.

NFR-R5. The system MUST define SLOs and error budgets (initial targets, adjustable as the system matures):

- Query workflow success rate,
- Time-to-first-token and time-to-final-answer,
- Ingestion pipeline completion rate and latency,
- Data quality violation rate.

---

## 4. Performance and Scalability

NFR-P1. The ingestion and curation pipeline MUST support bulk processing at scale (Spark), with the ability to:

- Process very large PubMed OA and ClinicalTrials.gov datasets,
- Scale horizontally where hardware allows (local cluster / bare-metal).

NFR-P2. Retrieval operations MUST be performant under load:

- Vector search latency must be measured and monitored (P50/P95/P99).
- Index rebuild times must be tracked and bounded.

NFR-P3. Feature computation MUST be batch scalable:

- Offline feature computation should be scheduled and monitored,
- Online feature lookup latency must be measured and monitored.

NFR-P4. The system MUST include performance tests that:

- Measure ingestion throughput,
- Measure query throughput and latency under concurrency,
- Identify bottlenecks in vector DB, feature store, and orchestration.

---

## 5. Security

NFR-S1. The system MUST be deployable in a secure-by-default posture:

- Components bound to internal networks by default,
- TLS supported for external exposure,
- Default credentials must be prohibited in production mode.

NFR-S2. Secrets MUST be handled securely:

- No secrets committed to the repository,
- Secret injection via environment variables or a self-hosted secret manager,
- Key rotation procedures documented.

NFR-S3. Access control MUST be enforced:

- RBAC for MinIO buckets, Temporal UI/APIs, vector DB, feature store, and the application API,
- Principle of least privilege for internal service accounts.

NFR-S4. Supply chain security MUST be practiced:

- Dependency pinning (lock files),
- SBOM generation (open-source tool),
- Container image scanning (open-source tool),
- Signed releases recommended (open-source tooling).

---

## 6. Observability

NFR-O1. The system MUST provide unified observability across services:

- **Metrics**: ingestion throughput, workflow counts, error rates, queue/backlog sizes, resource usage.
- **Logs**: structured JSON logs with correlation IDs.
- **Traces**: request and workflow traces including per-agent spans.

NFR-O2. Agent observability MUST include:

- LangGraph state transitions,
- Per-agent inputs/outputs,
- Retrieval queries and results,
- Feature store queries and returned values,
- Reviewer rejection reasons.

NFR-O3. The system MUST provide alerting hooks for:

- Workflow failures exceeding thresholds,
- Ingestion lag,
- Data quality violations above thresholds,
- Elevated latency or error rates.

---

## 7. Data Integrity and Governance

NFR-D1. The data lake MUST provide ACID guarantees for curated tables (Iceberg).

NFR-D2. The system MUST prevent duplicate or corrupted records through:

- Idempotent ingestion design,
- Strong validation rules,
- Snapshot isolation and rollback via table snapshots.

NFR-D3. The system MUST maintain lineage:

- Raw → curated → derived/feature tables,
- Pipeline versions and configuration captured per run.

---

## 8. Maintainability and Delivery

NFR-M1. The system MUST be fully containerized and runnable via Docker Compose on bare-metal Linux.

NFR-M2. The repository MUST include:

- Clear bootstrap instructions,
- Local development environment setup,
- Runbooks for common operations and incident response.

NFR-M3. Continuous integration MUST run:

- Linting and formatting,
- Unit tests,
- Critical integration tests (can be a reduced “smoke” subset for PRs, with a full suite in nightly runs).

NFR-M4. Testing requirements:

- Target **≥ 80% unit test coverage** for business logic and safety-critical components.
- Integration tests for cross-service boundaries.
- End-to-end tests for the full query pipeline.

---

## 9. User Interface

NFR-UI1. The UI MUST be implemented using an open-source, self-hostable framework. Recommended default: **Streamlit** (Python-native, low operational overhead). A **Next.js** frontend is an acceptable alternative if a richer clinical UX is prioritized.

NFR-UI2. The UI MUST communicate exclusively via the existing `agent-api` and `audit-api` REST endpoints — it MUST NOT access internal data stores (Iceberg, vector DB, feature store) directly.

NFR-UI3. The Researcher Portal MUST support real-time agent step progress updates via **Server-Sent Events (SSE)** from `agent-api`, displaying each agent transition (CMO → Librarian → Biostatistician → Researcher → Reviewer) as it occurs.

NFR-UI4. The UI MUST enforce the same RBAC rules as the underlying APIs:

- Researcher Portal: available to Researcher User role.
- Operator Dashboard and Audit View: restricted to Operator role.

NFR-UI5. The UI MUST NOT cache or persist raw query responses or evidence locally beyond the active browser session. Persistent audit artifacts are owned by the `audit-api`.

NFR-UI6. Page load and initial render times for the Researcher Portal MUST be measured and monitored (target: first meaningful paint < 2s on local network). Evidence panel expansions must not block the primary answer view.

NFR-UI7. The UI MUST be runnable as a Docker Compose service alongside the rest of the stack with no external dependencies.

---

## 10. Compliance and Licensing

NFR-C1. The system MUST respect dataset licensing terms and record source attribution.

NFR-C2. Any included third-party open-source components MUST:

- Have compatible licenses,
- Be documented with attribution,
- Have version pinning and security scanning.

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- NFR-A4 (replay/reconstruction) is consistent with FR-A3 and FR-28 in `01-functional-requirements.md`. Cross-document finding: `06-qa-test-plan.md` covers replay only at E2E level. A dedicated integration test is required (see Conditions).
- NFR-S3 references RBAC for MinIO, Temporal, vector DB, feature store, and the application API. Cross-document finding: neither this document nor `03-architecture-and-tech-stack.md` enumerates the actual role names (e.g., `researcher`, `operator`) and their specific permission sets exhaustively. The closest enumeration is NFR-UI4 (Researcher Portal vs. Operator Dashboard access split). A complete role/permission matrix must be defined in `03-architecture` section 8 before Phase 5 begins.
- NFR-UI1 names Streamlit as default and Next.js as alternative but defers the decision. This is a recognized open item tracked as a Phase 5 gate in `docs/07-phased-development-plan.md`.
- NFR-UI3 (SSE from `agent-api`) and NFR-UI4 (RBAC on UI) are consistent with `03-architecture` sections 4.5, 4.7, and 6.3.
- Performance targets (NFR-P2 P95 vector search, NFR-R5 SLOs) do not yet have concrete numeric values. These must be defined before Phase 6 load tests can have a pass/fail criterion.

**Gaps noted:**
- No SLO numeric values are defined for NFR-R5 (query success rate, P95 latency targets, ingestion completion rate). Without concrete numbers, Phase 6 load test exit criteria cannot be verified. These values must be documented before Phase 6 begins.
- RBAC role/permission matrix is absent — addressed as a Condition below.

**Conditions:**
1. A dedicated replay integration test covering NFR-A4 must exist as a Phase 4 exit criterion (enforced in `07-phased-development-plan.md`).
2. Concrete SLO numeric targets (P95 latency, query success rate, ingestion rate) must be documented in this document or in `03-architecture` before Phase 6 begins.
3. RBAC role names and permission sets must be exhaustively defined in `03-architecture-and-tech-stack.md` section 8 before Phase 5 begins.

**Phase gate:** Phase 4 (multi-agent orchestration), Phase 6 (production hardening).


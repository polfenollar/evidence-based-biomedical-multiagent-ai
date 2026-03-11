## Evidence-Based Bio-Medical Multi-Agent System – Phased Development Plan

This document is the primary artifact of the CTO agent. It defines the incremental delivery roadmap, with each phase producing a functional, testable slice of the system. No phase begins until the CTO has signed off the documents that gate it.

---

## Guiding Principles

- **No "big bang" delivery**: each phase must be independently runnable and testable before the next phase begins.
- **Exit criteria are hard gates**: a phase is not complete until every listed criterion is verifiably satisfied.
- **Infrastructure before application code**: Phase 0 must be stable before any application service is written.
- **Owner accountability**: each phase has a named owner responsible for delivery and for resolving blockers.
- **Hybrid structure — parallel horizontal tracks + integration spike**: Phases 2 and 3 run in parallel after Phase 1. Phase 1 exits with a thin end-to-end smoke test that validates inter-service contracts early, before full agent implementation begins. This combines the team-specialization benefit of horizontal layers with the contract-validation benefit of vertical slices. Throwaway stub code is minimized: the smoke test wires one real path through real data, not a fake data layer.

---

## Phase 0 – Infrastructure Baseline

**Owner:** All devs (bootstrapping responsibility)
**Gated by docs:** `03-architecture-and-tech-stack.md` (CTO sign-off required before Phase 0 begins)

**What:**
Bring the full Docker Compose stack to a healthy, scripted, idempotent state:

- MinIO (object storage)
- Iceberg REST catalog (or equivalent metastore)
- Temporal server + UI + persistence database
- Qdrant (vector DB)
- Feast registry + online store
- Langfuse + dependencies
- Prometheus + Grafana (skeleton dashboards)

No application code (no ingestion-worker, feature-worker, embedding-worker, agent-api, etc.). Infrastructure services only.

**Testable exit criteria:**

- [ ] Health check smoke tests pass for all 8+ infrastructure services (scripted, repeatable).
- [ ] MinIO bucket creation is scripted and idempotent (re-running does not error or duplicate).
- [ ] Temporal UI is reachable; a no-op workflow can be registered and executed via CLI or test.
- [ ] Iceberg catalog responds to schema creation and table listing calls.
- [ ] Qdrant collection creation API responds correctly.
- [ ] Feast registry initializes without errors against the running infrastructure.
- [ ] Prometheus scrape targets are configured; Grafana loads without errors.
- [ ] `docker compose up` from a clean state reaches healthy status within a documented time bound.

**Unblocks:** Phase 1

---

## Phase 1 – Data Ingestion & Lake Foundation

**Owner:** Dev A
**Gated by docs:** `01-functional-requirements.md`, `04-data-model-and-governance.md`, `05-data-quality-rules.md` (CTO sign-off required before Phase 1 begins)
**Depends on:** Phase 0 complete

**What:**
Implement the ingestion pipeline end-to-end for a representative sample:

- `ingestion-worker`: parsers for PubMed OA sample + ClinicalTrials.gov sample.
- Spark jobs write raw (`raw_pubmed_articles`, `raw_clinicaltrials_studies`) and curated (`curated_articles`, `curated_trials`) Iceberg tables.
- DQ block and warn rules enforced (per `05-data-quality-rules.md`).
- Temporal ingestion workflow scheduled and producing run metadata.

**Testable exit criteria:**

- [ ] Unit tests for PubMed and ClinicalTrials parsers achieve ≥ 80% coverage.
- [ ] DQ block rules reject synthetic corrupt inputs (null PMID, null NCT ID, missing provenance metadata); pipeline marks workflow failed with auditable DQ report.
- [ ] Integration test: Spark job writes Iceberg tables; snapshot IDs are queryable via Spark SQL.
- [ ] Temporal workflow completes for the sample dataset and records run metadata (run ID, pipeline version, timestamps).
- [ ] Operator can query `raw_pubmed_articles` and `curated_articles` via Spark SQL and verify record counts match expected sample.
- [ ] DQ report artifact emitted per run (per DQ-REP-1).
- [ ] Ingestion metadata fields (`source_name`, `source_version`, `ingestion_run_id`, `pipeline_version`, `ingested_at`, `source_uri`) present on all curated records (DQ-P1).
- [ ] **Integration smoke test passes** (contract validation spike): using real Iceberg curated data, a stub retrieval function (returns a hardcoded ranked passage list with valid PMID and snapshot reference), and a stub single-agent call (returns a hardcoded answer + citation), `POST /v1/query` returns a JSON response that includes a non-empty citations list and a valid `evidence_manifest_id` referencing a stored artifact. This test does not assert answer quality — it asserts that the data → API contract is wired correctly end-to-end and that snapshot references flow from Iceberg through the response. Stubs are replaced by real implementations in Phases 2–4.

**Unblocks:** Phase 2 and Phase 3 (both start immediately after Phase 1 exits — see parallel track note below)

---

## Phases 2 & 3 – Parallel Tracks (start together at Phase 1 exit)

> Phases 2 and 3 have no dependency on each other. Both depend only on Phase 1 (curated Iceberg tables). Dev C and Dev B start simultaneously the day Phase 1 exits. Each track replaces one stub from the Phase 1 smoke test with a real implementation. Phase 4 begins only when **both** tracks are complete.

---

## Phase 2 – Vector Retrieval *(parallel with Phase 3)*

**Owner:** Dev C
**Gated by docs:** `03-architecture-and-tech-stack.md`, `04-data-model-and-governance.md` (CTO sign-off required before Phase 2 begins)
**Depends on:** Phase 1 complete (curated articles and trials available)
**Runs in parallel with:** Phase 3

**What:**

- `embedding-worker`: generates embeddings for curated articles and trials.
- Qdrant collections populated (`articles_abstracts`, `articles_methods`, `trials_descriptions`).
- `retrieval-api` live with semantic search endpoint, filter support (date range, entity tag), and ranked result output.
- Each vector record includes: stable identifier, snippet reference, embedding model version, indexing run ID, dataset snapshot reference (per DQ-VEC-1).

**Testable exit criteria:**

- [ ] Unit tests for embedding pipeline achieve ≥ 80% coverage.
- [ ] Integration test: embed 100 curated documents → write to Qdrant → query returns ranked results with PMID/NCT metadata and snapshot reference.
- [ ] `retrieval-api` contract tests: date range filter returns only records within range; entity tag filter returns only matching records.
- [ ] Indexing run ID and Iceberg snapshot reference are recorded in every vector record (DQ-VEC-1).
- [ ] Index drift metrics emitted (fraction without embeddings, stale embedding rate — DQ-VEC-2).
- [ ] Smoke test updated: stub retrieval function replaced by real `retrieval-api` call; smoke test still passes end-to-end with real ranked results.

**Unblocks:** Phase 4 (Librarian agent needs retrieval-api — both Phase 2 and Phase 3 must be complete)

---

## Phase 3 – Feature Store *(parallel with Phase 2)*

**Owner:** Dev B
**Gated by docs:** `03-architecture-and-tech-stack.md`, `04-data-model-and-governance.md`, `05-data-quality-rules.md` (CTO sign-off required before Phase 3 begins)
**Depends on:** Phase 1 complete (curated Iceberg tables available as feature inputs)
**Runs in parallel with:** Phase 2

**What:**

- `feature-worker`: computes entity-level statistics (co-occurrence frequencies, trial outcome distributions) from curated Iceberg tables.
- Feast offline store and online store materialized.
- Feature lookup service live.
- Every feature value includes: Iceberg snapshot reference, feature view definition version, pipeline run ID (per DQ-FEAST-1).

**Testable exit criteria:**

- [ ] Unit tests for feature computation functions achieve ≥ 80% coverage.
- [ ] Integration test: curated Iceberg tables → Feast offline store → online materialization → feature lookup returns correct values with feature view version and snapshot reference.
- [ ] Feature freshness metrics emitted; staleness alert fires in a controlled test scenario (DQ-FEAST-3).
- [ ] DQ-FEAST rules pass on feature registry: numeric features have units/semantic definitions and null-handling documented (DQ-FEAST-2).
- [ ] Temporal feature-refresh workflow completes and records run metadata.
- [ ] Smoke test updated: stub single-agent call now performs a real feature store lookup for one entity; smoke test still passes end-to-end with real feature values in the response.

**Unblocks:** Phase 4 (Biostatistician agent needs feature store — both Phase 2 and Phase 3 must be complete)

---

## Phase 4 – Multi-Agent Integration

**Owner:** Dev D
**Gated by docs:** `01-functional-requirements.md`, `02-non-functional-requirements.md`, `03-architecture-and-tech-stack.md` (CTO sign-off required before Phase 4 begins)
**Depends on:** Phase 2 complete (retrieval-api live), Phase 3 complete (feature store live)

> **Framing**: Phase 4 is an *integration* phase, not a greenfield build. The smoke test from Phase 1 (iteratively updated in Phases 2–3) already proves the `POST /v1/query` → data path works with real retrieval results and real feature values. Dev D's job is to replace the remaining stub single-agent call with the full LangGraph graph and Temporal wrapper. Inter-service contracts have already been validated; integration risk is concentrated on the orchestration logic itself.

**What:**

- Replace stub single-agent with the full LangGraph cognitive workflow: CMO Router → Medical Librarian → Clinical Biostatistician → Lead Researcher → Peer Reviewer loop → final answer.
- Add Temporal wrapper workflow providing durable execution, retries, and workflow history.
- Complete evidence manifest produced per query run (per `03-architecture` section 5.2) — smoke test already validated the manifest id flows; Phase 4 completes the manifest content.
- `agent-api` `POST /v1/query` fully live (API-only; no UI yet).
- Structured refusal/fallback when evidence is insufficient (FR-A4, NFR-A5).

**Testable exit criteria:**

- [ ] Unit tests for each agent node with mocked retrieval and feature interfaces achieve ≥ 80% coverage.
- [ ] Integration test: LangGraph graph runs with real `retrieval-api` and feature store on golden dataset; answer includes citations.
- [ ] E2E test: `POST /v1/query` returns structured answer + citations list + `evidence_manifest_id` (DQ-UI-1).
- [ ] Evidence manifest resolves to real snapshot-backed records (every evidence item has stable doc ID and snapshot reference).
- [ ] Peer Reviewer correctly rejects a synthetic answer containing unsupported claims (returns structured refusal, not a partial answer).
- [ ] Temporal workflow history is queryable; replay of the same query against the same snapshot produces materially consistent results (FR-28, NFR-A4).
- [ ] Dedicated replay integration test exists covering FR-28/NFR-A4 (CTO condition — see sign-off on `01-FR` and `02-NFR`).
- [ ] SSE endpoint `GET /v1/query/stream` emits correctly formed agent step events per the schema in `03-architecture` section 6.3 (see CTO condition in `03-architecture` sign-off).

**Unblocks:** Phase 5

---

## Phase 5 – Audit API & UI

**Owner:** Dev E
**Gated by docs:** `01-functional-requirements.md`, `03-architecture-and-tech-stack.md` (UI framework decision documented), `04-data-model-and-governance.md` (CTO sign-off required before Phase 5 begins)
**Depends on:** Phase 4 complete

**What:**

- `audit-api` `GET /v1/audit/{id}`: serves full evidence manifest and execution timeline for any Phase 4 query run.
- SSE streaming endpoint `GET /v1/query/stream` (if not fully live after Phase 4, completed here).
- `ui` service (Streamlit default, or Next.js if chosen — **UI framework decision must be documented before Phase 5 begins**; see CTO condition on `03-architecture` sign-off):
  - Researcher Portal: question submission, real-time agent step progress, structured answer with inline citation badges, evidence panel, statistics panel, "View Audit Trail" link.
  - Operator Dashboard: ingestion job status table, trigger/reindex actions, DQ report viewer.
  - Audit/Explainability View: execution timeline, evidence manifest viewer, replay button.
- RBAC enforced: Operator Dashboard restricted to Operator role (NFR-UI4, NFR-S3).
- DQ-UI rules enforced at `agent-api` boundary (see CTO condition on `05-DQ` sign-off — contract test for split ownership required).

**Testable exit criteria:**

- [ ] `audit-api` returns full evidence manifest and execution timeline for any Phase 4 query run.
- [ ] UI component tests: citation badge rendering, evidence panel expansion, SSE step progress (5 agent labels in order), refusal display, Operator Dashboard table, Audit View timeline.
- [ ] Playwright E2E: submit golden-dataset question → all 5 agent steps visible during SSE streaming → structured answer with citations → navigate to Audit View → evidence manifest items listed and clickable.
- [ ] RBAC tests: Operator Dashboard returns 403/redirect for Researcher-role sessions.
- [ ] DQ-UI contract tests: mock `agent-api` returning response missing citations → UI renders error, not blank view (DQ-UI-1); malformed SSE event → UI skips without crashing (DQ-UI-3).
- [ ] UI container runs in Compose stack (`docker compose up`) with no external dependencies.
- [ ] UI framework decision documented in `03-architecture-and-tech-stack.md` before Phase 5 starts (CTO gate).

**Unblocks:** Phase 6

---

## Phase 6 – Production Hardening

**Owner:** All devs + QA
**Gated by docs:** `06-qa-test-plan.md` (CTO sign-off required before Phase 6 begins)
**Depends on:** Phase 5 complete

**What:**
Bring the full system to production-grade quality:

- Full observability: Grafana dashboards for SLO metrics (query success rate, ingestion rate, DQ violation rate), Langfuse agent traces configured end-to-end.
- Load tests: sustained query throughput meeting P95 latency target (NFR-P2, NFR-P4).
- Chaos/resilience tests: all 5 kill/restart scenarios (agent worker, retrieval-api, vector DB, feature service, Temporal worker).
- UI resilience: SSE drop → error state; `audit-api` down → degraded-mode warning (DQ-UI-5).
- Security hardening: RBAC audit, TLS configuration, secret scanning, no critical CVEs in shipped images.
- SBOM generated and committed (NFR-S4).
- Runbooks for common operations and incident response (NFR-M2).

**Testable exit criteria:**

- [ ] Load test: sustained query throughput meets P95 latency target defined in `02-non-functional-requirements.md` (NFR-P2).
- [ ] Chaos tests: all 5 kill/restart scenarios recover cleanly (workflows complete or produce auditable failure artifact; no silent data corruption).
- [ ] UI resilience: SSE drop → UI displays connection error (not frozen indicator); `audit-api` down → UI shows degraded-mode warning per DQ-UI-5.
- [ ] Container image scan: no critical CVEs in shipped images (NFR-S4).
- [ ] SBOM generated and committed to repository.
- [ ] All QA release blockers from `06-qa-test-plan.md` section 2.1 satisfied.
- [ ] Grafana dashboards show SLO metrics for: query success rate, ingestion rate, DQ violation rate (NFR-O1, NFR-R5).
- [ ] Langfuse traces capture per-agent spans for a complete query workflow (NFR-O2).
- [ ] Runbooks exist for: ingestion failure, agent workflow failure, vector DB recovery, feature store staleness, and UI/API restart.

---

## Phase Summary Table

| Phase | Name | Owner | Key Deliverable | Runs with | Unblocks |
|-------|------|-------|-----------------|-----------|---------|
| 0 | Infrastructure Baseline | All | Full Compose stack healthy | — | 1 |
| 1 | Data Ingestion & Lake Foundation | Dev A | Iceberg tables + Temporal ingestion + E2E smoke test | — | 2 ∥ 3 |
| 2 | Vector Retrieval | Dev C | Qdrant + retrieval-api; smoke test stub replaced | ∥ Phase 3 | 4 |
| 3 | Feature Store | Dev B | Feast offline+online + lookup API; smoke test stub replaced | ∥ Phase 2 | 4 |
| 4 | Multi-Agent Integration | Dev D | Full LangGraph graph replaces stubs; Temporal wrapper; complete agent-api | — | 5 |
| 5 | Audit API & UI | Dev E | audit-api + UI service | — | 6 |
| 6 | Production Hardening | All + QA | Load/chaos/security/observability | — | — (release) |

---

## Document Gate Summary

| Phase start | Documents that must have CTO sign-off |
|-------------|---------------------------------------|
| Phase 0 | `03-architecture-and-tech-stack.md` |
| Phase 1 | `01-functional-requirements.md`, `04-data-model-and-governance.md`, `05-data-quality-rules.md` |
| Phase 2 | `03-architecture-and-tech-stack.md`, `04-data-model-and-governance.md` |
| Phase 3 | `03-architecture-and-tech-stack.md`, `04-data-model-and-governance.md`, `05-data-quality-rules.md` |
| Phase 4 | `01-functional-requirements.md`, `02-non-functional-requirements.md`, `03-architecture-and-tech-stack.md` |
| Phase 5 | `01-functional-requirements.md`, `03-architecture-and-tech-stack.md` (UI decision), `04-data-model-and-governance.md` |
| Phase 6 | `06-qa-test-plan.md` |

---

## CTO Sign-Off

**Status:** APPROVED

**Consistency review:**
This document was produced by the CTO agent after reviewing docs 00–06 in their entirety. The phase boundaries and exit criteria have been reconciled against all functional requirements (01), non-functional requirements (02), architecture contracts (03), data contracts (04), DQ rules (05), and QA gates (06). No contradictions with the phased plan were found.

**Gaps noted:**
- The document gate table above references the SSE event schema being canonicalized in `03-architecture` section 6.3 as a pre-condition for Phase 4 completion; this is tracked as a condition on the `03-architecture` sign-off.
- The UI framework decision (Streamlit vs. Next.js) is listed as a Phase 5 gate; it is tracked as a condition on the `03-architecture` sign-off.
- The dedicated replay integration test (FR-28/NFR-A4) is listed as a Phase 4 exit criterion; it is tracked as conditions on the `01-FR` and `02-NFR` sign-offs.
- DQ-UI rule enforcement split ownership (rules in `05-DQ`, enforced at `agent-api` boundary owned by Dev E) is tracked as a condition on the `05-DQ` sign-off.

**Conditions:** None. This document itself is self-consistent and does not block any phase start.

**Phase gate:** This document governs all phase boundaries; it is a prerequisite for implementation to begin on any phase.

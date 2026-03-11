## 1. Purpose

This document defines the QA strategy and test plan for the Evidence-Based Bio-Medical Multi-Agent System.

The goal is production-grade quality with a fail-closed safety posture for medical evidence synthesis.

Auditability and transparency are explicit testable requirements: every test that produces an output must also validate the correctness and completeness of its audit artifacts.

---

## 2. Quality Gates (Go/No-Go Criteria)

### 2.1 Release blockers (must be satisfied)

- **No critical defects** in ingestion, governance, retrieval, feature store, orchestration, API, or UI layers.
- **All “Block” data quality rules pass** for curated outputs used by agent workflows.
- **Evidence manifest correctness**:
  - Every final answer must include citations and an evidence manifest.
  - Evidence manifest entries must resolve to real snapshot-backed records.
- **Reliability**:
  - Workflows recover from common failures (worker restarts, transient timeouts) via Temporal.
  - No unhandled exceptions in critical paths.
- **Testing**:
  - ≥ 80% unit test coverage on business logic and safety-critical modules.
  - Integration test suite passes for core service boundaries.
  - End-to-end suite passes on a representative environment.

### 2.2 Non-blocking but tracked

- Performance targets are met or have documented mitigations and known bottlenecks.
- Observability dashboards exist for critical SLOs and workflows.

---

## 3. Test Types and Scope

### 3.1 Unit testing

- Targets:
  - Parsing and normalization functions.
  - Deduplication and key generation.
  - Evidence manifest generation and claim mapping logic.
  - Peer-review rejection logic (evidence insufficiency detection).
  - Feature calculation functions (where implemented outside Spark/SQL).
- Coverage target:
  - ≥ 80% for critical logic (as per NFR).

### 3.2 Integration testing

Critical integration boundaries:

- Spark ↔ Iceberg (writes produce expected table snapshots and schemas)
- Iceberg ↔ Feast (offline features computed and served correctly)
- Embedding worker ↔ Vector DB (index writes, query correctness)
- Retrieval API ↔ Vector DB (filters and rankings behave)
- LangGraph ↔ Retrieval/Feature interfaces (contracts)
- Temporal ↔ workers (retries, idempotency, failure recovery)

Each integration test MUST assert both:

- Functional correctness of the primary output, and
- Auditability artifacts (run metadata, snapshot references, trace links).

### 3.3 End-to-end (E2E) testing

E2E test flow:

1. Ingest a known, fixed small dataset snapshot (golden dataset).
2. Build/refresh:
   - curated tables,
   - embeddings and vector index,
   - features in Feast.
3. Run an agent query workflow.
4. Validate:
   - final answer format and refusal behaviors,
   - citations are present and resolvable,
   - evidence manifest maps answer sections/claims to evidence items,
   - workflow trace exists and is queryable,
   - replay/reconstruction works.
5. UI E2E validation (Playwright):
   - Submit the same golden-dataset question via the Researcher Portal.
   - Assert all five agent step indicators appear during SSE streaming.
   - Assert the final answer renders with at least one inline citation badge.
   - Navigate to the Audit View via "View Audit Trail" and assert evidence manifest items are listed.
   - Verify the Operator Dashboard reflects the ingestion run status from step 1.

### 3.4 Data quality testing

- Validate DQ rules using:
  - synthetic corrupted inputs (null ids, duplicate ids, invalid dates),
  - real samples with expected quirks.
- Ensure:
  - block rules fail the pipeline and quarantine correctly,
  - warnings are emitted as reports.

### 3.5 Performance testing

Performance tests MUST cover:

- **Ingestion throughput**:
  - records/sec for raw parsing and curated writes
  - time to complete a representative batch
- **Indexing throughput**:
  - embeddings/sec and index update time
- **Query latency**:
  - P50/P95/P99 for retrieval and full agent workflow
- **Resource usage**:
  - CPU, memory, disk, network I/O per component

### 3.6 Load testing

Load tests MUST cover:

- Sustained query load (concurrent users).
- Burst load patterns.
- Backpressure behavior (queueing in Temporal, request throttling).

### 3.7 UI testing

UI tests MUST cover all three views (Researcher Portal, Operator Dashboard, Audit/Explainability View).

**Component-level tests (unit/integration):**

- Query form validation: empty input, max-length, filter combinations.
- Citation badge rendering: verify each badge links to the correct PMID/NCT.
- Evidence panel expansion: assert snippets and source metadata render without blocking the answer view.
- SSE stream rendering: mock server emitting step events, assert each agent label appears in order.
- Refusal display: assert structured refusal reason fields are surfaced, not swallowed.
- Operator Dashboard table: assert run status, DQ counts, and trigger buttons render from mock API responses.
- Audit View timeline: assert agent steps render in chronological order with correct summaries.

**Browser E2E tests (against local Compose stack):**

- Submit a known golden-dataset question and assert:
  - All five agent step indicators appear during streaming.
  - Final answer has at least one inline citation.
  - "View Audit Trail" navigates to the Audit View with a resolvable manifest.
- Trigger an ingestion run from the Operator Dashboard and assert status updates.
- Open the Audit View for a completed query and assert the evidence manifest items are listed and clickable.

**Access control tests:**

- Assert Operator Dashboard and Audit View are not accessible to unauthenticated or Researcher-role sessions.

**DQ-UI rule validation tests:**

- Mock `agent-api` returning a response missing citations → assert UI renders an error, not a blank view.
- Mock `agent-api` returning a malformed SSE event → assert UI skips the event without crashing.

### 3.9 Resilience / chaos testing

Required failure-injection scenarios:

- Kill/restart:
  - an agent worker mid-run,
  - retrieval API,
  - vector DB container,
  - feature service,
  - Temporal worker.
- Simulate:
  - timeouts,
  - rate limiting,
  - corrupted partitions triggering DQ block rules.
- UI-specific resilience:
  - Kill `agent-api` mid-SSE stream → assert UI displays a connection error, not a frozen progress indicator.
  - Kill `audit-api` → assert Audit View shows a degraded-mode warning (per DQ-UI-5).

Expected outcomes:

- Temporal retries where applicable.
- Workflows either complete successfully or fail with an auditable refusal/error artifact.
- No silent data corruption; no uncited outputs.

---

## 4. Test Data Strategy

### 4.1 Golden datasets

Maintain small, versioned datasets for deterministic testing:

- A minimal PubMed OA sample set.
- A minimal ClinicalTrials.gov sample set.
- Expected derived features and expected retrieval outputs (where feasible).

### 4.2 Synthetic datasets

Generate:

- edge-case records (nulls, weird encodings, missing fields),
- duplicated records,
- contradictory records to test reviewer logic.

---

## 5. Auditability Validation Checklist (Required in Multiple Test Types)

For any workflow producing a user-facing response:

- A workflow execution id exists and is recorded.
- Configuration versions are recorded (agent policies, model versions, feature registry versions).
- Iceberg snapshot references are recorded.
- Vector index version / run id is recorded.
- Feature store lookups are recorded with keys and returned values.
- Evidence manifest exists, is machine-readable, and resolves to real evidence items.
- Replay/reconstruction of the workflow is possible or, if non-determinism remains, variability is bounded and justified by recorded context.

---

## 6. Tooling (Open Source / Self-Hosted)

- **Unit/integration tests**: `pytest` (or equivalent), coverage reporting.
- **Performance/load**: `k6` (HTTP load), `locust` (optional), `pytest-benchmark` (optional).
- **Chaos**: container kill/restart scripts and Temporal workflow-level failure injection.
- **UI component tests**: `pytest` with Streamlit testing utilities (if Streamlit) or `jest` + `@testing-library/react` (if Next.js).
- **UI E2E tests**: `playwright` (open-source, self-hosted) against the local Compose stack.
- **CI**: GitHub Actions (allowed), using open-source tooling only.

---

## 7. Reporting and Traceability

Every test run MUST produce artifacts:

- Summary report (pass/fail) with links to logs.
- Coverage reports.
- Performance metrics snapshots.
- For E2E tests: evidence manifest artifacts and workflow trace references.

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- Section 2.1 (release blockers) correctly references ≥ 80% unit test coverage consistent with `00-agents-overview.md` section 1.5, `01-FR` section 1.1, and `02-NFR` NFR-M4. Consistent across all four documents.
- Section 3.3 E2E step 4 includes "replay/reconstruction works" as a validation item, consistent with `01-FR` FR-28 and `02-NFR` NFR-A4. However, the replay item appears only at E2E level. Cross-document finding: FR-28 and NFR-A4 require replay capability; no dedicated integration test for replay exists at the integration test level (section 3.2). This is a gap identified independently from the `01-FR` and `02-NFR` sign-offs.
- Section 3.7 (UI testing) DQ-UI rule validation tests correctly reference the behavior expected by `05-data-quality-rules.md` DQ-UI-1 and DQ-UI-3. However, the tests reference behavior without tracing to DQ-UI rule IDs. This makes it harder to verify that all DQ-UI rules are covered.
- Section 3.9 (chaos testing) UI resilience scenarios (SSE drop, `audit-api` down) are consistent with `05-DQ` DQ-UI-5 and `02-NFR` NFR-R3. Consistent.
- Section 6 (tooling): Playwright for UI E2E is consistent with `03-architecture` approach. Pytest for unit/integration is consistent with Python as the primary language (`03-architecture` section 3.3).

**Gaps noted:**
- No dedicated replay integration test at the integration test level (section 3.2). Replay appears only in E2E (section 3.3). This gap was noted independently in the `01-FR` and `02-NFR` sign-offs.
- DQ-UI rule validation tests (section 3.7) lack explicit traceability to DQ-UI rule IDs. A test matrix mapping each DQ-UI rule ID (DQ-UI-1 through DQ-UI-5) to a specific test case should be added.
- Performance tests (section 3.5) lack concrete pass/fail thresholds (P95 latency targets, ingestion throughput minimums). These depend on SLO numeric values that are not yet defined in `02-NFR` NFR-R5. This is flagged as Condition 2 on the `02-NFR` sign-off.

**Conditions:**
1. A dedicated replay integration test must be added to section 3.2 covering the ability to re-run a workflow against the same snapshot and produce materially consistent results. This test must be a Phase 4 exit criterion (enforced in `docs/07-phased-development-plan.md`).
2. DQ-UI rule traceability matrix (DQ-UI-1 through DQ-UI-5 → test cases) must be added to section 3.7 before Phase 5 begins.
3. Concrete numeric pass/fail thresholds for performance tests (section 3.5) must be added once SLO values are defined in `02-non-functional-requirements.md` (per Condition 2 of that document's sign-off), before Phase 6 load tests run.

**Phase gate:** Phase 6 (production hardening — all release blockers in section 2.1 must be satisfied).


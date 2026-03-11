## 1. Purpose

This document defines data quality (DQ) rules and integrity checks for the Evidence-Based Bio-Medical Multi-Agent System.

These rules exist to ensure:

- **Correctness** and **integrity** of the governed data lake (Iceberg).
- **Reproducibility** through versioned snapshots and lineage metadata.
- **Auditability**: evidence used by agents is verifiable and traceable to data snapshots.
- **Safety**: the multi-agent system fails closed when evidence is insufficient or invalid.

---

## 2. Data Quality Framework

### 2.1 Rule categories

- **Schema rules**: required columns, data types, allowed enumerations.
- **Uniqueness rules**: deduplication keys, primary-key uniqueness in curated tables.
- **Validity rules**: date bounds, numeric ranges, identifier formats.
- **Consistency rules**: referential integrity across curated tables.
- **Completeness rules**: minimal required fields for downstream pipelines.
- **Timeliness rules**: freshness expectations for scheduled pipelines.
- **Provenance rules**: lineage and ingestion metadata presence.

### 2.2 Outcomes of rule evaluation

- **Fail (Block)**: pipeline must not publish to curated/derived outputs; record quarantined.
- **Warn (Quarantine subset)**: allow pipeline completion but quarantine specific records/partitions.
- **Info (Monitor)**: record metrics for trends but do not block.

---

## 3. Minimum Required Metadata (Provenance Rules)

DQ-P1 (Block). Every raw and curated record MUST include:

- `source_name`
- `source_version`
- `ingestion_run_id`
- `pipeline_version`
- `ingested_at`
- `source_uri` or `source_file_ref`

DQ-P2 (Block). Curated and derived tables MUST include a snapshot/version reference sufficient to:

- Identify the Iceberg table snapshot ID (or equivalent),
- Identify the transformation job version.

---

## 4. PubMed Open Access – Quality Rules

### 4.1 Raw tables

DQ-PUB-RAW-1 (Block). Raw PubMed records MUST contain a stable identifier (PMID or equivalent), and it MUST be non-null.

DQ-PUB-RAW-2 (Warn). `publication_date` parsing failures MUST be tracked; invalid dates should not block raw ingestion but must be quarantined for curation.

DQ-PUB-RAW-3 (Info). Track counts of missing abstracts, missing methods, missing full text.

### 4.2 Curated tables

DQ-PUB-CUR-1 (Block). In `curated_articles`, `pmid` MUST be unique.

DQ-PUB-CUR-2 (Block). `title` MUST be non-empty for curated articles.

DQ-PUB-CUR-3 (Warn). `abstract` SHOULD be present; missing abstracts are allowed but must be flagged for retrieval limitations.

DQ-PUB-CUR-4 (Block). Any curated section/snippet record MUST reference an existing curated article (referential integrity).

DQ-PUB-CUR-5 (Info). Maintain language distribution stats; flag unusually high non-English fractions.

---

## 5. ClinicalTrials.gov – Quality Rules

### 5.1 Raw tables

DQ-CT-RAW-1 (Block). Raw trial records MUST contain `nct_id` and it MUST be non-null.

DQ-CT-RAW-2 (Warn). Trials missing outcome data are allowed but must be flagged as limited for biostatistics.

### 5.2 Curated tables

DQ-CT-CUR-1 (Block). In `curated_trials`, `nct_id` MUST be unique.

DQ-CT-CUR-2 (Warn). `sample_size` SHOULD be present; if missing, flag as unknown and prevent numeric aggregation that assumes a value.

DQ-CT-CUR-3 (Block). Outcome records MUST reference an existing curated trial.

DQ-CT-CUR-4 (Info). Track distribution of trial statuses and flag unexpected spikes.

---

## 6. Cross-Domain Consistency Rules

DQ-X-1 (Warn). If entity extraction is enabled, extracted entities MUST reference the source document/trial record and the exact section/snippet used.

DQ-X-2 (Block). Any evidence snippet stored for retrieval MUST contain:

- stable identifier (PMID/NCT),
- section type,
- snippet text or snippet hash,
- dataset snapshot reference.

---

## 7. Feature Store Quality Rules (Feast)

DQ-FEAST-1 (Block). Every feature value MUST be traceable to:

- an Iceberg snapshot reference,
- the feature view definition version,
- and the pipeline run id producing it.

DQ-FEAST-2 (Block). Numeric features MUST include:

- units or clear semantic definition in the feature registry,
- null-handling behavior (e.g., unknown vs zero).

DQ-FEAST-3 (Warn). Feature freshness metrics MUST be recorded and alerts triggered on staleness.

---

## 8. Vector DB / Embedding Pipeline Quality Rules

DQ-VEC-1 (Block). Every vector record MUST include:

- stable identifier (PMID/NCT),
- snippet reference (offsets or snippet hash),
- embedding model version,
- indexing run id,
- dataset snapshot reference.

DQ-VEC-2 (Warn). Index drift should be monitored:

- fraction of documents without embeddings,
- stale embedding rate,
- distribution of vector norms (basic sanity check).

---

## 9. Data Quality Reporting

DQ-REP-1. Every pipeline run MUST emit a DQ report artifact containing:

- rule evaluations (pass/warn/fail) with counts and sample record ids,
- quarantined partitions/records,
- links to logs/traces,
- snapshot IDs and run metadata.

DQ-REP-2. DQ reports MUST be accessible to operators and referenced by:

- Temporal workflow runs,
- and the audit store.

---

## 10. UI Response Quality Rules

These rules govern the data contracts delivered to the UI service and must be validated at the `agent-api` boundary before any response is returned or streamed.

DQ-UI-1 (Block). Every query response delivered to the UI MUST include:

- At least one citation in the citations list.
- A non-empty `evidence_manifest_id` referencing a stored audit artifact.
- Structured answer sections (not a single opaque text blob).

DQ-UI-2 (Block). Every citation object in a query response MUST include:

- A non-null `id` (PMID or NCT ID).
- A `type` field with value `article` or `trial`.
- A non-empty `snippet`.

DQ-UI-3 (Block). SSE agent step events MUST include `agent`, `status`, and `summary` fields. Malformed events MUST NOT be forwarded to the UI.

DQ-UI-4 (Block). Refusal responses MUST include a structured `refusal_reason` with:

- Missing evidence types.
- The data gap or validation failure that triggered the refusal.
- This refusal MUST itself be stored as an auditable artifact.

DQ-UI-5 (Warn). If the audit artifact referenced by `evidence_manifest_id` cannot be retrieved within a defined timeout, the UI response MUST surface a degraded-mode warning rather than a silent failure.

---

## 11. Failure Policy (Fail-Closed)

DQ-FP-1. If any **Block** rule fails for a curated output, the pipeline MUST:

- prevent publishing corrupted curated tables,
- and mark the workflow as failed with an auditable DQ report.

DQ-FP-2. Domain agent workflows MUST refuse to answer when required evidence cannot be validated due to:

- missing snapshot references,
- missing provenance metadata,
- or failed DQ checks that invalidate evidence.

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- DQ-P1 (provenance fields) is consistent with `04-data-model` section 5.1 (ingestion metadata requirements). Fields listed match exactly. Consistent.
- DQ-X-2 (evidence snippet storage requirements) is consistent with `04-data-model` section 7 (document evidence item contract) and `03-architecture` section 6.2 (vector DB record requirements). Consistent across all three documents.
- DQ-FEAST-1 (feature traceability) is consistent with `04-data-model` section 7 (statistical evidence item contract) and `04-data-model` section 4.3 (snapshot reference requirements). Consistent.
- DQ-UI-1 through DQ-UI-5 (section 10): these rules govern data contracts delivered to the UI. Cross-document finding: the rules are defined here (owned by the Data Officer) but are enforced at the `agent-api` boundary, which is a service owned by Dev E. This creates a **split ownership** situation: the rule author (Data Officer / `05-DQ`) and the rule enforcer (Dev E / `agent-api`) are different parties. There is no contract test currently listed in `06-qa-test-plan.md` that explicitly references DQ-UI rules by ID and verifies them at the `agent-api` boundary as a separate concern from E2E tests. This is a gap.
- DQ-UI-5 (degraded-mode warning when `evidence_manifest_id` cannot be retrieved) is consistent with `06-qa-test-plan.md` section 3.9 (UI resilience: `audit-api` down → degraded-mode warning). Consistent.

**Gaps noted:**
- DQ-UI rules (section 10) are enforced at the `agent-api` boundary but owned by the Data Officer. No contract test in `06-qa-test-plan.md` is explicitly tied to DQ-UI rule IDs as a discrete test category. The QA plan's "DQ-UI rule validation tests" (section 3.7) covers this behaviorally but without traceability to the specific rule IDs. This gap should be closed by adding a DQ-UI contract test section to `06-qa-test-plan.md` or by explicitly cross-referencing DQ-UI rule IDs in the existing UI test section.
- Rule DQ-VEC-2 (index drift monitoring) does not specify alert thresholds. The thresholds should be defined here or in an operational runbook before Phase 6 begins.
- Rule DQ-FEAST-3 (feature freshness alerts) does not specify the staleness threshold that triggers the alert. This should be defined before Phase 3 begins.

**Conditions:**
1. DQ-FEAST-3 staleness threshold must be defined before Phase 3 begins.
2. A contract test explicitly validating DQ-UI rules at the `agent-api` boundary (with DQ-UI rule ID traceability) must be included in the Phase 5 exit criteria. This is enforced in `docs/07-phased-development-plan.md` Phase 5 exit criteria.

**Phase gate:** Phase 1 (DQ-P1, DQ-PUB-*, DQ-CT-* rules gate ingestion), Phase 2 (DQ-VEC-* rules gate embedding pipeline), Phase 3 (DQ-FEAST-* rules gate feature store), Phase 5 (DQ-UI-* rules gate UI/agent-api contract).


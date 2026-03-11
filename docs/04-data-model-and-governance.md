## 1. Purpose and Principles

This document defines the data model and governance requirements for the Evidence-Based Bio-Medical Multi-Agent System.

### 1.1 Core principles

- **ACID + snapshotting**: Curated data must be stored as ACID tables with snapshot-based rollback and reproducibility.
- **Lineage by design**: Every curated/derived record must be traceable to raw source records and ingestion job versions.
- **Evidence integrity**: All evidence used by agents must be referenced by stable identifiers and immutable snapshots.
- **Auditability**: Data snapshots used by any agent workflow must be recorded so outputs can be reconstructed.

---

## 2. Data Domains

### 2.1 PubMed Open Access Subset (literature)

Primary extracted units:

- **Article**: identifier(s), title, abstract, methods, results (where available), publication date, journal, authors.
- **Full text artifacts**: sections/paragraphs and offsets (when available in the source format).
- **Metadata**: license, source version, ingestion timestamps.

### 2.2 ClinicalTrials.gov (trials)

Primary extracted units:

- **Trial**: NCT ID, conditions, interventions, outcomes, sample sizes, study status, start/end dates.
- **Outcome measures**: primary/secondary outcomes, adverse events, and other statistics (as available).
- **Metadata**: source version, ingestion timestamps.

---

## 3. Table Layers (Lakehouse Zones)

The data lake SHALL be organized into layers to separate concerns and improve governance.

### 3.1 Raw layer (`raw_*`)

- Stores **source-faithful** representations of incoming data.
- Minimal transformations allowed (only those required for parsing and storage).
- Must retain source identifiers and source file references.

Examples:

- `raw_pubmed_articles`
- `raw_pubmed_fulltext`
- `raw_clinicaltrials_studies`
- `raw_clinicaltrials_results`

### 3.2 Curated layer (`curated_*`)

- Normalized, deduplicated, schema-stabilized representations suitable for analytics and downstream AI pipelines.
- Adds canonical identifiers, normalized dates, and cleaned text fields.

Examples:

- `curated_articles`
- `curated_article_sections`
- `curated_trials`
- `curated_trial_outcomes`

### 3.3 Derived / Feature input layer (`derived_*`, `feature_inputs_*`)

- Derived datasets for:
  - entity extraction,
  - co-occurrence computations,
  - trial outcome aggregation,
  - and embedding preparation.

Examples:

- `derived_entities` (drug/disease/etc. mentions)
- `derived_relationships` (entity pairs with context)
- `feature_inputs_entity_stats`
- `feature_inputs_trial_stats`

---

## 4. Core Entities and Keys

### 4.1 Stable identifiers

- **PubMed**: PubMed ID (PMID) and/or other stable identifiers as provided by the dataset.
- **ClinicalTrials.gov**: NCT ID.

All curated records MUST include their stable identifier(s).

### 4.2 Internal surrogate keys

Curated tables MAY add surrogate keys to improve joins and performance, but MUST retain stable identifiers for audit and provenance.

### 4.3 Snapshot references

Any workflow producing user-facing outputs MUST record:

- Iceberg table snapshot IDs (or equivalent snapshot references),
- Vector index version / indexing run ID,
- Feature store registry version and feature view definitions version.

---

## 5. Lineage and Provenance Requirements

### 5.1 Ingestion metadata

Each raw and curated record MUST include, at minimum:

- `source_name` (pubmed / clinicaltrials)
- `source_version` (bulk dump version/date)
- `ingestion_run_id`
- `pipeline_version` (git sha or semantic version)
- `ingested_at` (timestamp)
- `source_uri` or `source_file_ref` (where it came from)

### 5.2 Transformation lineage

For curated and derived tables, the system MUST record:

- the upstream table(s),
- the transformation job id/version,
- row-level or partition-level lineage identifiers where feasible.

---

## 6. Governance Controls

### 6.1 Schema governance

- Curated schema changes MUST be versioned and reviewed.
- Breaking changes MUST be avoided; when required, they must be introduced with:
  - compatibility periods,
  - migration scripts,
  - and updated contract tests.

### 6.2 Access control

- Raw tables may contain noisy/unstructured fields and should be **restricted** to internal pipelines and operator roles.
- Curated/derived tables are available for downstream services and agent workflows on a least-privilege basis.

### 6.3 Retention and lifecycle

- Raw data SHOULD be retained to support reprocessing and audit.
- Curated snapshots MUST be retained according to the auditability requirements.
- Vector indices and feature registries MUST be versioned and retain enough history to reproduce past answers.

---

## 7. Evidence Contracts for Agents

To support “fully auditable and transparent agents,” the system MUST provide evidence contracts:

- **Document evidence item**:
  - stable doc id (PMID/NCT),
  - section type (abstract/methods/results),
  - snippet text or snippet hash,
  - offsets (when available),
  - dataset snapshot reference.

- **Statistical evidence item**:
  - feature name/key,
  - entity id(s),
  - value,
  - timestamp (if time-aware),
  - feature view version / registry version,
  - dataset snapshot reference.

These evidence items are the building blocks of the evidence manifest described in the FRD/NFRD.

---

## 8. UI Data Contracts

The UI service MUST consume data exclusively through the `agent-api` and `audit-api`. No direct data store access is permitted from the UI layer.

### 8.1 Query response contract (Researcher Portal)

The `POST /v1/query` response and its SSE streaming events MUST include structured fields sufficient for the UI to render:

- **Agent step events** (SSE): `{ "agent": "<role>", "status": "started|completed|error", "summary": "<short text>" }`
- **Final answer**: structured sections (background, evidence, statistics, conclusion) as named fields, not a single opaque text blob.
- **Citations**: list of `{ "id": "<PMID|NCT>", "type": "article|trial", "snippet": "<text>" }` objects.
- **Evidence manifest id**: stable reference for subsequent audit lookup.

### 8.2 Audit artifact contract (Audit View)

The `GET /v1/audit/{id}` response MUST include structured fields sufficient for the UI to render:

- Execution timeline: ordered list of `{ "agent", "input_summary", "output_summary", "timestamp" }` entries.
- Evidence manifest: list of `{ "claim_ref", "evidence_items": [{ "doc_id", "snippet", "snapshot_ref" }] }`.
- Replay metadata: snapshot IDs and configuration version needed to re-execute.

### 8.3 Operator status contract (Operator Dashboard)

The `GET /v1/ingest/status` response MUST include:

- List of recent runs: `{ "run_id", "status", "records_ingested", "dq_pass", "dq_warn", "dq_fail", "started_at", "completed_at" }`.
- Current pipeline health indicators per service.

---

## 9. Open Questions (To Be Resolved During Implementation)

- Exact Iceberg catalog choice (REST catalog vs metastore-based approaches).
- Online store choice for Feast in a fully self-hosted configuration.
- Standardization strategy for drug/disease canonicalization (e.g., optional integration with open biomedical ontologies).

---

## CTO Sign-Off

**Status:** APPROVED WITH CONDITIONS

**Consistency review:**
- Table layer definitions (section 3: raw/curated/derived) are consistent with `01-FR` FR-7 and `03-architecture` section 6.1. Table names (`raw_pubmed_articles`, `curated_articles`, etc.) are consistent across documents.
- Section 7 (Evidence Contracts for Agents) defines document evidence items and statistical evidence items. These structures are consistent with `05-data-quality-rules.md` DQ-X-2 (snippet storage requirements) and DQ-FEAST-1 (feature traceability requirements). Consistent.
- Section 8.1 (Query response contract): the SSE agent step event schema `{ "agent", "status", "summary" }` is defined here rather than in `03-architecture` section 6.3. Cross-document finding: this creates a risk of schema drift. The CTO has flagged this as a Condition on `03-architecture` (Condition 1). Until section 6.3 of `03-architecture` is updated, section 8.1 of this document is the normative reference for the SSE event schema.
- Section 8.2 (Audit artifact contract) defines the `GET /v1/audit/{id}` response structure consistent with `03-architecture` section 6.3 and `06-qa-test-plan.md` section 3.3 E2E step 4. Consistent.
- Section 4.3 (Snapshot references) requires workflows to record Iceberg snapshot IDs, vector index version, and feature store registry version. This is consistent with `05-DQ` DQ-FEAST-1, DQ-VEC-1, and the replay requirements in `02-NFR` NFR-A4.

**Gaps noted:**
- Section 9 lists the Iceberg catalog choice as an open question. This must be resolved before Phase 0 begins (flagged as Condition 4 on `03-architecture` sign-off; tracking here for completeness).
- The online store choice for Feast is an open question. This must be resolved before Phase 3 begins.
- Section 6.2 (access control) states raw tables should be restricted to internal pipelines and operator roles, but does not reference the RBAC role definitions. Once the role/permission matrix is added to `03-architecture` section 8 (per CTO Condition 3 on that document), this section should be updated with explicit role references.

**Conditions:**
1. Online store choice for Feast must be documented before Phase 3 begins.

**Phase gate:** Phase 1 (data ingestion and lake), Phase 2 (vector retrieval — vector record contracts), Phase 3 (feature store — feature contracts), Phase 5 (UI — data contracts for API responses).


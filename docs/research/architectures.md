## Research: Reference Architectures and Patterns

This document collects architecture patterns and implementation guidance relevant to this project.

The Researcher Agent maintains this as the “why” behind key design choices, with links to upstream sources where possible.

---

## 1. Two-Layer Orchestration Pattern (LangGraph + Temporal)

### Pattern summary

- **LangGraph**: deterministic cognitive workflow (agent routing + shared state).
- **Temporal**: durable infrastructure workflow (retries, timeouts, scheduling, resumption).

### Why this matters

- Medical workflows must fail closed and recover safely without losing state.
- Agent reasoning and tool usage must be auditable.

### Implementation notes

- Keep workflow logic deterministic; push non-deterministic work to activities.
- Use Temporal workflow history as an audit substrate.
- Capture config versions and dataset snapshot references in workflow state.

---

## 2. Lakehouse Governance with Iceberg + Object Storage

### Pattern summary

- Store curated data in Iceberg tables backed by object storage (MinIO).
- Use snapshots for time travel and reproducibility.

### Implementation notes

- Partitioning must balance ingestion throughput with query patterns.
- Use compaction and maintenance jobs (Temporal-scheduled).
- Treat snapshot IDs as part of the “evidence contract” for agent outputs.

---

## 3. Evidence-Centric RAG for Scientific/Medical Domains

### Pattern summary

- Retrieval returns **verbatim** passages/snippets with stable identifiers.
- Synthesis must be constrained to retrieved context and numeric features.

### Anti-hallucination controls

- Reviewer/critic loop rejects uncited claims.
- “Evidence manifest” artifact maps claims to sources.
- Refuse when evidence is insufficient rather than guessing.

---

## 4. Feature Store as “Ground Truth for Numbers”

### Pattern summary

Instead of having an LLM estimate statistics, compute and serve them from Feast:

- Co-occurrence frequencies
- Trial outcome distributions
- Counts and rates

### Implementation notes

- Version and trace feature definitions.
- Record the feature keys/values used per answer for audit.

---

## 5. Auditability and Transparency Patterns

### Requirements-to-pattern mapping

- **Traceability**:
  - correlation IDs across services,
  - Temporal workflow id in every log line,
  - OTel traces linking API request → workflow → agent steps.

- **Tamper-evidence**:
  - immutable log storage or integrity checks,
  - strict RBAC to audit data.

- **Reconstruction**:
  - store dataset snapshot IDs,
  - store vector index run IDs,
  - store feature registry versions,
  - store agent configuration and tool call transcripts.


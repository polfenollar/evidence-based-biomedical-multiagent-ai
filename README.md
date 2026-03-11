## Evidence-Based Bio-Medical Multi-Agent System (Open Source)

Production-grade, self-hosted biomedical evidence synthesis platform using a governed lakehouse and a deterministic multi-agent workflow.

### Key properties

- **100% free / open-source** and **self-hosted** (no proprietary managed cloud services).
- **Big data ingestion**: PubMed Open Access Subset + ClinicalTrials.gov.
- **Governed lakehouse**: MinIO + Apache Iceberg (ACID, schema evolution, snapshots).
- **AI context**: Vector DB (Qdrant or Milvus) + embedding pipeline.
- **AI features**: Feast feature store for ground-truth statistics.
- **Two-layer orchestration**: LangGraph (cognitive state machine) + Temporal (durable workflows).
- **Non-negotiable**: **Fully auditable and transparent agents** (traceability, provenance, replay/reconstruction).

---

## Documentation

### Engineering “team” agents and responsibilities

- `docs/00-agents-overview.md`

### Requirements and design

- `docs/01-functional-requirements.md`
- `docs/02-non-functional-requirements.md`
- `docs/03-architecture-and-tech-stack.md`
- `docs/04-data-model-and-governance.md`
- `docs/05-data-quality-rules.md`
- `docs/06-qa-test-plan.md`

### Research bundle (upstream sources and patterns)

- `docs/research/technologies.md`
- `docs/research/architectures.md`
- `docs/research/open-source-components.md`

---

## Repository status

This repository currently contains the project documentation and delivery-quality requirements. Implementation will follow these documents, starting with:

- Docker Compose stack definition for core services
- Service boundaries (workers, APIs)
- Ingestion pipelines and data governance
- Agent workflows with evidence manifests and audit store
- Automated unit/integration/e2e tests and performance testing harness

---

## Human actions requested (optional, for faster implementation)

To accelerate design review with real-world reference code, clone these upstream OSS repos locally and share any notes/questions:

- Temporal Python samples: `https://github.com/temporalio/samples-python`
- LangGraph repo/examples: `https://github.com/langchain-ai/langgraph`
- (Optional) Langfuse self-host patterns: `https://github.com/langfuse/langfuse`


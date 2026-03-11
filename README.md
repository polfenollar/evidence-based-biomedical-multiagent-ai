## Evidence-Based Bio-Medical Multi-Agent System (Open Source)

This is an MLOps, production-grade, self-hosted biomedical evidence synthesis platform using a governed lakehouse and a deterministic multi-agent workflow.

It´s intended to ease medical research for trials and articles by providing a contextual search engine with transparent and auditable results (both content and agents traceability)

### Key properties

- **100% free / open-source** and **self-hosted** (no proprietary managed cloud services).
- **Big data ingestion**: PubMed Open Access Subset + ClinicalTrials.gov.
- **Governed lakehouse**: MinIO + Apache Iceberg (ACID, schema evolution, snapshots).
- **AI context**: Vector DB (Qdrant or Milvus) + embedding pipeline.
- **AI features**: Feast feature store for ground-truth statistics.
- **Two-layer orchestration**: LangGraph (cognitive state machine) + Temporal (durable workflows).
- **Fully auditable and transparent agents** (traceability, provenance, replay/reconstruction).
- **Fully observable with Prometheus, Loki, Grafana and Langsmith for agent monitoring and tracing

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



## Research: Technologies and Official Documentation

This document is maintained by the Researcher Agent as the authoritative list of upstream documentation for all core technologies in the system.

Requirement: all links must be to official docs or widely trusted maintainers. For each component, capture:

- What it is used for in this project
- Key APIs/config references needed to implement
- Deployment/self-host notes
- Observability/auditability hooks

---

## 1. Workflow Orchestration: Temporal

- **Docs**: `https://docs.temporal.io/`
- **Concepts to implement**:
  - Workflows vs Activities
  - Retries, timeouts, heartbeats
  - Signals/queries (for live status and audit introspection)
  - Worker deployment patterns
  - Deterministic workflow constraints
- **Project usage**:
  - Durable orchestration for ingestion, indexing, feature refresh, and multi-agent query runs.
  - Workflow history used as part of audit trails.

---

## 2. Cognitive Orchestration: LangGraph

- **Docs**: `https://langchain-ai.github.io/langgraph/`
- **Concepts to implement**:
  - State schema design
  - Node/edge routing patterns
  - Cycles for reviewer loops
  - Determinism controls and state serialization
- **Project usage**:
  - Implements the domain multi-agent state machine.

---

## 3. Big Data Compute: Apache Spark

- **Docs**: `https://spark.apache.org/docs/latest/`
- **Concepts to implement**:
  - Structured streaming vs batch (decide for ingestion)
  - DataFrame transformations and schema enforcement
  - Partitioning strategies
  - Fault tolerance and checkpointing
- **Project usage**:
  - Bulk parsing/curation of PubMed OA + ClinicalTrials.gov exports.

---

## 4. Lakehouse Table Format: Apache Iceberg

- **Docs**: `https://iceberg.apache.org/docs/latest/`
- **Concepts to implement**:
  - Table snapshots and time travel
  - Schema evolution
  - Partitioning and compaction
  - Catalog options (REST catalog vs metastore)
- **Project usage**:
  - ACID tables over MinIO for governed data lake.
  - Snapshot IDs used for reproducibility and audit.

---

## 5. Object Storage: MinIO

- **Docs**: `https://min.io/docs/minio/`
- **Concepts to implement**:
  - Buckets, policies, and service accounts
  - Encryption/TLS options
  - Performance tuning
- **Project usage**:
  - S3-compatible storage for Iceberg files and pipeline artifacts.

---

## 6. Vector Database: Qdrant (default) / Milvus (alternative)

### Qdrant

- **Docs**: `https://qdrant.tech/documentation/`
- **Concepts**:
  - Collections and payloads
  - Filtering
  - Persistence and snapshots
  - HNSW parameters and tuning

### Milvus

- **Docs**: `https://milvus.io/docs`
- **Concepts**:
  - Collections/partitions
  - Index types and tuning
  - Deployment topology

---

## 7. Feature Store: Feast

- **Docs**: `https://docs.feast.dev/`
- **Concepts**:
  - Entities, feature views, data sources
  - Offline store integration
  - Online store options (must be OSS/self-host)
  - Registry versioning
- **Project usage**:
  - Serve numeric/statistical metrics to the Biostatistician agent.

---

## 8. Observability: Langfuse + OpenTelemetry + Prometheus/Grafana

### Langfuse (recommended OSS/self-host)

- **Docs**: `https://langfuse.com/docs`
- **Key items**:
  - Trace/span modeling for agent steps
  - Metadata and tags for audit search
  - Self-host deployment instructions

### OpenTelemetry

- **Docs**: `https://opentelemetry.io/docs/`

### Prometheus

- **Docs**: `https://prometheus.io/docs/`

### Grafana

- **Docs**: `https://grafana.com/docs/`

---

## 9. Containerization: Docker and Docker Compose

- **Docs**: `https://docs.docker.com/`
- **Compose**: `https://docs.docker.com/compose/`
- **Project usage**:
  - Fully reproducible local/bare-metal deployment.


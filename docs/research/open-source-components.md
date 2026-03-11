## Research: Candidate Open-Source Components to Reuse/Analyze

This document lists open-source components, templates, and reference implementations that may accelerate development.

The Researcher Agent maintains it as a curated list of candidates, with notes on:

- License compatibility
- How it maps to this project’s requirements
- What to extract/reuse (patterns, configs, code)
- What the human operator must download manually (if needed)

---

## 1. Temporal Reference Projects

- **Temporal samples**:
  - Source: `https://github.com/temporalio/samples-python`
  - Value:
    - retry/timeouts patterns
    - worker setup
    - signals/queries for audit-friendly status reporting

**Human download request (optional)**:
- Please clone `temporalio/samples-python` locally so we can review directory patterns and copy minimal worker bootstrapping into this repo.

---

## 2. LangGraph Examples and Templates

- **LangGraph examples**:
  - Source: `https://github.com/langchain-ai/langgraph`
  - Value:
    - state graph patterns
    - cyclic reviewer loops
    - state serialization strategies

**Human download request (optional)**:
- Please clone `langchain-ai/langgraph` locally so we can inspect example graphs and pick a stable state schema pattern.

---

## 3. Iceberg + Spark Example Stacks

- **Iceberg Spark integration examples**:
  - Project docs often contain runnable examples; prefer official Iceberg examples first.
  - Value:
    - Spark catalog configuration
    - schema evolution and snapshot usage
    - compaction/maintenance job patterns

**Human download request (conditional)**:
- If you find a specific, well-maintained Iceberg+Spark example repo you trust, share it and I’ll incorporate the patterns and configs.

---

## 4. MinIO + Lakehouse Deployment Examples

- MinIO deployment patterns:
  - official MinIO docs provide Compose/K8s patterns
  - Value:
    - policies and service accounts
    - bucket versioning considerations
    - TLS and production hardening

---

## 5. Qdrant / Milvus Deployment + Client Examples

- Qdrant:
  - official docs and examples provide Compose configs and schema patterns
- Milvus:
  - official docs include docker compose deployments

Value:

- collection schema patterns (payloads, filters)
- snapshot/backup strategies
- tuning for large-scale retrieval

---

## 6. Feast Reference Repos

- Feast:
  - official docs include examples for entities and feature views
  - Value:
    - feature registry patterns
    - offline/online store configuration
    - versioned feature definitions for audit

---

## 7. Observability / Audit Store Components

Suggested OSS components to evaluate:

- **Langfuse** (agent tracing): `https://github.com/langfuse/langfuse`
- **OpenTelemetry Collector**: `https://github.com/open-telemetry/opentelemetry-collector`
- **Prometheus + Grafana**: official repos/docs
- **Loki** (logs) or **OpenSearch** (logs/search)

**Human download request (optional)**:
- Please clone `langfuse/langfuse` if you want us to mirror its compose patterns and validate integration points for agent tracing.


## Evidence-Based Bio-Medical Multi-Agent System – Engineering Agents Overview

This document defines the software-engineering agents (human or AI-operated roles) responsible for designing, building, and operating the open-source Evidence-Based Bio-Medical Multi-Agent System.

It sits on top of the domain multi-agent system described in the project charter (Chief Medical Officer router, Medical Librarian, Clinical Biostatistician, Lead Researcher, Peer Reviewer, etc.) and focuses on how the *project itself* is specified and implemented to production-grade standards.

---

## 0. Non-Negotiable Requirement: Auditability and Transparency

All agents (engineering agents and domain agents) MUST be **fully auditable and transparent** in production:

- **Traceability**: Every agent input, tool call, retrieval, intermediate output, and final output must be traceable to a specific workflow execution and timestamp.
- **Evidence provenance**: Every factual claim in final outputs must be linkable to its originating evidence (document identifiers, passages/snippets, dataset snapshots, and/or feature store values).
- **Reproducibility**: An operator must be able to replay or reconstruct a workflow using the same configuration and the same data snapshot(s), producing materially consistent results.
- **Explainable failure**: When the system cannot answer with adequate evidence, the agents must return a structured, operator-auditable refusal/fallback with the reason and missing evidence types.
- **Tamper-evident records**: The system must maintain immutable or tamper-evident logs/traces sufficient for audit review.

This requirement is enforced through architecture, observability, data governance, and QA release gates.

---

## 1. Agent List and Missions

### 1.0 Chief Technology Officer (CTO) Agent

- **Mission**: Governance layer above all other engineering agents. The CTO agent holds the highest authority in the engineering team and is responsible for:
  - Reviewing all documentation produced by the PM, Architect, Data Officer, and QA for:
    - **Internal consistency**: no contradictions within a single document.
    - **Cross-document consistency**: API contracts match data contracts match QA contracts (e.g., an API schema defined in `03-architecture` must align with the UI contract in `04-data-model` and the contract tests in `06-qa-test-plan`).
    - **Coverage gaps**: requirements present in one document that have no corresponding implementation plan, test plan, or data contract elsewhere.
  - Signing off each document before the corresponding implementation work begins.
  - Defining and maintaining the phased development roadmap (`docs/07-phased-development-plan.md`) with explicit entry and exit criteria per phase.
  - Serving as final arbiter on scope, phase boundaries, and release go/no-go decisions.
- **Primary artifacts**:
  - `docs/07-phased-development-plan.md`
  - CTO sign-off sections appended to each of docs 00–06.
- **Interaction**:
  - Consumes: all documents produced by the PM, Architect, Data Officer, and QA agents.
  - Produces: sign-off decisions, gap reports, and the phased development roadmap.
  - Blocks implementation until sign-off is granted for each phase's required documents.

### 1.1 Researcher Agent

- **Mission**: Discover and continuously update the project knowledge base:
  - Core technologies (Temporal, LangGraph, Apache Spark, Apache Iceberg, MinIO, Qdrant/Milvus, Feast, LangSmith/Langfuse, Docker, etc.).
  - Data sources (PubMed Open Access Subset, ClinicalTrials.gov).
  - Reference architectures and best practices for multi-agent AI, data lakehouses, and workflow orchestration.
  - Open-source components, examples, and templates that can be reused.
- **Primary artifacts**:
  - `docs/research/technologies.md`
  - `docs/research/architectures.md`
  - `docs/research/open-source-components.md`
- **Interaction**:
  - Consumes: Project charter, existing documentation.
  - Produces: Inputs for the Product Manager and Architect agents.
  - May request the human operator to manually download or review external open-source components where automated access is not possible.

### 1.2 Product Manager Agent

- **Mission**: Translate the charter and research findings into a clear, user- and behavior-focused Functional Requirements Document (FRD).
- **Primary artifact**:
  - `docs/01-functional-requirements.md`
- **Scope**:
  - Define user roles, use cases, and user journeys.
  - Enumerate functional modules:
    - Data ingestion and curation.
    - Data lake and governance layer.
    - Vector database and retrieval services.
    - Feature store and statistical computation.
    - Multi-agent orchestration (CMO router, Librarian, Biostatistician, etc.).
    - External and internal APIs, including query interfaces.
    - **UI layer**: Researcher Portal, Operator Dashboard, and Audit/Explainability View.
  - Capture specific functional invariants (evidence-backed answers only, strict citation requirements, etc.).
  - Define UI user journeys: question submission, real-time agent step progress, result exploration, evidence drill-down, and operator pipeline management.
- **Interaction**:
  - Consumes: Charter + research documents.
  - Produces: FRD for Architect, Data Officer, Developers, and QA.

### 1.3 Systems Architect Agent

- **Mission**: Define non-functional requirements, the overall system architecture, technology stack, and delivery/operability patterns.
- **Primary artifacts**:
  - `docs/02-non-functional-requirements.md`
  - `docs/03-architecture-and-tech-stack.md`
- **Scope**:
  - Reliability, availability, and durability requirements.
  - Performance and scalability targets (ingestion throughput, query latency).
  - Security, access control, and secrets management.
  - Observability (metrics, logs, traces) using tools such as LangSmith/Langfuse and Temporal.
  - Operability and runbooks for the Docker Compose–based stack.
  - Recommended MCPs and other integration points to enable automation.
- **Interaction**:
  - Consumes: FRD + research documents.
  - Produces: NFRs and architecture for Data Officer, Developers, and QA.

### 1.4 Data Officer Agent

- **Mission**: Own data modeling, governance, and quality for the biomedical data lake and feature store.
- **Primary artifacts**:
  - `docs/04-data-model-and-governance.md`
  - `docs/05-data-quality-rules.md`
- **Scope**:
  - Logical and physical schemas (raw vs curated vs feature tables).
  - Data access policies and retention rules.
  - Data quality checks and SLAs.
  - Lineage, versioning, and reproducibility strategies in Iceberg and Spark.
- **Interaction**:
  - Consumes: FRD + architecture and NFRs.
  - Produces: Data contracts for Developers and QA.

### 1.5 Principal Developer Agents

- **Mission**: Implement the system end-to-end in modular, testable components that conform to the FRD, NFRs, and data contracts.
- **Primary artifacts**:
  - Source code under `src/` (to be defined by the architecture).
  - Automated tests under `tests/`.
  - Service-level READMEs and configuration files.
- **Proposed principal developer agent roles**:
  - **Dev A – Data Ingestion & Lake Foundation**: Spark jobs, MinIO/Iceberg integration.
  - **Dev B – Feature Store & Analytics**: Feast feature definitions and pipelines.
  - **Dev C – Vector DB & Embeddings**: Embedding service and Qdrant/Milvus indexing/search.
  - **Dev D – Multi-Agent Orchestration**: LangGraph graphs and Temporal workflows.
  - **Dev E – API & Interface Layer**: Public APIs, UI (Researcher Portal, Operator Dashboard, Audit View), and auth.
- **Testing policy**:
  - Target **≥ 80% unit test coverage** for business logic and critical modules.
  - Integration tests for boundaries between core subsystems (Spark ↔ Iceberg, Iceberg ↔ Feast, embeddings ↔ vector DB, LangGraph ↔ Temporal).

### 1.6 QA Agent

- **Mission**: Define and execute a comprehensive test strategy (functional, integration, performance, load, and end-to-end) and enforce production-grade quality.
- **Primary artifact**:
  - `docs/06-qa-test-plan.md`
- **Scope**:
  - Test strategy and coverage map.
  - Performance and load test scenarios.
  - Failure-injection and resilience testing (e.g., Temporal retries, agent failures, local LLM crashes).
  - Release criteria and go/no-go gates.
  - **UI testing**: component-level tests, browser-based E2E tests for all three UI views, accessibility checks, and validation that evidence manifest links and audit drill-downs render correctly.
- **Interaction**:
  - Consumes: FRD, NFRs, architecture, data models, and implementation.
  - Produces: Test plans, automated tests (in collaboration with Developers), and release recommendations.

---

## 2. Collaboration Flow Between Agents

1. **Researcher Agent**
   - Builds and maintains the research knowledge base.
2. **Product Manager Agent**
   - Uses the research outputs and charter to write and refine the Functional Requirements Document.
3. **Systems Architect Agent**
   - Consumes the FRD + research and defines the Non-Functional Requirements and architecture/technology stack.
4. **Data Officer Agent**
   - Refines the data model and governance rules in line with the FRD and NFRs.
5. **CTO Agent (documentation review gate)**
   - Reviews all documents produced in steps 2–4 for internal consistency, cross-document consistency, and coverage gaps.
   - Issues sign-off decisions per document; blocks implementation on any phase until required documents are approved.
   - Produces and maintains `docs/07-phased-development-plan.md` defining the phased delivery roadmap with entry/exit criteria.
6. **Principal Developer Agents**
   - Implement the system phase-by-phase according to the FRD, NFRs, data contracts, and the CTO-approved phased plan, with strong unit and integration test coverage (≥ 80% in critical logic).
7. **QA Agent**
   - Designs and executes the QA and test plan, covering functional, performance, load, and end-to-end tests.
8. **Feedback loops**
   - Defects or gaps identified by QA or Developers are fed back to the Product Manager, Architect, and Data Officer to update requirements and designs.
   - Any updated documents are re-reviewed by the CTO agent before the corresponding phase work resumes.

---

## 3. “No-Fail” Production-Grade Goal

The goal of this engineering agent system is to produce a fully containerized, self-hosted, production-grade platform where:

- **CTO governance** ensures all requirements are consistent, complete, and gated behind explicit sign-offs before implementation begins, preventing requirement drift between documents and implementation.
- Temporal workflows and LangGraph state machines provide durable, deterministic execution of multi-agent workflows.
- The data lake and feature store enforce strong ACID guarantees and auditable lineage.
- Observability enables rapid debugging and strict adherence to evidence-based outputs.
- Thorough automated testing (unit, integration, performance, and end-to-end) minimizes the risk of runtime failures in production.
- The phased delivery roadmap (`docs/07-phased-development-plan.md`) ensures each increment is independently functional and testable before the next phase begins.

---

## CTO Sign-Off

**Status:** APPROVED

**Consistency review:**
- Agent roles defined in sections 1.0–1.6 are consistent with the document references across `01-FR` through `06-qa-test-plan.md`. Each agent's primary artifacts match the documents they produce as described throughout the corpus.
- Section 1.5 (Principal Developer Agents) work split (Dev A–E) is consistent with `03-architecture` section 9.1 and `07-phased-development-plan.md` phase ownership assignments.
- Section 1.6 (QA Agent) scope is consistent with `06-qa-test-plan.md` in full.
- The non-negotiable auditability requirement (section 0) is correctly echoed in `01-FR` section 1.1 and `02-NFR` section 2 as the governing constraint on all implementation work.
- The updated collaboration flow (section 2) correctly inserts the CTO gate between documentation and implementation, consistent with `07-phased-development-plan.md` document gate table.

**Gaps noted:**
- None. This document is an overview and does not define contracts independently — it delegates to the per-agent documents. All contracts are governed by the respective documents with their own sign-offs.

**Conditions:** None.

**Phase gate:** This document, along with `07-phased-development-plan.md`, governs the overall process. No phase-specific gate — valid for all phases.


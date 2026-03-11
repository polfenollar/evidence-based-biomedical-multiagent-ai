# Runbook: Agent Workflow Failure

**Service:** `agent-worker`, `agent-api`
**Temporal workflow:** `EvidenceWorkflow`
**Symptoms:** `POST /v1/query` returns 502; Grafana shows query success rate drop; Temporal UI shows failed workflows.

---

## 1. Triage

```bash
# Check container status
docker compose -f infrastructure/docker-compose.yml ps agent-worker agent-api

# View logs
make logs-agent-worker
make logs-agent-api

# List recent failed workflows in Temporal
docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow list --namespace default \
  --query 'WorkflowType="EvidenceWorkflow" AND ExecutionStatus="Failed"'
```

## 2. Common Causes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConnectionRefusedError: retrieval-api:8001` | retrieval-api down | `make restart-retrieval-api` |
| `ConnectionRefusedError: feature-api:8002` | feature-api down | `make restart-feature-api` |
| Temporal `ActivityError: start_to_close_timeout` | Graph took > 5 min | Check retrieval/feature latency; increase timeout in workflows.py |
| `MaxRevisionsReached` — review_status=rejected | Retrieval returning empty snippets | Verify Qdrant collections populated (Phase 2) |
| `502` on all queries | agent-worker not listening | `make restart-agent-worker` |

## 3. Recovery

```bash
# Restart agent-worker
make restart-agent-worker

# Verify the worker is connected to Temporal
docker compose -f infrastructure/docker-compose.yml logs --tail=20 agent-worker
# Expect: "Agent worker listening on task queue 'agent'"

# Test a single query
curl -s -X POST http://localhost:8003/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"aspirin test"}' | python3 -m json.tool
```

## 4. Audit Trail Check

Failed workflows leave an auditable artifact in Temporal history. Even if a query fails, the Temporal UI at `http://localhost:8080` preserves the full execution history for post-mortem analysis.

## 5. Escalation

If `review_status=rejected` persists across multiple queries with real (non-test) data, the evidence quality issue must be escalated to the Data Officer to investigate Qdrant index freshness.

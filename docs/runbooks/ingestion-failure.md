# Runbook: Ingestion Failure

**Service:** `ingestion-worker`
**Temporal workflow:** `IngestionWorkflow`
**Symptoms:** No new Iceberg snapshots; DQ report artifact absent; embedding-worker downstream stalls.

---

## 1. Triage

```bash
# Check container status
docker compose -f infrastructure/docker-compose.yml ps ingestion-worker

# View last 100 log lines
make logs-ingestion-worker

# Check Temporal workflow history
docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow list --namespace default --query 'WorkflowType="IngestionWorkflow"'
```

## 2. Common Causes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SparkException: No space left on device` | MinIO volume full | Expand volume or delete old snapshots |
| `ConnectionRefusedError: nessie:19120` | Nessie down | `make restart-nessie` |
| `DQ block rule fired: null PMID` | Bad source data | Inspect `data/sample/` files; fix or exclude bad records |
| Workflow stuck in `Running` > 30 min | Spark OOM | Increase container memory in docker-compose.yml |
| `AccessDenied` on MinIO | Wrong credentials | Check `infrastructure/.env` MINIO_ROOT_USER/PASSWORD |

## 3. Recovery

```bash
# Restart ingestion worker (picks up pending Temporal tasks)
make restart-ingestion-worker

# If Temporal history shows failed workflow, re-trigger:
docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow start --workflow-type IngestionWorkflow \
  --task-queue ingestion --namespace default \
  --input '{"source_name":"articles","run_id":"manual-recovery","pipeline_version":"0.1.0"}'
```

## 4. Escalation

If DQ block rules fired on production data (not test data), escalate to the Data Officer before re-running. Do not suppress DQ rules to force ingestion through.

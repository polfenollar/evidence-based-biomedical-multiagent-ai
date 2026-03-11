# Runbook: Vector Database (Qdrant) Recovery

**Service:** `qdrant`
**Symptoms:** `retrieval-api` returns empty results; Grafana shows high latency; `biomedical_queries_total{status="rejected"}` spike.

---

## 1. Triage

```bash
# Check Qdrant container
docker compose -f infrastructure/docker-compose.yml ps qdrant

# Check Qdrant health
curl -s http://localhost:6333/healthz

# List collections
curl -s http://localhost:6333/collections | python3 -m json.tool

# Check collection vector counts
curl -s http://localhost:6333/collections/biomedical_articles | python3 -m json.tool
```

## 2. Common Causes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Collections exist but 0 vectors | embedding-worker failed mid-run | Re-run IndexingWorkflow (see below) |
| Qdrant container not running | OOM or host restart | `docker compose up -d qdrant` |
| `qdrant-data` volume missing | Volume deleted (e.g., `make clean`) | Full re-index required |
| High search latency | Too many segments | Qdrant auto-optimises; wait 5–10 min or force: `POST /collections/{name}/index` |

## 3. Recovery: Re-index Collections

```bash
# Trigger re-indexing via Temporal (embedding-worker must be running)
docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow start --workflow-type IndexingWorkflow \
  --task-queue embedding --namespace default \
  --input '{"source_name":"articles","run_id":"recovery-$(date +%s)","pipeline_version":"0.2.0"}'

docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow start --workflow-type IndexingWorkflow \
  --task-queue embedding --namespace default \
  --input '{"source_name":"trials","run_id":"recovery-$(date +%s)","pipeline_version":"0.2.0"}'
```

## 4. Verify Recovery

```bash
# After indexing completes, verify vectors are present
curl -s http://localhost:6333/collections/biomedical_articles | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('vectors:', d['result']['vectors_count'])"

# Test a search
curl -s -X POST http://localhost:8001/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"aspirin","limit":3}' | python3 -m json.tool
```

## 5. Data Durability Note

Qdrant data is stored in the `qdrant-data` Docker volume. This volume is **not** backed up automatically. For production, configure Qdrant snapshot backups (`POST /collections/{name}/snapshots`) on a schedule.

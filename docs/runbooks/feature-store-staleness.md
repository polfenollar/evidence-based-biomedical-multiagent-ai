# Runbook: Feature Store Staleness

**Service:** `feature-worker`, `feature-api`
**Symptoms:** `feature-api` returns stale `snapshot_ref`; `biostatistician` node returns empty features; Grafana staleness alert fires.

---

## 1. Triage

```bash
# Check feature-worker and feature-api status
docker compose -f infrastructure/docker-compose.yml ps feature-worker feature-api

# Check feature-api health and a known entity
curl -s http://localhost:8002/health
curl -s http://localhost:8002/v1/features/article/99000001 | python3 -m json.tool

# Check feature-worker logs for last materialization
make logs-feature-worker | tail -50
```

## 2. Staleness Definition

Features are considered stale if the `snapshot_ref` returned by `feature-api` does not match the current Iceberg snapshot ID for `curated_articles`. Check:

```bash
# Current Iceberg snapshot (via Nessie)
curl -s http://localhost:19120/api/v2/trees/main/contents/biomedical.curated_articles \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('content',{}).get('snapshotId','not found'))"

# Feature-api snapshot ref
curl -s http://localhost:8002/v1/features/article/99000001 | python3 -c "import json,sys; print(json.load(sys.stdin).get('snapshot_ref'))"
```

## 3. Common Causes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Features absent for new PMIDs | feature-worker not re-run after ingestion | Trigger FeatureRefreshWorkflow (below) |
| `snapshot_ref` stale by hours | feature-worker cron not firing | Check Temporal schedule; restart feature-worker |
| Redis evicted feature data | Redis maxmemory policy | Increase Redis memory or adjust TTL in feast materialisation |
| `404` on feature-api for known PMID | Online store not materialised | Run materialisation manually (below) |

## 4. Recovery: Re-materialise Features

```bash
# Trigger FeatureRefreshWorkflow via Temporal
docker compose -f infrastructure/docker-compose.yml exec temporal \
  temporal workflow start --workflow-type FeatureRefreshWorkflow \
  --task-queue feature --namespace default \
  --input '{"run_id":"recovery-$(date +%s)","pipeline_version":"0.2.0"}'

# Or restart feature-worker (it runs materialisation on startup)
make restart-feature-worker
```

## 5. Verify Recovery

```bash
# After materialisation, check a known entity
curl -s http://localhost:8002/v1/features/article/99000001 | python3 -m json.tool
# Expect: snapshot_ref matches current Iceberg snapshot
```

## 6. Escalation

If freshness SLA is breached (features > 24 h old in production), escalate to the Data Officer. Do not serve stale features without notifying downstream consumers.

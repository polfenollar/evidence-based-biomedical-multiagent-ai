# Runbook: UI / API Restart

**Services:** `ui`, `agent-api`, `audit-api`
**Symptoms:** UI unreachable at port 8501; queries return errors; audit trail unavailable.

---

## 1. Triage

```bash
# Check all Phase 5 service status
docker compose -f infrastructure/docker-compose.yml ps ui agent-api audit-api

# Health checks
curl -s http://localhost:8003/health   # agent-api
curl -s http://localhost:8004/health   # audit-api
curl -s http://localhost:8501/healthz  # ui (Streamlit)

# Logs
make logs-ui
make logs-agent-api
make logs-audit-api
```

## 2. Common Causes & Fixes

### agent-api (port 8003)

| Symptom | Cause | Fix |
|---------|-------|-----|
| 503 on `/v1/query` | Temporal client not connected | `make restart-agent-api`; check Temporal health |
| `KeyError` in logs | New `AgentOutput` field missing | Rebuild image after code update: `docker compose build agent-api && docker compose up -d agent-api` |
| Redis connection error | Redis down | `make restart-redis`; then `make restart-agent-api` |
| Metrics endpoint `/metrics` 404 | Old image cached | Force rebuild: `docker compose build --no-cache agent-api` |

### audit-api (port 8004)

| Symptom | Cause | Fix |
|---------|-------|-----|
| 503 on `/v1/audit/{id}` | Redis connection lost | `make restart-audit-api` |
| 404 for valid manifest | Redis TTL expired (24 h) | Re-run the original query to regenerate the manifest |

### UI (port 8501)

| Symptom | Cause | Fix |
|---------|-------|-----|
| UI shows "Degraded mode" warning | audit-api down | Fix audit-api first; UI will recover on next page load |
| "SSE connection dropped" banner | agent-api overloaded or restarting | Wait for agent-api to restart; retry query |
| Blank white page | Streamlit startup failure | `make restart-ui`; check for Python import errors |
| Operator Dashboard shows 403 | Wrong role selected | Change sidebar role to **operator** |

## 3. Full Stack Restart (last resort)

```bash
# Restart Phase 4+5 services in dependency order
make restart-agent-worker
make restart-agent-api
make restart-audit-api
make restart-ui
```

## 4. Verify Recovery

```bash
# Smoke test all three services
curl -s http://localhost:8003/health | python3 -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'"
curl -s http://localhost:8004/health | python3 -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'"
echo "Services healthy"

# Test a full query
curl -s -X POST http://localhost:8003/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"aspirin test"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('citations:', len(d.get('citations',[])))"
```

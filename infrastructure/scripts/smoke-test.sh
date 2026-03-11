#!/bin/bash
# Phase 0 Infrastructure Smoke Test
# Checks the Docker health status of every required service.
# All containers must report "healthy" for the test to pass.
#
# Usage (from project root):
#   bash infrastructure/scripts/smoke-test.sh
#
# Prerequisites: Docker must be running and `docker compose up -d` must have completed.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0

# ─── Helper ──────────────────────────────────────────────────────────────────

check() {
  local label=$1
  local container=$2

  printf "  %-32s" "$label"

  local status
  status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "not_found")

  case "$status" in
    healthy)
      echo -e "${GREEN}✓  healthy${NC}"
      PASS=$((PASS + 1))
      ;;
    starting)
      echo -e "${YELLOW}⏳ starting (still warming up)${NC}"
      FAIL=$((FAIL + 1))
      ;;
    not_found)
      echo -e "${RED}✗  container not found — is the stack running?${NC}"
      FAIL=$((FAIL + 1))
      ;;
    *)
      echo -e "${RED}✗  $status${NC}"
      FAIL=$((FAIL + 1))
      ;;
  esac
}

# Also verify a one-shot init container exited 0
check_init() {
  local label=$1
  local container=$2

  printf "  %-32s" "$label"

  local exit_code
  exit_code=$(docker inspect --format='{{.State.ExitCode}}' "$container" 2>/dev/null || echo "missing")

  if [ "$exit_code" = "0" ]; then
    echo -e "${GREEN}✓  completed (exit 0)${NC}"
    PASS=$((PASS + 1))
  elif [ "$exit_code" = "missing" ]; then
    echo -e "${RED}✗  container not found${NC}"
    FAIL=$((FAIL + 1))
  else
    echo -e "${RED}✗  exited with code $exit_code${NC}"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Checks ──────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}   Phase 0 Infrastructure Smoke Test           ${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

echo -e "${BOLD}Storage:${NC}"
check         "MinIO"                   "minio"
check_init    "MinIO bucket init"       "minio-init"

echo ""
echo -e "${BOLD}Database & Cache:${NC}"
check "PostgreSQL"                      "postgres"
check "Redis"                           "redis"
check "ClickHouse"                      "clickhouse"

echo ""
echo -e "${BOLD}Iceberg REST Catalog:${NC}"
check "Nessie"                          "nessie"

echo ""
echo -e "${BOLD}Workflow Orchestration:${NC}"
check "Temporal"                        "temporal"
echo -e "  ${YELLOW}Note: Temporal UI has no health check — verify manually at http://localhost:8080${NC}"

echo ""
echo -e "${BOLD}Vector Database:${NC}"
check "Qdrant"                          "qdrant"

echo ""
echo -e "${BOLD}Agent Tracing:${NC}"
check "Langfuse"                        "langfuse-server"

echo ""
echo -e "${BOLD}Observability:${NC}"
check "Prometheus"                      "prometheus"
check "Grafana"                         "grafana"

# ─── Results ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}───────────────────────────────────────────────${NC}"
echo -e "${BOLD}  Results: ${PASS} passed, ${FAIL} failed${NC}"
echo -e "${BOLD}───────────────────────────────────────────────${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}${BOLD}SMOKE TEST FAILED${NC}"
  echo ""
  echo "Troubleshooting:"
  echo "  docker compose -f infrastructure/docker-compose.yml logs <service-name>"
  echo "  docker inspect <container-name> | jq '.[0].State'"
  exit 1
else
  echo -e "${GREEN}${BOLD}SMOKE TEST PASSED — Phase 0 infrastructure is healthy.${NC}"
  echo ""
  echo "Service endpoints:"
  echo "  MinIO console     → http://localhost:9001"
  echo "  Nessie UI         → http://localhost:19120"
  echo "  Temporal UI       → http://localhost:8080"
  echo "  Qdrant dashboard  → http://localhost:6333/dashboard"
  echo "  Langfuse          → http://localhost:3000"
  echo "  Prometheus        → http://localhost:9090"
  echo "  Grafana           → http://localhost:3001  (admin / \$GRAFANA_ADMIN_PASSWORD)"
  exit 0
fi

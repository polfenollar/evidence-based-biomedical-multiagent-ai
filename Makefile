# Evidence-Based Bio-Medical Multi-Agent System
# Root Makefile — convenience targets for the Docker Compose infrastructure stack.
#
# Usage:
#   make help          — list all targets
#   make env           — create .env from .env.example (first-time setup)
#   make up            — start all infrastructure services
#   make smoke-test    — run Phase 0 health check

COMPOSE_FILE := infrastructure/docker-compose.yml
ENV_FILE     := infrastructure/.env
COMPOSE      := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

.PHONY: help env up down restart logs ps clean smoke-test init-minio temporal-namespace \
        test test-unit test-integration test-chaos load-test scan sbom

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Setup ───────────────────────────────────────────────────────────────────

env: ## Create infrastructure/.env from .env.example (skip if already exists)
	@if [ -f $(ENV_FILE) ]; then \
	  echo ".env already exists — skipping. Edit it manually if needed."; \
	else \
	  cp infrastructure/.env.example $(ENV_FILE); \
	  echo "Created $(ENV_FILE) — edit it with real secrets before running 'make up'."; \
	fi

# ─── Lifecycle ───────────────────────────────────────────────────────────────

up: ## Start all infrastructure services in detached mode
	$(COMPOSE) up -d

down: ## Stop all infrastructure services (volumes preserved)
	$(COMPOSE) down

restart: ## Restart all infrastructure services
	$(COMPOSE) restart

clean: ## Stop and remove containers, networks, and ALL volumes (destructive)
	@echo "This will delete all persistent data (MinIO, PostgreSQL, Qdrant, etc)."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE) down -v --remove-orphans

# ─── Operations ──────────────────────────────────────────────────────────────

logs: ## Follow logs for all services (Ctrl-C to stop)
	$(COMPOSE) logs -f

logs-%: ## Follow logs for a specific service: make logs-temporal
	$(COMPOSE) logs -f $*

ps: ## Show service status
	$(COMPOSE) ps

smoke-test: ## Run Phase 0 infrastructure health check
	@bash infrastructure/scripts/smoke-test.sh

init-minio: ## Re-run MinIO bucket initialisation (idempotent)
	$(COMPOSE) run --rm minio-init

temporal-namespace: ## Register Temporal namespace 'biomedical' (if not already registered)
	$(COMPOSE) exec temporal temporal operator namespace describe biomedical 2>/dev/null \
	  || $(COMPOSE) exec temporal temporal operator namespace create biomedical --retention 30d

# ─── Individual service restart shortcuts ────────────────────────────────────

restart-%: ## Restart a specific service: make restart-nessie
	$(COMPOSE) restart $*

# ─── Testing ─────────────────────────────────────────────────────────────────

test: ## Run all unit tests
	python3 -m pytest tests/unit/ -q

test-unit: ## Run unit tests with coverage report
	python3 -m pytest tests/unit/ --cov=src --cov-report=term-missing -q

test-integration: ## Run integration tests (requires running stack)
	python3 -m pytest tests/integration/ -m integration -q

test-chaos: ## Run chaos/resilience tests (requires running stack + docker SDK)
	python3 -m pytest tests/chaos/ -m chaos -q

# ─── Phase 6: Production hardening ───────────────────────────────────────────

load-test: ## Run Locust load test (10 users, 60 s). Requires: pip install locust
	@command -v locust >/dev/null 2>&1 || { echo "Install locust: pip3 install locust"; exit 1; }
	locust -f tests/load/locustfile.py \
	  --host=http://localhost:8003 \
	  --users=10 --spawn-rate=2 --run-time=60s \
	  --headless --only-summary

scan: ## Scan Docker images for CVEs using Trivy (requires: docker pull aquasec/trivy)
	@echo "Scanning images for critical CVEs..."
	@for image in infrastructure-agent-api infrastructure-agent-worker \
	              infrastructure-audit-api infrastructure-ui; do \
	  echo "\n─── $$image ───"; \
	  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
	    aquasec/trivy:latest image --exit-code 0 --severity CRITICAL \
	    --quiet $$image:latest 2>&1 | tail -5; \
	done
	@echo "\nScan complete."

sbom: ## Generate SBOM (Software Bill of Materials) using pip-licenses
	@command -v pip-licenses >/dev/null 2>&1 || pip3 install pip-licenses -q
	@mkdir -p sbom
	pip-licenses --format=json --output-file sbom/sbom.json
	@echo "SBOM written to sbom/sbom.json ($$( python3 -c \"import json; d=json.load(open('sbom/sbom.json')); print(len(d))\" ) packages)"

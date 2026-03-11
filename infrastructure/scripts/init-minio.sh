#!/bin/sh
# MinIO bucket initialisation — idempotent.
# Runs inside the minio/mc container after MinIO is healthy.
# Re-running this script is safe: --ignore-existing prevents errors on existing buckets.
set -e

MC=/usr/bin/mc
ALIAS=local
ENDPOINT="http://minio:9000"

echo "init-minio: configuring alias..."
$MC alias set $ALIAS "$ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

echo "init-minio: creating buckets (idempotent)..."

# Iceberg warehouse — Nessie stores table data here
$MC mb --ignore-existing $ALIAS/iceberg-warehouse

# Langfuse media/blob storage
$MC mb --ignore-existing $ALIAS/langfuse-storage

# Ingestion staging — raw source files before Spark processing
$MC mb --ignore-existing $ALIAS/ingestion-staging

# Feast registry backup (optional, for S3-backed registry in future)
$MC mb --ignore-existing $ALIAS/feast-registry

echo "init-minio: buckets ready:"
$MC ls $ALIAS/

echo "init-minio: done."

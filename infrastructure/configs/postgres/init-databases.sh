#!/bin/bash
# Runs once on first PostgreSQL container start (via /docker-entrypoint-initdb.d).
# Creates the additional databases required by Nessie and Langfuse.
#
# Temporal's auto-setup image creates its own databases (temporal, temporal_visibility)
# when it first connects, so those are not listed here.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE nessie;
    CREATE DATABASE langfuse;
    CREATE DATABASE feast_registry;
EOSQL

echo "init-databases.sh: created databases: nessie, langfuse, feast_registry"

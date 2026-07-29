#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${BACKUP_DIR}/the_all_seeing_eye_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:?POSTGRES_USER requerido}" \
  -d "${POSTGRES_DB:?POSTGRES_DB requerido}" \
  --no-owner \
  --no-privileges \
  > "${OUTPUT_FILE}"

chmod 0600 "${OUTPUT_FILE}"
echo "Backup creado: ${OUTPUT_FILE}"

#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-all-seeing-eye-agent}"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ "${EUID}" -ne 0 ]; then
  echo "Este desinstalador debe ejecutarse con privilegios de administrador." >&2
  exit 1
fi

systemctl stop "${SERVICE_NAME}" || true
systemctl disable "${SERVICE_NAME}" || true
rm -f "${UNIT_FILE}"
systemctl daemon-reload

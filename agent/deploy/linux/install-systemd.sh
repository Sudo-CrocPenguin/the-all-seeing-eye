#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-all-seeing-eye-agent}"
INSTALL_DIR="${INSTALL_DIR:-/opt/the-all-seeing-eye}"
CONFIG_DIR="${CONFIG_DIR:-/etc/the-all-seeing-eye}"
ENV_FILE="${ENV_FILE:-${CONFIG_DIR}/agent.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT_TEMPLATE="${SOURCE_DIR}/agent/deploy/linux/all-seeing-eye-agent.service.template"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ "${EUID}" -ne 0 ]; then
  echo "Este instalador debe ejecutarse con privilegios de administrador." >&2
  exit 1
fi

install -d -m 0755 "${INSTALL_DIR}"
install -d -m 0750 "${CONFIG_DIR}"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude ".git" \
    --exclude ".venv" \
    --exclude ".mypy_cache" \
    --exclude ".pytest_cache" \
    --exclude ".ruff_cache" \
    "${SOURCE_DIR}/" "${INSTALL_DIR}/"
else
  cp -R "${SOURCE_DIR}/agent" "${SOURCE_DIR}/backend" "${SOURCE_DIR}/pyproject.toml" "${INSTALL_DIR}/"
fi

"${PYTHON_BIN}" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/.venv/bin/python" -m pip install -e "${INSTALL_DIR}"

if [ ! -f "${ENV_FILE}" ]; then
  install -m 0600 "${SOURCE_DIR}/agent/deploy/linux/agent.env.example" "${ENV_FILE}"
  echo "Configura ${ENV_FILE} con AGENT_BACKEND_URL y AGENT_TOKEN antes de validar el servicio."
fi

sed \
  -e "s|{{INSTALL_DIR}}|${INSTALL_DIR}|g" \
  -e "s|{{ENV_FILE}}|${ENV_FILE}|g" \
  "${UNIT_TEMPLATE}" > "${UNIT_FILE}"

chmod 0644 "${UNIT_FILE}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
systemctl status "${SERVICE_NAME}" --no-pager

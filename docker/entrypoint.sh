#!/bin/sh
set -eu

export N8N_PORT="${PORT:-${N8N_PORT:-5678}}"
export N8N_HOST="${N8N_HOST:-0.0.0.0}"
export N8N_PROTOCOL="${N8N_PROTOCOL:-https}"
export WEBHOOK_URL="${WEBHOOK_URL:-}"
export N8N_EDITOR_BASE_URL="${N8N_EDITOR_BASE_URL:-}"

mkdir -p /home/node/.n8n

IMPORT_MARKER="/home/node/.n8n/.telegram-assistant-workflow-imported-v1"
WORKFLOW_FILE="/opt/bootstrap/workflows/telegram-ai-assistant.json"

if [ -f "$WORKFLOW_FILE" ] && [ ! -f "$IMPORT_MARKER" ]; then
  n8n import:workflow --input="$WORKFLOW_FILE" || true
  touch "$IMPORT_MARKER"
fi

exec n8n start


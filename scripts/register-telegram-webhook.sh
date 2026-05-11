#!/bin/sh
set -eu

if [ ! -f .env ]; then
  echo "Missing .env file in the repository root." >&2
  exit 1
fi

set -a
. ./.env
set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is missing." >&2
  exit 1
fi

if [ -z "${WEBHOOK_URL:-}" ]; then
  echo "WEBHOOK_URL is missing." >&2
  exit 1
fi

WEBHOOK_ENDPOINT="$(printf "%s" "$WEBHOOK_URL" | sed 's:/*$::')/webhook/telegram-assistant"

PAYLOAD=$(cat <<EOF
{
  "url": "$WEBHOOK_ENDPOINT",
  "drop_pending_updates": true$(if [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then printf ',\n  "secret_token": "%s"' "$TELEGRAM_WEBHOOK_SECRET"; fi)
}
EOF
)

curl -sS \
  -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"


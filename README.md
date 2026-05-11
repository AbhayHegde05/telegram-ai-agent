# AI Telegram Assistant with n8n, Groq, Supabase, Render, and Docker

This repository is a complete production-ready Telegram AI assistant built around `n8n`, `Groq`, `Supabase`, `Docker`, and `Render`.

It is designed to be:

- modular enough to evolve
- scalable enough for multi-user use
- beginner-friendly enough to deploy without stitching missing files together
- restart-safe through persistent n8n storage

## What it does

The bot:

- receives Telegram messages through a webhook-driven n8n workflow
- responds with `llama-3.3-70b-versatile` via Groq's OpenAI-compatible API
- stores users, memories, and conversation history in Supabase
- isolates memory by Telegram user ID
- supports `/start`, `/help`, `/remember <fact>`, `/history`
- falls back to normal AI chat for any non-command message
- supports simple AI tool calling for memory and history access

## Architecture

```text
Telegram Bot API
  -> n8n Webhook
  -> AI Agent Orchestrator
     -> Supabase user upsert
     -> Supabase memory/history retrieval
     -> Groq planning call
     -> Local tool execution
     -> Groq final response call
     -> Supabase conversation persistence
  -> Telegram sendMessage
```

## Repository structure

```text
.
|-- .env.example
|-- .gitignore
|-- Dockerfile
|-- docker-compose.yml
|-- render.yaml
|-- README.md
|-- docker/
|   `-- entrypoint.sh
|-- docs/
|   |-- deployment-guide.md
|   |-- groq-setup.md
|   |-- telegram-setup.md
|   `-- troubleshooting.md
|-- scripts/
|   |-- build-workflow.ps1
|   |-- register-telegram-webhook.ps1
|   `-- register-telegram-webhook.sh
|-- supabase/
|   `-- schema.sql
|-- workflow-assets/
|   `-- ai-agent-orchestrator.js
`-- workflows/
    `-- telegram-ai-assistant.json
```

## Environment variables

Required runtime variables:

- `TELEGRAM_BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `GROQ_API_KEY`
- `N8N_BASIC_AUTH_PASSWORD`
- `N8N_HOST`
- `N8N_PROTOCOL`
- `N8N_PORT`
- `WEBHOOK_URL`
- `N8N_EDITOR_BASE_URL`
- `GENERIC_TIMEZONE`
- `TZ`

Recommended production variables included in `.env.example`:

- `N8N_BASIC_AUTH_ACTIVE`
- `N8N_BASIC_AUTH_USER`
- `N8N_ENCRYPTION_KEY`
- `TELEGRAM_WEBHOOK_SECRET`
- `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS`
- `N8N_RUNNERS_ENABLED`

## Quick start

1. Copy `.env.example` to `.env`.
2. Fill in Telegram, Supabase, and Groq secrets.
3. Run the SQL in [supabase/schema.sql](/c:/My%20Projects/Telegram%20bot/supabase/schema.sql:1) inside Supabase SQL Editor.
4. Generate the workflow file again if you change the orchestrator source:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-workflow.ps1
```

5. Start locally:

```powershell
docker compose up --build
```

6. Open `http://localhost:5678` for local setup, or your Render domain in production.
7. Register the Telegram webhook after the deployment URL is live:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register-telegram-webhook.ps1
```

## Local development notes

For local-only Docker testing, set these values in `.env`:

- `N8N_PROTOCOL=http`
- `N8N_EDITOR_BASE_URL=http://localhost:5678/`
- `WEBHOOK_URL=https://<your-public-tunnel-or-deployed-url>/`
- `N8N_SECURE_COOKIE=false`

Telegram requires a public HTTPS webhook URL, so fully local webhook testing needs a tunnel or a remote deployment.

## Render deployment summary

- Render builds the included `Dockerfile`
- n8n persists state under `/home/node/.n8n`
- attach a Render persistent disk at `/home/node/.n8n`
- `render.yaml` defines the web service, environment variables, and HTTP health check path
- the bundled entrypoint imports the workflow automatically on first boot

Full deployment instructions are in [docs/deployment-guide.md](/c:/My%20Projects/Telegram%20bot/docs/deployment-guide.md:1).

## Telegram commands

- `/start` introduces the assistant
- `/help` shows command help
- `/remember <fact>` stores a user-specific memory
- `/history` shows recent saved conversation history

## AI behavior

The orchestrator uses a two-step agent loop:

1. Groq plans a reply and optionally asks for tools in strict JSON.
2. The workflow executes supported tools:
   `remember_fact`, `get_history`, `get_memories`
3. Groq produces the final user-facing answer using tool results.

This keeps the workflow modular while avoiding credential-bound n8n nodes, making imports and Render deployments more predictable.

## Database design

Tables:

- `users`
- `messages`
- `memories`

The schema also includes:

- indexes on lookup and sort columns
- foreign-key-aware indexing
- RPC helper functions for workflow-safe reads and writes
- row level security policies compatible with server-side anon-key usage

## Example conversations

User:
`/remember My favorite IDE theme is Tokyo Night`

Assistant:
`Saved to memory: My favorite IDE theme is Tokyo Night`

User:
`What theme do I prefer?`

Assistant:
`You previously told me your favorite IDE theme is Tokyo Night.`

User:
`/history`

Assistant:
`Your recent conversation history:
You: /remember My favorite IDE theme is Tokyo Night
Assistant: Saved to memory: My favorite IDE theme is Tokyo Night`

## Docs

- [docs/telegram-setup.md](/c:/My%20Projects/Telegram%20bot/docs/telegram-setup.md:1)
- [docs/groq-setup.md](/c:/My%20Projects/Telegram%20bot/docs/groq-setup.md:1)
- [docs/deployment-guide.md](/c:/My%20Projects/Telegram%20bot/docs/deployment-guide.md:1)
- [docs/troubleshooting.md](/c:/My%20Projects/Telegram%20bot/docs/troubleshooting.md:1)

## Official references used

- n8n Docker and environment configuration: https://docs.n8n.io/hosting/installation/docker/
- n8n import commands: https://docs.n8n.io/hosting/cli-commands/
- n8n monitoring endpoints: https://docs.n8n.io/hosting/logging-monitoring/monitoring/
- Groq OpenAI compatibility: https://console.groq.com/docs/openai
- Groq model reference: https://console.groq.com/docs/models
- Render Blueprint spec: https://render.com/docs/blueprint-spec
- Render persistent disks: https://render.com/docs/disks
- Render health checks: https://render.com/docs/health-checks
- Render deploy behavior: https://render.com/docs/deploys
- Render environment variables: https://render.com/docs/environment-variables

# Deployment Guide

## 1. Prepare the services

You need:

- a Telegram bot token from BotFather
- a Supabase project
- a Groq API key
- a Render account

## 2. Configure Supabase

1. Open the Supabase dashboard.
2. Go to SQL Editor.
3. Run the full SQL from [supabase/schema.sql](/c:/My%20Projects/Telegram%20bot/supabase/schema.sql:1).
4. Copy:
   - project URL into `SUPABASE_URL`
   - anon key into `SUPABASE_ANON_KEY`

## 3. Configure environment variables

Create `.env` from `.env.example`.

Minimum required production values:

- `TELEGRAM_BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `GROQ_API_KEY`
- `N8N_BASIC_AUTH_PASSWORD`
- `N8N_BASIC_AUTH_USER`
- `N8N_ENCRYPTION_KEY`
- `TELEGRAM_WEBHOOK_SECRET`
- `WEBHOOK_URL`
- `N8N_EDITOR_BASE_URL`

For Render, keep:

- `N8N_PROTOCOL=https`
- `N8N_SECURE_COOKIE=true`
- `N8N_HOST=0.0.0.0`

## 4. Generate the workflow export

The repository already includes the generated workflow JSON. If you edit [workflow-assets/ai-agent-orchestrator.js](/c:/My%20Projects/Telegram%20bot/workflow-assets/ai-agent-orchestrator.js:1), rebuild the export with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-workflow.ps1
```

## 5. Deploy to Render

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, create a new Blueprint or Web Service from the repo.
3. If using the Blueprint flow, Render will read [render.yaml](/c:/My%20Projects/Telegram%20bot/render.yaml:1).
4. Add all secret environment variables that use `sync: false`.
5. Create a persistent disk for the web service.
6. Mount the disk at `/home/node/.n8n`.
7. Confirm your generated public domain.
8. Set:
   - `WEBHOOK_URL=https://<your-render-domain>/`
   - `N8N_EDITOR_BASE_URL=https://<your-render-domain>/`
9. Redeploy the service after saving those values.

The entrypoint imports the workflow automatically on first boot.

## 6. First login to n8n

1. Open your Render domain.
2. Use HTTP Basic Auth credentials if prompted.
3. Complete initial n8n owner setup if this is the first boot.
4. Confirm the workflow `Telegram AI Assistant - Groq + Supabase` exists.
5. Activate the workflow in the n8n editor.

## 7. Register Telegram webhook

Once the workflow is active and the deployment is public:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register-telegram-webhook.ps1
```

Linux or macOS:

```bash
chmod +x ./scripts/register-telegram-webhook.sh
./scripts/register-telegram-webhook.sh
```

## 8. Verify the system

Check these URLs:

- `https://<your-render-domain>/healthz`
- `https://<your-render-domain>/healthz/readiness`

Test in Telegram:

1. `/start`
2. `/help`
3. `/remember I like concise answers`
4. `What do you know about me?`
5. `/history`

## Render production checklist

- Persistent disk attached at `/home/node/.n8n`
- `N8N_ENCRYPTION_KEY` set and stable
- `TELEGRAM_WEBHOOK_SECRET` set
- workflow activated
- Render health check path set to `/healthz/readiness`
- persistent disk mounted at `/home/node/.n8n`
- public URL copied exactly into `WEBHOOK_URL` and `N8N_EDITOR_BASE_URL`

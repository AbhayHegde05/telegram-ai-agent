# Troubleshooting Guide

## The bot does not reply in Telegram

Check:

- the workflow is activated in n8n
- the Railway deployment is healthy
- the Telegram webhook is registered to `/webhook/telegram-assistant`
- `TELEGRAM_BOT_TOKEN` is correct
- `WEBHOOK_URL` matches the live public domain exactly

Run:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

## Railway deployment succeeds but the editor is unreachable

Check:

- `N8N_HOST=0.0.0.0`
- `N8N_PORT` resolves to Railway `PORT` through the entrypoint
- `N8N_EDITOR_BASE_URL` is your exact public domain
- `N8N_PROTOCOL=https` in production

## The workflow imported but is missing after restart

Check the Volume mount path:

```text
/home/node/.n8n
```

If the volume is not attached there, n8n data does not persist.

## Supabase writes fail

Check:

- `SUPABASE_URL` is the project URL, not the dashboard URL
- `SUPABASE_ANON_KEY` is correct
- [supabase/schema.sql](/c:/My%20Projects/Telegram%20bot/supabase/schema.sql:1) ran successfully
- the RPC functions exist
- RLS policies were created

## Groq calls fail

Check:

- `GROQ_API_KEY` is valid
- `GROQ_BASE_URL=https://api.groq.com/openai/v1`
- `GROQ_MODEL=llama-3.3-70b-versatile`

If the model or key is invalid, the assistant falls back to a temporary-error reply.

## Telegram says the webhook is failing

Common causes:

- workflow inactive
- wrong domain in `WEBHOOK_URL`
- HTTPS not available
- `TELEGRAM_WEBHOOK_SECRET` mismatch
- Railway service not passing readiness yet

## n8n asks for onboarding or owner setup

That is expected on the first boot of a fresh instance. Complete it once. After that, the workflow and instance data persist on the mounted volume.

## The bot remembers data for the wrong user

This repository isolates state by `telegram_id`.

Check:

- incoming payload contains the expected `from.id`
- Supabase rows use the correct `telegram_id`
- you are not manually editing rows with the wrong user ID

## Local Docker works but Telegram webhook still fails

Telegram cannot call `localhost`. Use either:

- Railway deployment
- a public HTTPS tunnel that forwards to local n8n


# Telegram Setup Guide

## Create the bot

1. Open Telegram.
2. Start a chat with `@BotFather`.
3. Run `/newbot`.
4. Choose a bot name.
5. Choose a unique bot username ending in `bot`.
6. Copy the bot token into `TELEGRAM_BOT_TOKEN`.

## Recommended BotFather settings

Run these commands in BotFather:

- `/setprivacy` -> Disable privacy mode if you want broader group behavior
- `/setdescription` -> Add a short description
- `/setabouttext` -> Add a summary
- `/setuserpic` -> Optional branding
- `/setcommands`

Suggested command list:

```text
start - Start the assistant
help - Show help and commands
remember - Save a memory
history - Show recent conversation history
```

## Register the webhook

After your Railway service is live and the workflow is active:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register-telegram-webhook.ps1
```

This registers:

```text
https://<your-domain>/webhook/telegram-assistant
```

If `TELEGRAM_WEBHOOK_SECRET` is set, the script also configures Telegram to send that secret in the `X-Telegram-Bot-Api-Secret-Token` header. The workflow validates it before doing any work.

## Webhook validation

To inspect webhook status manually:

```text
GET https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

Healthy signs:

- `ok: true`
- correct webhook URL
- no recent delivery errors

## Common Telegram gotchas

- Telegram requires a public HTTPS endpoint.
- Webhook URL must match your deployed public domain.
- The n8n workflow must be active, not just imported.
- If you rotate the bot token, you must update Railway and re-register the webhook.


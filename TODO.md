# TODO

## Investigation + Fix Webhook Delivery (/start not responding)
- [ ] Fix FastAPI webhook routing for Vercel: ensure correct route is deployed (likely missing correct `vercel.json` for `/api/(.*)` mapping).
- [ ] Fix PTB webhook lifecycle for serverless: ensure `ptb_app.initialize()` + `ptb_app.start()` is correct (or avoid `start()` if unsupported).
- [ ] Ensure PTB can send messages: add explicit API call logging and remove silent exception swallowing in `/start` and webhook diag.
- [ ] Patch `start()` to never assume `update.message` exists; fallback to `context.bot.send_message(chat_id, ...)`.
- [ ] Patch `keyboards/menu.py start_menu()` to also fallback when `update.message` missing.
- [ ] Add per-update logs: handler matching + `/start` entry + before/after `process_update()`.
- [ ] Run local test using a sample Telegram update payload against `/api/webhook`.

## Validation
- [ ] Deploy and trigger `/start`.
- [ ] Confirm: webhook POST returns 200, `/start` handler log appears, and at least one `sendMessage` request is logged.

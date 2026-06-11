# TODO

## Investigation + Fix Webhook Delivery (/start not responding)
- [x] Fix PTB webhook handling so `/start` works when `update.message` is missing.
- [x] Add high-signal logs for handler entry + update parsing.
- [ ] Remove/disable per-request diagnostic Telegram sends.
- [ ] Fix cold-start blocking in `/api/webhook` (move PTB init/start out of request path).
- [ ] Prevent blocking supabase calls inside async handlers (offload to thread).

## Validation
- [ ] Deploy and trigger `/start`.
- [ ] Confirm: request returns quickly (no indefinite “Waiting for response”).
- [ ] Confirm: Telegram replies are sent.
- [ ] Confirm: cold start doesn’t add >10s latency.


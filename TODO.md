# TODO

## Investigation + Fix Webhook Delivery (/start not responding)
- [x] Fix PTB webhook handling so `/start` works when `update.message` is missing.
- [x] Add high-signal logs for handler entry + update parsing.
- [ ] Remove/disable per-request diagnostic Telegram sends.
- [ ] Fix cold-start blocking in `/api/webhook` (move PTB init/start out of request path).
- [ ] Prevent blocking supabase calls inside async handlers (offload to thread).

## Supabase schema permissions (RLS) — FilmNChill session storage
- [ ] Edit `supabase/schema.sql` to fix RLS permission grants for `service_role` (remove broken `revoke ... from service_role`) and add missing anon policies.
- [ ] Deploy updated SQL changes / apply via Supabase SQL editor.
- [ ] In Vercel env vars ensure `SUPABASE_SERVICE_ROLE_KEY` is set (and not falling back to anon).

## Validation
- [ ] Hit `GET /api/health/config` and confirm `supabase_service_role` is `true`.
- [ ] Trigger `/start`.
- [ ] Confirm rows are written to:
  - `public.bot_sessions`
  - `public.session_events`


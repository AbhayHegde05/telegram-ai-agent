# TODO

- [ ] Add/align Supabase env var handling so `SUPABASE_ANON_KEY` and `SUPABASE_KEY` both work
- [ ] (Optional) Add debug logging around history writes to confirm inserts happen
- [ ] Verify that `handle_brief_or_review_input()` is triggered in webhook mode and that `current_feature` becomes `brief`/`review`
- [ ] Run a quick local smoke test (if possible) to confirm rows are inserted into `user_history`


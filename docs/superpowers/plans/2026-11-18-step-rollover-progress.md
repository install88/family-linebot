# Execution ledger — 2026-11-18-step-rollover.md

- Approved approach: user explicitly requested implementation of independent daily App counting; execute inline without another planning approval round.
- Isolation: managed-worktree tool rejected both calls; created external Git worktree C:/Users/insta/family-linebot-rollover on codex/fix-step-day-rollover. Original main checkout and modified CLAUDE.md are untouched.
- Android is not a Git repository. Preserve originals in C:/Users/insta/step-counter-app/backups/day-rollover-20261118-221113 and implement in the established ASCII build folder, then sync only touched sources.
- Ruling: preserve existing 49+ same-day steps as a partial total; no reconstruction of Xiaomi's 250 or DB backfill, because the original observations are insufficient.
- Pre-flight shared interface: Android immutable date/status payload must match Flask validation; waiting writes config only and old apps remain compatible.
- Production backend push/publication remains a final step; local implementation and validation proceed first.
- Task 1: complete locally — 16 unittest tests pass. Initial tests proved stale-date acceptance; reviewer regressions proved metadata failure, retry, ordering and waiting precedence issues before fixes.
- Task 2: complete — 15 pure counter tests pass; assembleDebug / assembleDebugAndroidTest / lintDebug pass with zero lint errors. Signing identity matches 1.0.1.
- Task 3: instrumentation migration/rebase/activity and alarm-denied/allowed tests pass. Emulator's Google background startup initially caused environmental ANRs; disabled Google background packages only in the read-only disposable emulator, then reproduced the actual rebase failure and verified the fix.
- Review: one independent most-capable reviewer found five important issues; each addressed in the single fix pass with regressions. No minor findings were deferred.
- Ruling: preserve count and quality together as the durable latest snapshot in config before steps history, with retry recovery — avoids schema changes and falsely complete reports; this assumes the current single-process deployment, and multi-worker scaling would require a DB transaction/RPC.
- Redmi upgraded in place to 1.0.2, nickname/URL/49 partial steps retained; wake-up sensor selected and an HTTP 200 upload observed. Background walking validation passed: 49 → 81, PID 7919 unchanged. User explicitly authorized GitHub main push / Render publication.

# Reliable daily step counting

User approved independent App counting and asked us to implement it. Preserve the existing Android/Flask/Supabase stack, nickname and saved counts; do not try to match Xiaomi's private counter or edit historical DB rows.

The service owns a persistent daily counter; the Activity only reads it. Use the sensor event's occurrence time in Asia/Taipei, not callback arrival time. Keep the last hardware reading across dates, count the first new-day delta when a prior baseline exists, ignore old/out-of-order samples and handle reboot/reset without negative counts. A missing baseline or a gap crossing unobserved whole days is partial tracking, not a claimed complete total. No current-date sensor state means waiting, never yesterday's value.

Uploads contain an immutable snapshot with step_date, sensor_at, status, partial, app_version and a random app-local device_id. The API accepts legacy clients, rejects mislabeled/future/old sensor data from new clients, and uses sensor time for the existing time column (created_at remains DB receipt time). Waiting updates write only a latest-status JSON entry in the existing config table. LINE shows waiting or partial counts explicitly. No DB migration.

Prefer a wake-up step counter when available, falling back to the default counter. Bound CPU wake time around scheduled upload; preserve the existing exact-alarm permission fallback. App diagnostics retain recent raw samples and uploads in app-private storage. No always-held wake lock.

Alternatives: only suppressing yesterday's uploads is smaller but leaves duplicated counters and lost first batches; reading Xiaomi's native app adds an unverified external dependency. The approved approach fixes the independent counter and its upload boundary together.

Acceptance: unit tests across midnight, delayed events, reboot, reordering, partial migration and JSON/date validation; emulator alarm-denied/allowed regression; real Redmi install preserving settings and current count, background walk and reopening, plus no crash/signature verification. Do not claim a physical overnight run until one has actually occurred. Production backend publication is a separate final step after the implementation is reviewable.

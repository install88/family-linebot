# Reliable Daily Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** prevent prior-day counts being reported as today's steps and make daily counting observable and consistent.
**Architecture:** pure Kotlin counter plus SharedPreferences store owned by StepService; backwards-compatible Flask validation and status records using the existing config table.
**Tech Stack:** Kotlin 1.9, Android API 26+, Gradle, Flask, Python unittest.
**Spec:** ../specs/2026-11-18-step-rollover-design.md

## Global Constraints
- Asia/Taipei dates; preserve nickname, URL and existing same-day count during upgrade.
- No deletion/backfill of historical DB data; no required schema migration.
- Legacy clients continue to work. New invalid-date payloads never enter steps.
- UI never independently writes the counter. Uncertain first-day/reboot data is labeled partial.
- Preserve exact-alarm permission fallback, stop behavior and settings.

## Review Focus
- Delayed sensor event from yesterday must not be labeled today.
- A first batch crossing midnight must not be silently zeroed out.
- A reboot or hardware reset must not erase accumulated same-day steps.
- Permissions denied or no sensor must not cause a startup crash.
- A network delay crossing midnight must not insert stale data under a new date.

### Task 1: API validation and status reporting
Files: bot.py, tests/test_step_uploads.py.
Interface: POST /steps accepts optional step_date/sensor_at/status/partial/app_version/device_id; status waiting writes config, valid observations write steps plus status.
- [ ] Write and run tests proving stale-date uploads currently get accepted and missing statuses are invisible.
- [ ] Implement validation, DB error handling, status-aware LINE rendering, legacy compatibility.
- [ ] Run complete Python unittest suite with network/LINE boundaries replaced by in-memory fakes.

### Task 2: Android daily state and ownership
Files: DailyStepCounter.kt, StepStore.kt, StepService.kt, MainActivity.kt, AlarmReceiver.kt, BootReceiver.kt, app/build.gradle.kts, src/test/.../DailyStepCounterTest.kt.
Interface: CounterState + DailyStepCounter.record(...); StepStore.record/snapshot; Activity reads StepStore; service uploads snapshots.
- [ ] Write pure counter regression tests for date transitions, first-batch retention, clock ordering, reboot/reset, waiting and partial migration.
- [ ] Implement shared counter and store, event occurrence time, bounded upload wake lock, safe sensor/permission handling and diagnostics.
- [ ] Remove Activity sensor ownership and repair the pre-existing source-only duplicate companion object using the working receiver as baseline.
- [ ] Test and build version 1.0.2 (code 3), retaining signing identity.

### Task 3: integration and delivery
- [ ] Run emulator API/permission scenarios and complete suites, lint/build.
- [ ] Fresh reviewer examines both boundaries and Android state transitions; fix important findings with regression tests.
- [ ] Install upgrade on the connected Redmi only after tests/signature verification and back up its App prefs first.
- [ ] Verify real background counting/reopen/upload evidence without altering historical DB rows.
- [ ] Copy APK to Desktop, sync touched Android sources to the original source folder, document validation and pending production backend publication.

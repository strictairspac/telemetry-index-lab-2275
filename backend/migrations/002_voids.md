# Schema v2 — 作废校准与报告判定

v1 created `users`, `audits`, `workloads`, `candidates`, `experiments`, `telemetry`.

v2 adds:

- `experiments.evidence` — per-record telemetry ids read by the trial (baseline ∪
  candidate), plus the result checksum. NULL for reports published before v2.
- `experiments.report_state` — `valid` / `invalid` / `unverified`; NULL until published.
- `experiments.invalid_reason` — operator-facing reason shown on the report page; the
  report id is never removed or renumbered.
- `experiments.void_ids` — voids that caused the judgement.
- `experiments.void_epoch` / `experiments.published_at` — publish bookkeeping.
- `telemetry_voids` — one confirmed calibration decision: sensor, window, reason,
  actor, unique `dedupe_key` (idempotent retry).
- `telemetry_void_items` — materialised void membership (void_id, telemetry_id),
  unique per pair, indexed by telemetry_id.
- `void_guard` — singleton row; publish and confirmation take it `FOR UPDATE`, so a
  report published concurrently with a confirmation cannot escape judgement.

New trials exclude voided rows through `NOT EXISTS (... telemetry_void_items ...)`.
Historical reports are judged by intersecting stored evidence with void items; their
SELECTs are never re-executed. Evidence-less old reports whose snapshot window
overlaps a void are marked `unverified` instead of `invalid`.

Applied automatically on startup by `src/config/schema.py` (create missing tables,
add missing columns). No existing column is altered or dropped.

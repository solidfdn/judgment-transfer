# Release 1.0.29 status

Prepared on 2026-10-15. No deployment or LIVE success is claimed.

## Evidence

Owner-reported run `run_af7be10a5c65a7c026708a1b25f4ef0e` has two completed development tasks, one failed task and one pending task. Failed trace `trace_fb05bed876da42ed94e35bb5b846b6e8` records zero chunks on both attempts, a local 10-second first-text cancellation and then the remaining 8.549-second total-window limit. The total elapsed time was 20,051 ms. Recorded cumulative ledger: 526 calls, USD 17.64170399999999. These are supplied diagnostics, not independently fetched cloud records.

## Bounded correction

Decisions now have one attempt, 35 seconds to first text and at most 60 seconds overall. Complete STOP responses and existing validation remain mandatory. No automatic second decision attempt. Workflow, extraction and question policies are unchanged. A longer wait does not guarantee a successful response.

The existing six PDF readings, case confirmations, approved version 0, historical traces, usage and grants remain intact. A distinct four-case baseline is necessary because code/settings are pinned per run. The old partial run is preserved. The controller checks that its two completed tasks, failed task, pending task, receipts and traces remain unchanged. Subsequent comparison must use the new baseline and same protocol.

The authorized gate uses at most four decision calls, two question calls and one teaching call. It stops before rule approval or execution on the two holdout cases. It reuses the previously authorized named owner explanation, without attributing AI output to the owner. All generated conditions remain unapproved for inspection.

## Verification

- `stream129_offline.json`: 22 focused checks with SDK/HTTP doubles, including actual asynchronous cancellation and stream cleanup.
- `baseline129_offline.json`: 10 checks with real service/evidence code and explicit model/API doubles; confirms preservation, no duplicate confirmations/imports, separate new run, restart idempotency and response-loss recovery.
- Package integrity and unchanged deployment protection functions checked during packaging.
- New LIVE baseline, rule proposal quality, post-supplement comparison and holdout execution: not yet verified.

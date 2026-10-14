# 1.0.24 deployed source-review gate — 2026-10-14

The owner reported successful deployment, served asset verification and preservation of historical records/counters before the source gate.

The actual source review failed with `INVALID_INPUT`, request `req_1df21b07b83ca56c5b4aa1b3`, workspace `ws_1fc7f906adcf832815c6347e20fde077`. It consumed one generation and zero judgment calls. The ledger changed from USD 16.692693900000005 / 510 calls to USD 16.744161300000005 / 511 calls, an increase of USD 0.0514674. The decision count remained 251. This error is returned by the application validation path; it is different from the 1.0.23 provider 400. The actual saved provider answer and exact failing check remain to be inspected.

The gate's report omitted the application's error message. Service-level observation/evidence validation failures do not attach the returned model trace to their exception, so the new administrator trace diagnostic was not present. This omission is a diagnostic defect; it does not justify changing acceptance checks or calling the model again.

`releases/jt_inspect_124.py` reads the exact workspace, fictional-source metadata and cached application error using Firestore GET requests. It locates the single corresponding saved model result and replays the existing 1.0.24 validators in memory. It prints failing paths, evidence locations and bounded quotations from the fictional policy. It uses the existing pinned Cloud Shell environment without installation, deployment, application POSTs, new model calls or cloud writes. No original file, result, approval or counter is changed. This helper is separate support tooling, not a new application release.

PDF reading, before/after case execution, reserved-case testing and rendered browser acceptance remain pending. No successful review or automation-readiness result is claimed.

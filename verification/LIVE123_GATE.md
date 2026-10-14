# 1.0.23 deployed source-review gate — 2026-10-14

The owner reported successful deployment, asset verification and unchanged historical usage/records. The real browser showed Version 1.0.23.

The ordinary user interface successfully created a separate workspace and saved the fictional expense policy. The reviewer field was explicitly labelled `Codex (test verification)`; no owner approval was fabricated.

One `Organize the work` action was attempted. It returned HTTP 503 / `MODEL_FAILED` at `/requirements/review`, request ID `req_8935d9f32f48df24cbd78249`. The UI does not expose the underlying saved provider trace. Provider attempts, tokens and actual cost are not yet known. No manual retry was sent. The requirements gate has **not passed**; PDF case reading, before/after runs and history acceptance remain pending.

`releases/jt_diagnose_123.py` is a bounded read-only Cloud Shell helper. It uses the existing logged-in identity and existing project, reads saved traces and budget counters, and prints only selected diagnostics. It neither calls a model nor writes cloud state, prints credentials, changes access settings or reruns the old evaluation. It is independent support tooling and does not change the deployed application or package manifest.

## Diagnostic returned by the owner

The helper scanned 498 saved traces without a model call or cloud write. The relevant trace is `trace_690fb8c3e79449f3a38ee0bbfc10e840`, created at `2026-10-14T13:40:38.331009Z`. Its only generation attempt failed with provider HTTP 400 / `INVALID_ARGUMENT`, message `Request contains an invalid argument.` Total elapsed time was 3,254 ms; generation failure time was 2,654 ms. This is a request rejection, not a demonstrated budget or call-limit failure.

The application ledger reported USD 16.692693900000005 and 510 generation attempts. The failed attempt retained USD 0.1394712 as a conservative reservation because no provider usage was returned; this is not verified invoiced cost. The authorized USD 100 ceiling and owner-bound 40/24/4 validation allowance remain recorded; retry use was zero.

The exact invalid argument is not identified by the provider message. A complex bounded response schema is the working diagnosis. Release 1.0.24 simplifies only the extraction wire grammar, retains strict server validation and adds an explicitly requested, journalled deployed source-review gate. No successful 1.0.24 provider result is claimed by this diagnosis.

# Standalone workflow preparation 125.1 — 2026-10-14

Category: execution verification, within the existing authorized document and
before/after validation. The deployed application remains 1.0.25 with code hash
`ec550774dd59e6211d349e9671cfe793cfe73d75518f678c3066277aea33a471`.

Cause: the real source-review gate passed, but the actual generated workflow
has not been inspected. Case reading depends on its declared fields and on
explicit human approval; using an author-written fixture as the AI-generated
workflow would not demonstrate the requested product behavior.

Changed: the separate `releases/jt_prepare_125.py` controller reuses the passed
review, journals one actual `/domains/draft` request, checks unchanged approval,
source, case, history and old-study state, checks the bounded usage delta, and
prints/saves the actual conditions for review. An optional failure-only
read-only inspection retrieves the exact saved trace and validates it in memory.
No installed source, manifest, model configuration, approval requirement,
dependency, cloud access policy, budget or previously issued installer changes.

Verification: `verification/check_prepare125.py` and its recorded 39 checks
cover saved success/failure, lost-response reconciliation, wrong inputs,
unrelated usage/state changes, unapproved LIVE provenance, complete review
preview, API operation boundaries and read-only saved-answer diagnosis.
All external responses in these checks are explicit doubles. Actual LIVE
workflow preparation remains pending owner execution in Cloud Shell.

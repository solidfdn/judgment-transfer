# Judgment Transfer 1.0.25 — exact source citation recovery

The provider request now succeeds. The diagnosed 1.0.24 failure was caused by five finding citations that joined lines or abbreviated quotations with ellipses. The response shape and observation/perspective semantics passed; the existing exact source-reference check correctly refused the nonliteral quotations.

The new review path first applies the original exact validator. For a failed textual reference, it verifies the same source identifier, version hash and locator; it then accepts only a unique, ordered alignment of the supplied literal fragments within that location. Whitespace is restored from the source. For review findings and questions, explicit spaced ellipses may be expanded to the complete original span, including any omitted qualifications or negation. Raw observations permit whitespace restoration only. The result must pass the unchanged exact validator. Different words, changed numbers/negation, wrong source/hash/location, reordered or ambiguous matches and excessive searches remain rejected. This verifies textual provenance, not the correctness of the AI's interpretation or authorization to execute work.

The original model response remains unchanged in its trace. The accepted review records the original and restored references plus their method. No business values, rules, approvals, decisions, past results or counters are repaired or overwritten. Future prompts request short continuous verbatim quotations without ellipses. Administrator failures now include the post-model validation path, and the CLI retains the application error message.

## Completed local checks

- `citations_125.json`: 29 checks covering all five actual reported quotations, unchanged exact validation, negative cases, bounded/ambiguous matching, PDF whitespace, raw-response retention, current service integration, in-memory preflight and administrator diagnostics. Other response fields are explicit synthetic test data; a complete LIVE response was not reconstructed locally.
- `release_gate_125.json`: 29 installer/API/gate checks with transport doubles, including the 1.0.24 baseline, saved-result/lost-response behavior, retained validation messages and stopping before deployment on a failed saved-answer check.
- Package hashes and prior installer bytes are checked during packaging. Original interface assets, fixtures, contracts and completed study records are retained. No dependency, model, IAM or budget change.

## Required deployment sequence

The single release command with `--deploy --verify-source --reviewer` first runs the new validator against the exact cloud-saved 1.0.24 answer in memory, using Firestore GETs and the existing pinned Python environment. It makes no new model call or cloud write. If the check fails, it stops before deployment. Its local report is `.jt/upgrades/1.0.25/saved-review-check.json`.

After this passes, the installer deploys and verifies historical exports/counters and served assets, then issues one new LIVE source-review request on the same fictional source/workspace under a new, journalled 1.0.25 request key. The existing maximum is two generation attempts; the existing cumulative USD 100 ceiling and 40-call allowance apply. Previous failures and their checkpoints remain. Repeating the command reads a completed result or reconciles the same request, without fresh generation after a saved failure.

The complete saved-answer preflight and new deployed review are pending execution by the owner. PDF case reading, before/after execution, reserved-case verification and rendered browser acceptance remain pending. No automation-readiness or award outcome is claimed.

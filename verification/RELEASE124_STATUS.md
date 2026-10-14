# Judgment Transfer 1.0.24 — source-review correction

The concrete failure is the 1.0.23 source review's provider 400 / INVALID_ARGUMENT. Google did not identify an individual argument. Its structured-output documentation lists bounded-array/schema complexity as a possible cause. This is a bounded corrective candidate until the deployed gate succeeds.

Extraction now uses a compact response grammar containing the same fields, types, required properties and enums. Array counts, text lengths and identifier patterns remain enforced by the original JSON Schema after generation. Exact source references, one-of-each review perspective and approval requirements remain mandatory. The full schema is no longer duplicated in the extraction system prompt. Decision, domain drafting and rule drafting transports/prompts remain unchanged; dependencies, model and budget limits are unchanged.

## Verification performed

- `source_contract_124.json`: 22 targeted checks with actual adapter/service code and JSON Schema validation, using explicit provider doubles. Covers compact request construction, unchanged strict acceptance, evidence rejection, non-retry of 400, and bounded administrator diagnostics. No real Google request was sent.
- `release_gate_124.json`: 24 targeted installer/gate checks with explicit HTTP doubles. Covers the 1.0.23 baseline, resumability, saved failures, lost-response recovery without duplicate generation, and rejection of unexpected usage.
- Historical source files, original 216-case recorded evidence (including four failures), prior installers and unchanged interface assets are retained. Package hashes are checked before publishing. Cloud-side export and usage preservation are checked by the installer before the optional source gate.

## Deployment gate

`--deploy --verify-source --reviewer "Shinji Okada"` updates the app, then submits one real review of the fictional public expense policy through the actual deployed API. The existing adapter permits at most two generation attempts. It uses the existing allowance and cumulative USD 100 ceiling. The gate requires six perspectives, observed evidence, at least one question, matching source hashes and no judgment execution. It stores the full review and a named verification report. It does not approve a workflow or FIX a decision on the operator's behalf.

The installer and gate have separate checkpoints. Repeating the same command reads the saved result or reconciles the same idempotent request; it does not issue a fresh generation after a saved failure. Administrator errors include this request's bounded stage/code/trace identifier, without prompts, evidence text, model output or credentials.

Real Google acceptance, PDF intake, before/after case execution, held-out case verification and the rendered browser walkthrough remain pending. A passed source review alone is not proof of automation readiness or award merit.

## Product direction retained from the owner's feedback

Separating deterministic control from AI interpretation is not, by itself, a differentiator. The demonstration must reveal a concrete judgment condition missing from ordinary work materials; ask the owner a useful question; show what changes after the approved explanation on the same cases and on cases not used for the explanation; retain necessary human decisions; and compare the dated, named evidence and judgment records. The reviewer should be able to challenge a condition and understand the resulting boundary. This is the acceptance target, not a claimed live result. Additional screens, dependency graphs and architecture export are not added by this defect correction.

Technical reference, checked 2026-10-14: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output

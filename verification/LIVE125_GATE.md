# 1.0.25 deployed source review — owner-reported result

On 2026-10-14 the owner supplied the completed release command's output:

- Deployment and existing source/approval/usage preservation checks completed.
- Source review: `PASSED`, six perspectives and one clarification question.
- Workspace: `ws_1fc7f906adcf832815c6347e20fde077`.
- Review trace: `trace_62e5bd652ea8480b8a8c4372b7b9cdb8`.
- Model calls: one; judgment calls: zero.
- Ledger calls: 511 → 512; ledger decisions: 251 → 251.
- Recorded cumulative amount: USD 16.744161300000005 → 16.825037100000003.
- The earlier failures and their traces remain part of the history.

This establishes a real successful source review under 1.0.25. It does not
establish successful workflow generation, PDF case reading, before/after
execution, reserved-case execution, or general usefulness across other jobs.
The complete saved-answer preflight JSON was not in the supplied excerpt;
deployment completion is reported here without inventing its detailed output.

The public app was reloaded in the browser and showed Version 1.0.25, the
English upload/explanation entry controls, and an explicit Continue saved work
control. No model operation was triggered in that browser check. This is an
entry-screen observation, not full rendered end-to-end acceptance.

## Next bounded check

`releases/jt_prepare_125.py` is a standalone controller for the unchanged,
deployed 1.0.25 package. It checks the exact passed source review and creates
one actual workflow draft through the application API. It sends only the
existing workspace ID and goal; it never supplies the fixture workflow,
reference correction rules, expected outcomes or case answers to the model.

The remaining risk is whether the materials can produce a valid, useful
unapproved workflow suitable for later document reading and case tests.
Scope: one draft request, at most two generation attempts under the existing
policy and cumulative USD 100 ceiling. Stop: draft saved for content review,
any failure, changed input/protocol, unrelated usage, or uncertain request.
No approval, FIX, case import, judgment, allowance change or deployment occurs.
Human approval remains a separate required application step after the actual
conditions have been inspected. A saved draft is not a business-correctness pass.

The journal lives at `.jt/upgrades/1.0.25/workflow-prepare.json`. Re-entry uses
the same application idempotency key, and a final result never regenerates.
Definitive failures retain their original details. A bounded read-only
Firestore inspection can capture the exact failed draft trace and replay the
unchanged domain/reference validators in memory. No model is invoked by that
inspection; neither a missing nor ambiguous trace is guessed.

The full condition draft and verification report are saved privately under
`deliverables/release125/`. The terminal preview includes all actual fields,
actions, effects, condition expressions, priorities and source quotations for
review. The installed package manifest and all original installers are unchanged.

Local verification: `prepare125_offline.json`, 39 controller/diagnostic checks
with explicit API and Firestore doubles, including an actual source-validator
failure replay. No new real model call, cloud write or workflow success was
claimed while preparing the command.

# 1.0.28 — correct absence checks and revise circular inputs

## Actual result and diagnosis

`LIVE127_GATE.json` retains the owner-provided Cloud Shell result: deployment
and one workflow generation succeeded, with no approval or case execution.
Draft `draft_de02342096acb2d71b73812c20c92ec8`, trace
`trace_492b06f2d9c64540b421cb66153deaf4`; cumulative calls 514 → 515,
ledger USD 17.017019400000002 → 17.0815845.

The generated draft still requires `is_receipt_accepted` as an input. The
1.0.27 prompt correction did not resolve that problem. The amount field also
combines a numeric observation with whether its payment is marked PAID.
A separate concrete implementation defect was exposed by the generated
`exists: false` rule: the core ignored the operand and tested presence, so a
present amount incorrectly matched the hold condition. The defect was
reproduced with the actual reported rule before correction. No real case was
executed with this draft.

## Corrections

- `app/core/models.py`: `exists:false` checks absence; true checks presence.
  Legacy null retains its previous presence meaning, preserving the old example
  contracts. Other operand types are rejected. The UI wording now distinguishes
  presence from absence. No contract file, historical result or approved rule
  is rewritten.
- `app/workflow_review.py`: conservative checks flag common policy-verdict
  inputs and amounts combined with status conditions. These are general naming
  and description checks, not an expense-specific branch or a complete semantic
  verifier. Explicit declarations to copy an existing source checkbox remain
  possible and still need source/human review. An empty issue list does not
  establish correctness or independence from all possible inferred fields.
- `app/service.py`: draft issues are displayed and recomputed before approval.
  Clearing client metadata cannot bypass the check. A revision must name the
  current same-owner, same-source, same-version unapproved draft. It keeps the
  old draft/trace and records `revision_of`; concurrent replacement stops the
  new commit. No automatic approval is added.
- The existing LIVE generation receives the previous draft and specific review
  findings as untrusted model output to correct against the original sources.
  It remains one streamed call, with the existing 120-second total and
  35-second first-text limits. No fixture, private answer or reference rule is
  supplied. MOCK does not substitute a revision.
- The English UI shows only flagged issues and a `Revise these inputs` button;
  approval remains hidden until those checks clear. All conditions still require
  the existing human review and named approval.

## Verification

- `workflow128_offline.json`: 57 actual core/service/request-building checks,
  including the reported existence defect, true/false/null behavior, invalid
  operands, server-side approval blocking, source-grounded exact quotations,
  previous-draft preservation, idempotency, ownership and concurrent replacement.
  The corrected draft used in these tests is an explicitly hand-edited test
  response, not a LIVE model output and never fed to the real generator.
- `prepare128_offline.json`: 58 controller checks with API/Firestore doubles;
  exact previous draft pinning, one revision call, no automatic retries or
  approval, refusal to pass a still-flagged answer, preserved old checkpoints,
  and legitimate UTC daily-counter rollover.
- `workflow128_ui.json`: 11 checks of actual JS functions using DOM doubles;
  visibility, primary action, escaping and presence/absence wording.
- The existing PDF intake/approval checks were rerun for the changed approval
  path: 47 checks using six real PDFs/12 pages and explicit model observations
  supplied by a test double. Their saved report is unchanged. This is not new
  LIVE document extraction or a rendered browser walkthrough.

## Resume and remaining acceptance

The exact-1.0.27 incremental installer retains prior state, grants, usage,
original 216 decisions (including four failures), and previous drafts. Its
optional workflow check pins the exact reported 1.0.27 draft and saves a local
copy. It calls `/domains/draft` once with `revise_draft_id`, then stops at a
reviewable unapproved revision or a saved failure. Remaining flagged inputs are
reported as a failed gate, never promoted to success or automatically retried.

No new cloud/model call or deployment was performed while preparing this patch.
The next real revised answer is not known yet. After its content is reviewed:
named approval, real PDF extraction and fact confirmation, same-case before/
after execution, two unused cases, history comparison and final browser review.

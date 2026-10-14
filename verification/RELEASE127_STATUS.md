# 1.0.27 — keep document facts separate from workflow decisions

The owner-provided 1.0.26 log is recorded in `LIVE126_GATE.json`. Deployment and
one streamed workflow generation succeeded: draft
`draft_63bab9807f91bd34bad6e8a05ef99486`, trace
`trace_0d6f14a4b9f14aaa81e450f7ba74f446`. Calls increased 513 → 514,
ledger USD 16.968660900000003 → 17.017019400000002; no approval or judgment
was created. This is an owner-reported result, not an independent cloud read.

The generated draft is not ready for approval. `is_receipt_accepted` asks the
case reader to supply the very policy judgment the workflow must make. It also
omits the receipt addressee needed for the source's stated personal-receipt
condition. `has_paid_status` loses which party's payment is paid. The source's
unknown company-addressed-document criterion must stay unresolved rather than
be encoded as a false acceptance fact.

## Limited correction

The shared `draft_domain` instruction now requires directly readable input
attributes, separately identified parties/statuses, source-defined conditions
in rules, and no input standing for the current workflow's acceptance decision.
A documented pre-existing external approval or checkbox is still a valid fact;
this is not a blanket ban on boolean fields or recorded approvals. The model
must retain raw facts needed for unresolved questions without inventing the
missing permission. No expense-specific branch, fixture, expected answer or
reference rule is added to the generation request.

This is a prompt correction, not a proof that arbitrary model outputs are
semantically valid. Original schema and evidence checks remain unchanged;
human review is still required. A fresh actual answer must be examined before
approval and case execution. The existing transport, model, timeout, retry,
budget, case-intake, UI and execution engine remain unchanged.

## Resume safely

The incremental installer accepts exact 1.0.26. After deployment, the optional
workflow gate requires the exact reviewed old draft ID, trace, preview hash and
completed 1.0.26 checkpoint. It archives the complete old draft locally, leaves
its cloud record and old checkpoint intact, and generates one new unapproved
draft from the same passed source review. Re-entry uses the same request key.
Unknown or edited old drafts stop before generation. Failure stops without
retry, approval, case reading or execution. Both drafts remain reviewable.

The controller also recognizes the application's existing UTC daily judgment
counter rollover. The cumulative call/decision counters, previous study and
USD 100 ceiling must still match. It does not reset usage or increase a limit.

## Verification and remaining work

`prepare127_offline.json`: 54 bounded controller checks with API/Firestore
doubles, including previous-draft preservation, exact draft pinning, no double
generation, stopped failures, no approval, and daily-counter rollover. They do
not establish LIVE model acceptance. Unchanged transport and product checks
are reused. Installer payload hashes and unchanged preservation functions are
checked before release.

Cloud deployment and a new workflow output remain pending the owner-run
command. After content review: named approval, real PDF reading and named fact
confirmation, before/after case execution, two unused cases, history comparison
and the final browser walkthrough. No human approval is supplied by this patch.

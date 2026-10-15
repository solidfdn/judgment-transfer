# Resume v128 PDF intake without regenerating saved answers

## Owner-reported LIVE result, 2026-10-15

The reviewed workflow was approved with the responsible person's name and time.
Approved draft: `draft_15eb1a11987f17c9a775f6cc813de5ce`. The first two PDFs passed.
The third was read successfully but rejected by the standalone verification gate.

- Workspace: `ws_1fc7f906adcf832815c6347e20fde077`.
- Saved traces: `trace_9367aa581b6a428b8c02be699424e163`,
  `trace_8e1a6d9b10a5431dbee4f12f54df5ba3`,
  `trace_a46182d860834b54a92b30e4c5e54b96`.
- Calls 516 → 519; judgments 0; no cases confirmed.
- Recorded cumulative USD 17.1859638 → 17.2575255.
- Third case employee amount and status both remain null. The reported status
  observation is OBSERVED/null with the exact quote
  `Employee card payment status: Not stated` on page 2.
- The console did not include the amount observation's full reference. Recovery
  checks its saved response against the PDF before allowing any new read.

This is owner-provided evidence, not an independent cloud read.

## Cause and correction

The app contract permits OBSERVED/null with evidence. This can record the literal
observation that a value is explicitly absent, while the business fact stays
unknown. The standalone verifier incorrectly required UNRESOLVED for every null
expected value. No amount was invented and no case was executed.

The recovery accepts this representation only for the two known absent values
when the raw fact is still null and the exact employee-specific `Not stated`
line appears in a literal quotation from the correct source/hash and PDF page.
It changes classification in a temporary comparison copy only. Raw responses,
traces, extracted facts and existing approval remain unchanged. Interpretation
notes are saved separately. A forged/irrelevant quotation, wrong page/source or
filled value still fails. INFERRED values are not silently promoted.

`releases/jt_resume_intake_128.py` embeds the exact prior controller with a hash
check, pins the reported three traces and approval ID, revalidates all three
saved readings and current workspace/usage, and resumes in a NEW checkpoint and
output directory. The original failed checkpoint is preserved byte-for-byte.
Only the three unread PDF uploads with their existing deterministic request keys
are allowed by its API write guard. No new approval, repeated extraction of the
first three files, case confirmation, judgment, deployment or new grant.

At most three new extraction requests / six provider attempts under the existing
transport and budget limits. Lost responses reuse existing receipts. A different
failure or changed workspace cannot be resumed by this command.

## Verification

`intake128_resume_offline.json`: 19 checks reproduce the original verifier failure
with the real service/PDF path and explicit model/HTTP doubles. Confirmed raw
answer preservation, original failed checkpoint preservation, only three new
reads, rejection of unsupported absence, no duplicate approval, lost-response
recovery and changed-state refusal. No real model call or cloud write in local
verification. Syntax compilation passed.

Pending: actual continuation and review/confirmation of all six case facts,
then same-case before/after execution, unused cases and final UI/history review.

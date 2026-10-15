# Confirm reviewed facts and prepare a baseline/supplement comparison

## Latest owner-reported LIVE evidence

On 2026-10-15 the continuation completed all six PDFs. Status
READINGS_READY_FOR_REVIEW; original three readings reused, three new extraction
calls, six extraction calls in total. Calls 516 → 522; recorded cumulative
USD 17.1859638 → 17.313204. Zero judgment calls, zero case confirmations and no
new workflow approval during continuation. Unknown employee-payment values in
case 03 remain null with the original OBSERVED classification and separately
recorded explicit-absence interpretation. This is owner-provided evidence,
not an independent cloud read.

All six trace IDs are pinned by `releases/jt_baseline_128.py`. Its command requires
`--confirm-cases --provide-reviewed-explanation --reviewer NAME`.

## Concrete operations

1. Confirm the six saved PDF readings unchanged, preserving null, original case
   identity, development/holdout split and document evidence. Set only the isolated
   initial review status to NEW. Each confirmation records the named reviewer.
2. Attach private author-prepared assessment labels under the complete reviewed
   policy using the existing import endpoint, with identical cases and case
   hashes. This preserves confirmed PDF provenance. Labels never enter solver,
   question or teaching prompts. They are targets, not measured results.
3. Run four development cases once under the approved version 0. At most four
   decision requests, with existing transport retries. Save each actual export;
   stop on technical failure or a mismatch with current approved conditions.
4. FIX the baseline result with reviewer and timestamp, generate one question
   from the held development cases, and submit the explicitly reviewed explanation
   below. Question selection is the existing general mechanism; the controller
   does not inject a predetermined question or force selection of a particular case.
5. Save the AI-generated rule proposal, inspect it deterministically against the
   four development cases and five development-derived exception checks, then stop
   BEFORE approving the proposal. Neither held-out case is run or used in these
   candidate checks, questions or teaching input.

No app code, schema, model, deployment, budget grant or historical run changes.
One baseline run, one question, one proposed supplement; at most eleven provider
attempts (eight decision attempts, two question attempts, one rule-generation
attempt), within the existing allowance. Reentry uses journalled request keys.
Terminal failure is retained; there is no automatic replacement run or retry loop.

## Explanation reviewed through the command

Company-addressed hotel folios may be accepted when the guest matches the claimant
and an explicitly stated employee payment is marked PAID. Compare the claim with
that employee amount, never the total or company prepayment. A known mismatch is
returned for correction. Missing payment allocation/status stays unknown and is
held. Both stay dates must match approval; a changed stay still requires the
manager. The only successful state is documentary readiness for business approval,
never final approval/payment. The exact English text is in the controller's
EXPLANATION constant and is saved locally on execution.

## Measurement interpretation

The existing app's fixed labels describe the complete clarified policy. Therefore
an appropriately held company folio in the baseline may not match its final-policy
target. The controller separately records **current-rule compliance** and actual
states; it does not equate a safe baseline hold with an unsafe execution. No new
percentage or improvement claim is made before the actual before/after outputs.

## Verification and remaining gate

`baseline128_offline.json` exercises real services, case evidence, confirmation,
private labels, run receipts, FIX and teaching, with explicit model/HTTP doubles.
It checks no holdout exposure, no teaching approval, bounded operations and
lost-response reentry after confirmation, run creation, stepping and teaching.
The generated supplement in this test is a declared test double, not LIVE output.
No real model or cloud writes during preparation.

Pending: owner execution, inspection and named approval of the new LIVE rule
proposal, same-case after run, frozen two-case unused evaluation, history/UI review
and updating the explanatory demo with real results. Video remains deferred.

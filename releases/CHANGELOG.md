# Standalone runbook changes

## 2026-10-15 — jt_intake_128.py

Category: environment/runbook progression using existing 1.0.28 APIs. No app
package change or deployment. Cause: the owner-reported revised workflow is ready
for a concrete human review and actual PDF intake; its payment-status description
still needs employee-specific scope before reading mixed-payer documents.

Changed files: `jt_intake_128.py`; corresponding owner evidence, check script,
offline report and `verification/INTAKE128_STATUS.md`. The command requires
explicit approval of the documented edit, preserves the raw LIVE draft, saves
HUMAN_EDIT provenance and named history, then reads six pinned PDFs without
confirming cases or running decisions. Local expected facts stay out of requests.
Lost-response replay and failed-result stop are verified. 33 bounded offline
checks passed; real Gemini extraction and deployed approval remain pending.

The installed root CHANGELOG, SPEC_LOCK, package manifest, all release installers,
model limits and original 216 historical decisions remain unchanged.

## 2026-10-15 — jt_resume_intake_128.py

Category: standalone verification defect fix. Actual third-document facts were
null as required, but the verifier rejected OBSERVED/null despite an explicit
Not stated quotation permitted by the app's observation contract. Accept this
representation only after validating the employee-specific absence quotation
against the actual pinned PDF. Preserve raw responses and the failed checkpoint;
resume the three unread files in separate records. No app change or reapproval.
Changed: recovery controller, focused test/report and INTAKE128_RESUME_STATUS.
Nineteen offline checks passed; actual continuation remains pending.

## 2026-10-15 — jt_baseline_128.py

Category: existing-runbook progression after all six actual PDF reads passed.
Explicitly confirm reviewed facts and submit the documented task-owner explanation;
use existing APIs to preserve six evidence-linked cases, attach private targets,
execute four baseline cases, FIX the result, ask one question and create one
unapproved supplement. No app change, deployment, new allowance or holdout run.
Changed: baseline controller, focused test/report and BASELINE128_STATUS.
Compare current-rule compliance separately from complete-policy target metrics;
keep safe baseline holds distinct from unsafe actions. Preserve terminal failures
and resume lost responses with the same operation keys. Actual execution pending.

## 2026-10-15 — jt_inspect_teaching_129.py

Category: read-only diagnostic for the owner-reported 1.0.29 teaching citation failure. The four baseline decisions and the source-grounded question succeeded. The teaching request returned INVALID_INPUT after generation. No assumption is made about which quotation failed.

The standalone command pins the installed package, failed checkpoint, request ID, human-source hash, question and current domain; reads the single saved model answer via Firestore GETs; replays the existing rule/evidence validators in memory; prints exact invalid references, the original explanation and proposed rules. Whitespace-only recoverability is diagnostic and never applied to saved rules. It saves local diagnostic copies only. No model, deployment, approval, application POST or cloud write. Four bounded diagnostic checks passed with synthetic sources. Actual saved-answer diagnosis remains pending the owner command. The installed package, previous controllers and all evidence remain unchanged.

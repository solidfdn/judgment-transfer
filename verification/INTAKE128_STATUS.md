# 1.0.28 — reviewed baseline and real PDF intake preparation

## Owner-provided result

`LIVE128_GATE.json` preserves the supplied Cloud Shell report, not an independent
cloud read. Version 1.0.28 was deployed; one revised LIVE draft was saved as
`draft_583b01423999b7f9efc79bbc33d9aa00`, trace
`trace_1583bb08df16426aa5cebc5551f78ce5`. No approval or case execution occurred.
Calls 515 → 516; recorded cumulative USD 17.0815845 → 17.1859638. The daily
judgment counter rolled over to zero on October 15 UTC; cumulative usage was
not reset. Empty input-review findings do not establish semantic completeness.

## Review and explicit clarification

The generated conditions use raw names, dates, addressee and amounts. Personal
receipts can pass the documentary precheck; company-addressed folios remain
unresolved. Changed stay dates have higher priority than amount mismatches.
Actual generated rules were replayed locally against the six author-transcribed
cases, yielding one ready / five held, with seven additional boundary examples.
These are deterministic offline checks, not new model decisions or live results.

The payment-status description was still broad enough to mean total settlement.
The reviewed edit changes only that field's label/description to require the
employee's own payment status, preserving unknown when not stated. Two existing
rules receive an additional exact source line 7 reference for personal-receipt
acceptance. No executable condition, priority, action or default changes.
The original LIVE draft remains preserved; the edited version is truthfully
stored with `HUMAN_EDIT` origin. Its named approval memo links the original draft
and describes the exact change. This is not represented as an untouched AI answer.

## Standalone controller

`releases/jt_intake_128.py` requires explicit
`--approve-reviewed-workflow --reviewer NAME`. It pins the exact installed code,
workspace, source hash, saved v128 result and actual original preview hash before
editing. It uses existing draft-edit, approval and case-read APIs; it changes no
app file, manifest, deployment setting, model, dependency, budget or historical run.

It obtains the six existing fictional PDFs from the installed input ZIP, checks
all six hashes, creates the reviewed edit, records named approval with timestamp,
then reads each PDF once through the real case-intake route. Existing internal
transport retry policy remains at most two attempts per read, six requests /
twelve attempts maximum, within the prior cumulative allowance. No new grant is
created. It checks zero new judgments and preserves the archived study snapshot.

Each response is saved before validation. The private local verifier compares
read values to author-prepared document transcriptions and requires employee
payment evidence rather than a total-PAID quotation. These expected facts are
never sent to the model; only the case PDF and ordinary case metadata are uploaded.
No expected outcome, reference rule or holdout answer is supplied to the model.
The two unused cases retain their holdout split and stay out of shared sources.
There is no automatic fact repair or case confirmation. Every initial state stays
unconfirmed/null. A failure stops subsequent documents; re-entry reuses the same
persistent request keys, and terminal failures do not automatically generate again.

## Verification and pending acceptance

`intake128_offline.json`: 33 bounded checks. Real core/service logic, exact saved
rule content, six real PDFs and strict source references; model and HTTP calls
are explicit doubles. Named history, original preservation, field/source
separation, wrong-version/draft rejection, misleading total-payment evidence,
and lost responses after edit, approval and read were exercised. Zero real model
calls or cloud writes during preparation. Syntax compilation passed.

Pending: owner execution of the concrete approval/intake command; review and
confirmation of extracted facts; four development cases before and after an
approved task-owner explanation; two unused cases; named FIX/history comparison;
final browser walkthrough and demo presentation update using actual results.
No new completion or award-readiness claim. Video remains deferred.

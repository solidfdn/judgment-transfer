# Release 1.0.37 — run creation uses the audited compatibility guard

Category: integration defect fix and continuation from the saved approved state.

The 1.0.36 continuation successfully generated guidance, passed the dev/exception
checks and approved it. Creating the after run then failed in
run_capacity.select_cases with RUN_PROTOCOL_CHANGED. Release 1.0.36 updated the
comparison/publication guard but missed this separate run-start guard.

The run-start gate now reuses comparison.preparation_transport_pair. Only the
exact reviewed 1.0.35 baseline to the current verified 1.0.37 package is admitted;
the known 1.0.35-to-1.0.36 pair remains readable. Model settings/mode, ownership,
workspace, case order, earlier rule version, completeness and current evidence
checks still apply. Unrelated and unaudited future packages remain blocked.
Saved unfinished runs still cannot execute under a different implementation.

Capacity planning now counts two question and two guidance generation attempts,
matching the 1.0.36 transport policy. It changes no allowance or budget.
Provider invocation, decision prompt/settings, schemas, source validation,
approval/receipt machinery, executor and scoring are byte-identical to 1.0.36.

Recovery copies only the inspected failed create-after checkpoint into 1.0.37.
It verifies the unchanged saved baseline, approved teaching and current domain,
reuses all successful cached steps, and starts the after run with a new request
key. No baseline, question or guidance regeneration; no new approval. Both the
earlier 504 and run-start failure checkpoints remain unchanged.

Focused tests execute the actual Service.create_run through run_inputs,
select_cases and plan, including rejected model/package/mode/workspace/source/
case combinations. They also execute actual recovery and cached-call logic.
Schema/history/storage/provider boundaries use explicit doubles; this is not
a new live backend test. See verification/run_start137_offline.json.

Affected: app/run_capacity.py; app/comparison.py; app/config.py VERSION;
app/expense_demo.py display version; steps/usd_recovery137.py;
steps/usd_demo137.py; steps/verify_display137.py; metadata and verification.

Cloud gate pending: deploy with zero generation, verify preserved records,
then execute four after cases and two first-use cases and publish only matching
records. Original total USD allowance remains 24 attempts including earlier
failures, cumulative model budget USD100, per-attempt deadline 60 seconds.
No baseline replay or formal benchmark replay.

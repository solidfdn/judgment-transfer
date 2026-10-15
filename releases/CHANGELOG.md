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

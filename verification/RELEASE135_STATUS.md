# Release 1.0.35 — approved stops before model dispatch

Category: defect fix within the approved execution and evidence design.

The extended-stay USD case waited for Gemini despite an explicit approved rule
already requiring a manager's decision. Both 60-second attempts returned no
chunks. The saved trace establishes a silent transport timeout, not its upstream
cause. Increasing the deadline would not resolve the avoidable dependency.

For C_JT_RULES only, a known match to an explicit, human-approved default/HOLD
rule now executes before model dispatch. The existing three-valued evaluator,
source validator, executor, lease, version checks, receipt and scoring are reused.
Unknown/unmatched/conflicting rules, positive actions and A/B evaluation arms
retain their model path. A later provider failure remains technical FAILED.
There is no timeout-to-business-HOLD fallback and no expense-specific core branch.

Direct stops record APPROVED_RULE / RULE_ENGINE, zero model attempts, the matched
rules, source versions and input state. The publication gate independently
recomputes each direct stop. Operational and demonstration details expose origin.

Affected files: app/approved_stop.py; app/service.py; app/expense_demo.py;
app/config.py; app/web/app.js; app/web/demo/{index.html,demo.js};
steps/{approved_stop135,usd_demo135,verify_display135}.py; release metadata.

Offline: verification/check_approved_stop135.py exercises actual changed control
flow with explicit local schema, repository, source-validation and provider
doubles. See approved_stop135_offline.json. This is not a new provider/Firestore
benchmark. Unchanged schema/transport and earlier acceptance checks are reused.

Cloud gate, not yet executed here: first confirm the same extended-stay case
completes with zero model calls and unchanged usage. Then create a separate
same-package four-before/four-after/two-first-use USD comparison and publish only
matching completed records. Keep original three successes, failed fourth trace,
any stopped retry, all source/approval/history records and usage counters.
The installer snapshots them before and after deployment, without generation.

The original 24-generation USD ceiling includes earlier failed/retry attempts;
the cumulative USD100 limit, two 60-second attempts, model, dependencies and
request tier remain unchanged. No new formal benchmark is run. Technical failure
stops this validation and is retained; no automatic fresh experiment is started.

This removes a model dependency where a stop is already determined. It does not
establish that all remaining model requests are immune to provider timeouts.

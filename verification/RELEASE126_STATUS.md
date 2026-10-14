# 1.0.26 — streamed workflow proposal

## Observed failure

The source review passed on 1.0.25 (six perspectives, one specific question).
The subsequent actual workflow request failed before returning a model answer:

- Workspace: `ws_1fc7f906adcf832815c6347e20fde077`.
- Request: `req_cbe490d5eaea747c5d116dd2`.
- Trace: `trace_397fb9b3cb4548fab771d9a4d51cf778`.
- Provider: `499 CANCELLED`, “The operation was cancelled.”
- Generation stage: 32,530 ms; total: 33,072 ms; configured timeout: 35,000 ms.
- One generation attempt, zero judgments, no approval.
- Recorded calls: 512 → 513; cumulative ledger: USD 16.825037100000003 →
  16.968660900000003. The USD 0.1436238 entry is the retained reservation,
  without provider usage; it is not an invoice-confirmed charge.

The provider supplied no request ID or specific cancellation cause. The timing
is near, but below, our configured deadline; causation is unproven. This release
is a bounded transport correction, not a claim that Google's underlying cause
has been established or resolved.

## Change and bounds

Only workflow proposals adopt the existing per-request async stream path.
The workflow schema is sent once through the API and remains identical to the
strict validation schema. The maximum is one generation, with a 120-second
overall model window and 35-second first-text deadline. This uses the existing
180-second HTTP infrastructure; the workflow request lease is also 180 seconds.
The receiver must finish with STOP before parsing and validating the complete
answer. It records chunk/timing progress but never applies partial text.

The unchanged exact evidence validator, field types, comparisons and approval
requirements still apply. Model output is copied before application metadata
normalization, preserving its trace. Domain validation errors attach that trace.
Administrator errors include bounded timings, not prompts, raw responses or
credentials. Public errors remain unchanged. New draft failures can be examined
from their exact trace without another model call.

The source-review path and decision-path deadlines, retry counts and business
semantics are unchanged. No fixture workflow, expected answers, reserve-case
labels or reference correction rules enter the actual generation request.

Official background checked on 2026-10-15 JST:
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output
  describes streamGenerateContent and advises providing a response schema only
  through the API rather than duplicating it in the prompt.
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/api-errors
  identifies 499 as cancellation; it does not diagnose this individual event.

## Verification and execution

`stream126_offline.json`: 19 checks of the actual adapter, asynchronous receiver,
service and error response with explicit SDK doubles, covering complete and
partial responses, cancelled/stalled/no-text requests, STOP requirements, strict
shape/evidence rejection, cleanup, raw-answer retention and unchanged decision
first-text timing. No LIVE calls were made locally.

`prepare126_offline.json`: 39 existing controller/diagnostic tests reused against
the new controller. Previously passed checks for unaffected product functions
are retained; no 216-decision benchmark replay is performed.

The existing 22 extraction/schema/error-boundary checks also pass against the
shared adapter and administrator response changes. All those provider responses
are doubles; they do not establish new LIVE acceptance.

This incremental installer accepts the exact completed 1.0.25 package and ships
only changed files. Earlier installers remain unchanged. One command deploys
the revision, verifies preservation, then creates one real
workflow draft from the exact saved successful review. The controller is run in
the existing pinned Python environment. It records success/failure under
`.jt/upgrades/1.0.26/`, uses the same new request key on re-entry and never retries
a saved failure. Completed source reviews are not regenerated. Earlier files,
failed checkpoints, traces, grants and counters remain intact.

Expected next state is `DRAFT_READY_FOR_REVIEW`, not a business-correctness pass.
The complete actual conditions and source quotations are displayed for review.
Human approval, PDF reading, before/after execution, reserved-case testing and
the remaining rendered browser acceptance are still pending.

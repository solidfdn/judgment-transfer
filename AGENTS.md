# Judgment Transfer execution contract

Owner: SOLIFAN. This package implements the accepted Judgment Transfer v1.0 specification. The current user's explicit directions take priority. This file does not authorize sending messages, publishing code, creating cloud resources, increasing spend or changing requirements independently of the user's task.

## Keep the accepted deliverable fixed

- Product: **Judgment Transfer — by SOLIFAN**. Three English screens: Sources, Teach, Results.
- Deliverable: complete Python/Flask application plus a numbered Google Cloud Shell runbook in one ZIP. Do not replace it with a proposal, pseudocode, notebook, Sites project, Node rewrite or another cloud.
- Preserve the original specification and JSON contracts. Inspect `SPEC_LOCK.json`, `CHANGELOG.md` and the current step/state before edits. Do not overwrite the baseline.
- Shared business-agnostic core; material/field/action/rule declarations supply domain differences. Do not add invoice/support branches to core logic.
- Google Cloud Run, Firestore Native, private Cloud Storage, Google GenAI SDK, `gemini-3.5-flash`, global model location. No unrequested dependency or model upgrades.
- Approval before rule activation; immutable versions; compare-and-swap; evidence/source hashes; UNKNOWN→HOLD; no real customer-system side effects; no hidden MOCK substitution.
- Preserve A original source, B the same expert text, C approved structured rules. No holdout labels or v1 reference rules in LIVE solver/teaching prompts. Report failed calls and attempts honestly.

## Distinguish fixes from requirement changes

Routine implementation fixes already within the user's requested scope can proceed. Cloud Shell packaging, quoting and transport adjustments may change how an existing step is executed; they may not change what it produces. Keep the public CHANGELOG focused on product changes and operational effects. Do not publish cosmetic editing notes, development error or recovery narratives, or internal progress reports. A requirement change needs the user's authorization; do all unaffected work first.

Never edit a manifest merely to conceal a change. Issue a traceable new package version with updated hashes after the change is reviewed. Preserve original `.jt` state. Do not delete checkpoints to force success or silently adopt an unrelated project. No subagent delegation is requested by this file.

## Bound the work and verification

- Use the baseline acceptance mapping T01–T27 where it applies to the current change. Select checks from the affected behavior and the active execution protocol.
- Reuse passed checks for unchanged code. Repeat only checks affected by an actual change, a concrete remaining defect, or a required gate. Do not invent load tests, extra models, alternative benchmarks, repeated full rehearsals or cosmetic rewrites.
- Before adding verification, state the concrete risk it resolves, its bounded scope and the stop condition. Do not turn an unavailable browser or cloud account into an open-ended environment investigation.
- Stop on an IAM/organization-policy denial. Do not loosen organization policy, grant Owner, create service-account keys, change providers or increase quotas/budgets as a workaround.
- Preserve step numbers, error codes, state files and request IDs. Resume the failed step; do not start from zero. Report what is passed, failed and unexecuted separately.
- A generated source walkthrough is input evidence, not a recording of the finished application. A target is not a measured result; a model return is not a verified state change; a saved file is not a submitted entry.

## Report to the user

Lead with the outcome. Identify the exact step and reason when blocked. Ask only for information that actually blocks the next authorized action. Do not ask the user to repeat established requirements, paste long source code into Cloud Shell, or disclose credentials in chat.

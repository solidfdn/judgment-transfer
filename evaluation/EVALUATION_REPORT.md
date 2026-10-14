# Judgment Transfer — by SOLIFAN

## Measured evaluation

These are saved LIVE results, not targets. Failures and cancelled cases remain in the denominator.

| Arm | Correct autonomous completion | Critical errors | Failed/cancelled | Model cost |
|---|---:|---:|---:|---:|
| A_SOURCE_ONLY | 33.3% | 0 | 1 | $0.8274 |
| B_TEXT_ADDED | 66.7% | 0 | 0 | $1.3356 |
| C_JT_RULES | 66.7% | 0 | 3 | $1.1657 |

C − A: +33.3 percentage points. C − B: +0.0 percentage points.

Observed completion differences include unequal execution failures; these results do not establish a judgment-transfer benefit.

24 unique fictional holdout cases, repeated three times per arm. Repeats are not independent new cases. No confidence or generalization claim is made.

Preparation/extraction calls are reported separately in each export and are not double-counted in arm decision costs. Failed calls without usage retain their conservative reserved cost. Infrastructure charges are separate.

## Release gate

TARGET_MET

If QUALITY_GAP is shown, report that limitation. Do not tune the rules against these holdout results and reuse the same set as an unseen benchmark. A new experiment needs separately authored holdout cases and a new version.

## What the prototype does

A workflow is declared from evidence, an expert resolves a blocked development case, proposed rules require explicit human approval, and execution applies only declared effects to isolated case state. A receipt links the action to its approved rule and evidence version.

## Comparison design

A receives original source material. B receives exactly the same approved expert text in addition to the original material. C uses the approved structured rules and a deterministic execution guard. All arms use the same model settings, frozen cases, initial state and retry limits. Expected labels never enter solver or teaching prompts.

## Limits

Fictional test material; one developer; 24 unique holdout cases; no real customer-system actions; no award guarantee. The application does not fine-tune the model. Multimodal extraction and semantic rule quality still require human review.

## Recovery provenance

New synthetic sample records authored before this study. Policy, field vocabulary and rule structure were already exposed during development. Invoice transfer records necessarily share the same five Boolean facts. This is a fresh-record revalidation, not independent blind validation or proof of generalization to new business policies. Original exposed holdout records and results remain unchanged.

Existing human approvals were reused unchanged, not newly granted. Historical results remain in the original deliverables directory.

All arms requested Priority. Documented Standard downgrades are included and priced at the actual tier; this is not an exclusively Priority-served benchmark. See traffic-summary.json.

Three unaffected first-attempt development successes from 1.0.14 are reused with provenance; fifteen checks execute under 1.0.15. The first no-text attempt is cancelled after ten seconds, leaving time for one retry within the unchanged twenty-second model window. All 216 formal decisions use the same streamed response protocol and API-only response schema. The unchanged business instructions, cases, rules and JSON contract remain in effect for all arms. Prior failures and the paired Cloud Shell diagnostic are preserved separately. Transient retries, latency and reserved unknown-usage costs remain in the evidence. The paired diagnostic used different actual traffic tiers and does not establish a causal speedup or Cloud Run reliability.

## Continuation of the saved 1.0.15 comparison

finish115.1 acknowledged terminal RETRY_LIMIT failures without replaying or rescoring them. Each original stop and trace hash is preserved in continuation-provenance.json. The first 181 terminal records, receipts and traces are verified against the supplied result archive. Only the remaining 35 nominal decisions were eligible for dispatch. The six-retry reserve remained exhausted. No budget, call grant, approval, frozen input, application code or model settings were changed. The three-consecutive-technical-failure stop remains active. This is an explicitly recorded orchestration correction, not an independent new experiment.

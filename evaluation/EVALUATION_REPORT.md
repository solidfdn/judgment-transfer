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

## What the prototype does

A workflow is declared from evidence, an expert resolves a blocked development case, proposed rules require explicit human approval, and execution applies only declared effects to isolated case state. A receipt links the action to its approved rule and evidence version.

## Comparison design

A receives original source material. B receives exactly the same approved expert text in addition to the original material. C uses the approved structured rules and a deterministic execution guard. All arms use the same model settings, frozen cases, initial state and retry limits. Expected labels never enter solver or teaching prompts.

## Scope and limitations

The study used fictional test material and made no changes to real customer systems. Its 24 unique holdout cases do not establish performance across other jobs or organizations. The application does not fine-tune the model; multimodal extraction and semantic rule quality require human review.

The synthetic records were authored before the study, using policies, field vocabulary and rule structures already known during development. The invoice records share the same five Boolean facts. This is a fresh-record revalidation, with existing human approvals reused unchanged. It does not independently validate unseen policies or establish generalization to new business rules.

All 216 formal decisions used the same streamed response protocol and API response schema. All arms requested Priority service; documented Standard service is included and priced at the actual tier. The measured costs therefore describe the mixed service actually received.

## Evidence

The [saved evaluation viewer](https://judgment-transfer-unql76xapq-an.a.run.app/review/) provides the original arm results and case evidence. This study used application version **1.0.15** and a different protocol from the [current six-case expense example](../README.md#a-concrete-example-expense-document-checks).

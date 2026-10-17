# Architecture and implementation

The [README diagram](../README.md#architecture) shows the approved-workflow path in application **1.0.39**.

## Preparation and approval

Gemini reviews the supplied materials and proposes workflow conditions, questions and guidance. Source references are validated against the recorded evidence. The task owner approves the proposed version and confirms case facts before execution.

Workflow fields, actions and conditions are declarations interpreted by a shared core. The expense example uses this same core.

## Source input

| Material | Input supplied to Gemini |
|---|---|
| TXT and text PDF | Extracted text, with source metadata and evidence locators |
| PNG/JPEG and short MP4 | Private Cloud Storage URIs, with source metadata |

The dotted media arrow in the diagram represents URI input to Gemini. The application manages source-file and record writes.

## Execution and storage

The `C_JT_RULES` path uses `APPROVED_RULE_ENGINE_V1` to evaluate confirmed facts and the frozen starting state against the approved version. Required conditions that are unknown, or conflicting applicable actions, lead to a hold.

The application checks approval, source versions and case-state freshness before committing an action. Case state and its execution receipt are committed together in a Firestore transaction. Traces are saved separately. Firestore also stores workflow versions, approvals, runs and history; Cloud Storage retains source files.

## Comparison and recorded viewing

A comparison pairs the original and revised conditions with the same cases, facts, starting states and execution protocol. The application exposes saved results, evidence, history and exports for inspection.

The recorded demo reads a separately published snapshot through a read-only endpoint. Its case outcomes and handover checklist are described in the [current example](../README.md#a-concrete-example-expense-document-checks).

## Original evaluation paths

The original `A_SOURCE_ONLY` and `B_TEXT_ADDED` paths retain their model-based decision protocol. Their historical results are documented in the [original evaluation report](../evaluation/EVALUATION_REPORT.md).

The current diagram covers the approved-workflow path. Comparing the historical model baseline directly with the current rule engine would mix execution methods; the recorded expense comparison instead uses the same rule engine before and after the approved explanation.

## Implementation map

| Concern | Source |
|---|---|
| Browser interface and API | [app/web/](../app/web/) · [app/main.py](../app/main.py) |
| Preparation, approvals and execution coordination | [app/service.py](../app/service.py) |
| Approved-rule execution | [app/approved_execution.py](../app/approved_execution.py) |
| Conditions and shared data contracts | [app/core/models.py](../app/core/models.py) · [JSON schema](../app/contracts/jt_contracts.schema.json) |
| Model integration and evidence input | [app/adapters/model.py](../app/adapters/model.py) |
| Transactions and record storage | [app/storage/repository.py](../app/storage/repository.py) |
| Comparison | [app/comparison.py](../app/comparison.py) |
| Finalized decision history | [app/history.py](../app/history.py) |

[Return to the README](../README.md)

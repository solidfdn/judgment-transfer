# Judgment Transfer — by SOLIFAN

**Use the task owner’s materials and explanations. Check which parts of the work AI can handle.**

Judgment Transfer identifies missing information and decisions that need a person. Test the instructions, add the task owner’s explanation, and compare what changes. The findings also help improve the handover to the next task owner.

[Open the application](https://judgment-transfer-unql76xapq-an.a.run.app/) · [Explore the recorded example](https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html)

## From instructions to an evidence-backed result

1. **Organize the work.** Describe the job, upload its materials, and add an explanation or comment. AI reviews the purpose, required information, steps, decision conditions, exceptions and completion criteria, with references to the supplied evidence.
2. **Try the instructions.** Review and approve the proposed conditions. Add example cases, confirm their facts and starting states, and run them in an isolated workspace.
3. **Explain what is missing.** Read the targeted question, provide the task owner’s explanation, and approve the proposed guidance.
4. **Compare the change.** Try the same cases from the same starting states. See which can proceed, which need information, and which still require a person.

Finalized records retain the responsible person, timestamp, optional note, source versions and judgment. Open earlier records and compare them with later work. Deleting a record or resetting its history requires confirmation.

## A concrete example: expense document checks

The recorded example uses fictional **Cedarline Services** hotel claims. The original policy does not explain when a company-addressed receipt is acceptable. The task owner adds that explanation, including how to identify the employee’s own payment.

| Case | Original instructions | With approved explanation |
|---|---|---|
| Matching personal receipt | Ready for business approval | Ready for business approval |
| Company receipt with the employee’s payment identified | Held for clarification | Ready for business approval |
| Employee payment details missing | Held for evidence | Held for evidence |
| Stay dates changed | Held for a manager’s decision | Held for a manager’s decision |

Two additional cases, unused when preparing the explanation, check its application: a matching claim proceeds to business approval; a claim for 42,400 against an employee payment of 26,400 is returned for correction. The document check advances work to the person responsible for business approval.

The [three-step demo](https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html) presents these saved results, their supporting records and a downloadable handover checklist. Opening it makes no model calls. [Comparison record](verification/LIVE130_COMPARISON.json) · [Display and comparison verification](verification/comparison131_offline.json)

## Try your own work

Open the application and enter **Job and intended result**. Use **Upload file** for a document or **Explanation or comment** for the task owner’s knowledge, then select **Organize the work**. Select **Prepare a practice test** when you are ready to review the conditions and add cases.

Supported materials are TXT, text PDF, PNG/JPEG and short MP4. The input accepts up to five files and 20 MiB in total; individual limits appear beside the upload control. Cases can be read from a file or entered through fields generated for the approved workflow. Review extracted facts before confirming them. Missing facts remain unknown.

Use **Responsible person** when approving or finalizing work. **Decision history** opens saved evidence and judgments; **Saved tests** opens execution results. All test actions affect isolated case state.

## Why Google Cloud

| Component | Role in Judgment Transfer |
|---|---|
| Gemini through the Google GenAI SDK | Reads multimodal materials, identifies clarification questions, proposes workflow conditions and explains case decisions |
| Cloud Run | Hosts the Python/Flask application and its English browser interface |
| Firestore Native | Stores versioned workflows, approvals, runs and history; commits case state and execution receipts atomically |
| Private Cloud Storage | Retains source files and evidence tied to the recorded versions |

AI proposes and interprets. Application checks validate source references, require approval before guidance becomes active, and control which declared state changes can execute. Unknown or conflicting required conditions keep a case on hold. Workflow fields, actions and conditions are declarations shared by the same core across business domains.

## Run and inspect

See [Setup and operation](START_HERE.md) for local simulation and Google Cloud Shell deployment. The runtime is Python 3.12, Flask and vanilla JavaScript; dependencies are pinned in `requirements.lock`. The configured Google model is `gemini-3.5-flash` in `global`.

| Path | Contents |
|---|---|
| `app/web/` | Application, recorded demo and evidence viewer |
| `app/service.py`, `app/core/` | Workflow versions, approvals, conditions, execution and receipts |
| `app/adapters/`, `app/storage/` | Model integration, evidence validation and persistence |
| `steps/`, `releases/` | Numbered Cloud Shell runbook and versioned updates |
| `verification/`, `evaluation/` | Focused checks, recorded results and the original evaluation |

The [original evaluation report](evaluation/EVALUATION_REPORT.md) retains its separate protocol, measured outcomes and failed calls. [Change history](CHANGELOG.md) records subsequent fixes. These records can be inspected without rerunning the evaluation.

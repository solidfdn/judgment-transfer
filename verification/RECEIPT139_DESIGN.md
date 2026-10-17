# Recorded demo: receipt acceptance

The **v1.0.39 / PERSONAL_RECEIPT_139** example uses six fictional Cedarline Services accommodation claims in USD.

## Business setting

Cedarline Services' initial accommodation-reimbursement procedure accepts company-addressed receipts. The supplied instructions do not define when an employee-addressed receipt is acceptable.

The task owner explains that an employee-addressed receipt is acceptable when the addressee and guest match the claimant, the employee-paid amount and PAID status are explicit, and both stay dates match the approval. The already-recorded claim-versus-employee-payment checks then apply. A company prepayment is not reimbursed to the employee. Missing values stay unknown; changed stays still need a manager.

## Six-case design

| Case | Evidence | Original conditions | With approved explanation |
|---|---|---|---|
| Alex Morgan | Company addressee; claim and employee payment USD268; PAID; dates match | Precheck complete | Precheck complete |
| Sam Rivera | Own-name addressee; claim and employee payment USD348; PAID; dates match | Hold for acceptance conditions | Precheck complete |
| Jordan Chen | Own-name addressee; claim USD312; employee payment amount/status not stated | Hold | Hold |
| Taylor Brooks | Company addressee; claim/payment USD396; stay ends one day after approval | Hold for manager | Hold for manager |
| Casey Lee | Own-name addressee; claim/payment USD276; PAID; dates match | Excluded from teaching | Precheck complete |
| Jamie Patel | Own-name addressee; claim USD424; employee paid USD264; company paid USD160; PAID | Excluded from teaching | Return for correction |

Sam's claim has one payer and a USD348 total. Split payments are checked separately in Jamie's case. All six cases start from NEW. **Precheck complete** means that the documents are ready for a person's business approval.

## Materials and comparison method

- **Materials:** the `expense_review_usd139` fixtures contain six two-page PDFs. Case facts are author-reviewed transcriptions with references to the supplied documents.
- **Preparation:** the initial workflow was prepared from the supplied procedure. Gemini prepared the question and guidance proposal; the task owner approved the conditions. Expected labels and the two additional cases were excluded from the question and guidance inputs.
- **Execution:** `APPROVED_RULE_ENGINE_V1` applied the original and approved conditions in **4 before + 4 after + 2 additional case executions**. The before/after comparison uses the same code, engine, case facts and starting states. These ten executions make no model calls.
- **Evidence:** approvals and finalized results include the responsible person's name and timestamp. Saved runs retain source versions, decisions, execution receipts and traces.

The comparison shows how the approved explanation changes these documented cases. Its scope is six fictional claims, rather than a measurement of general AI accuracy or handover-time savings.

[Recorded evidence](RELEASE139_STATUS.md) · [Published comparison record](https://judgment-transfer-unql76xapq-an.a.run.app/api/v1/demo/expense)

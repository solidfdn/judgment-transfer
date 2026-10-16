# Receipt-acceptance revision 139

Category: user-authorized correction of the fictional demo scenario, not a change to JT's shared architecture or evaluation protocol.

## Business setting

Cedarline Services is fictional. Its initial accommodation-reimbursement procedure accepts company-addressed receipts. Acceptance conditions for employee-addressed receipts are deliberately absent from the supplied instructions. This is a gap in the supplied procedure, not a claim about tax law or general accounting practice.

The task owner explains that an employee-addressed receipt is acceptable when the addressee and guest match the claimant, the employee-paid amount and PAID status are explicit, and both stay dates match the approval. The already-recorded claim-versus-employee-payment checks then apply. A company prepayment is not reimbursed to the employee. Missing values stay unknown; changed stays still need a manager.

Authoritative user explanation:
> 会社宛ではない本人宛ての領収書でも、従業員本人が支払った金額と支払済みであることが明記され、氏名と承認済みの宿泊日程が一致していれば、社内規定として問題なく受け付けられます。担当者がこの条件を承認することで、既存の支払確認のルールを適用できるようになります。

## Six-case design

| Case | Evidence | Original conditions | With approved explanation |
|---|---|---|---|
| Alex Morgan | Company addressee; claim and employee payment USD268; PAID; dates match | Precheck complete | Precheck complete |
| Sam Rivera | Own-name addressee; claim and employee payment USD348; PAID; dates match | Hold for acceptance conditions | Precheck complete |
| Jordan Chen | Own-name addressee; claim USD312; employee payment amount/status not stated | Hold | Hold |
| Taylor Brooks | Company addressee; claim/payment USD396; stay ends one day after approval | Hold for manager | Hold for manager |
| Casey Lee | Own-name addressee; claim/payment USD276; PAID; dates match | Excluded from teaching | Precheck complete |
| Jamie Patel | Own-name addressee; claim USD424; employee paid USD264; company paid USD160; PAID | Excluded from teaching | Return for correction |

The main Sam example has one payer and a USD348 total. Split payments are checked separately in Jamie's case. All six start from NEW. No case can approve an expense, execute a payment or send a message.

## Environment and evidence

- New fixture/domain namespace `expense_review_usd139`; a separate workspace, source hash, initial approval and explanation approval. Original fixtures, workspaces, successes, failures and approvals remain unchanged.
- Six deterministic two-page PDFs, matching exact author-reviewed transcriptions, field references and private expected labels. The model does not receive private labels or held-out cases in its question/guidance inputs. PDF re-extraction is not claimed.
- Initial workflow is human-prepared from the supplied procedure. Gemini generates a fresh question and guidance proposal from the revised sources. No old model result is relabelled.
- Existing `APPROVED_RULE_ENGINE_V1` executes 4 baseline + 4 after + 2 held-out cases. Same package, engine, cases and starting states for the before/after comparison. No model calls during these ten case executions.
- The initial rules cannot be replaced by the guidance. A development-only gate checks all four cases, missing/unpaid evidence, changed dates, third-party addressee and known amount mismatch before approval. Held-out outcomes do not repair the proposal.
- Every approval and fixed result includes reviewer name and timestamp. Original runs and their source references are retained.
- Publish to a new immutable `expense_receipt139` record only after raw decisions, exact cases, traces, receipts, frozen targets and source hashes pass. The endpoint prefers that record when it exists; until then, the old verified story remains visible. UI copy follows the scenario marker, so new labels never decorate old results.

## Cost and release

Use only the remaining existing authorization and cumulative USD100 ceiling. Question and guidance each make one request with the existing maximum of two bounded internal attempts; at most four new model attempts in total. No timeout, model, dependency, allowance or budget change. A failure saves the checkpoint and stops; it does not trigger a new generation request automatically.

Bounded verification: source/PDF consistency, actual schema/evidence validators, existing engine/executor, Service approvals/run creation/steps/freeze, history, full new controller, comparison and publisher, prior/new UI copy and installer payload checks. Storage and generation test doubles are explicit. No 216-case benchmark replay. Cloud Run validation is performed by the owner-operated release command and is not represented as completed offline.

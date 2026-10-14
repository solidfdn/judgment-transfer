FICTIONAL EXPENSE REVIEW INPUT PACK

Purpose
Test a documentary precheck for business-trip accommodation reimbursement.
The only actions update an isolated case status. No expense is approved and
no payment or message is sent.

Contents
policy/source_sop.txt: initial procedure, including its recorded evidence gap.
case_inputs/dev/: four development cases, two pages each (claim and hotel).
case_inputs/holdout/: two cases to keep out of task-owner teaching.
owner_review/expert_teaching_draft.txt: proposed clarification; not approved.
evaluation/: private author-prepared labels, field evidence and test plan.
Never upload evaluation files as model sources or include them in prompts.

Review and comparison
Review the initial procedure and extracted fields before approving a workflow.
Run the initial conditions from NEW. Use development cases to ask the task
owner what is missing. Review the proposed explanation and derived conditions
before explicitly approving them. Compare the same cases from the same NEW
state, then check the two cases not used for the explanation.
The field evidence map is an author transcription of the supplied documents;
it is not evidence that a model has extracted those fields.

Boundaries
READY_FOR_BUSINESS_APPROVAL means documentary precheck complete, not approval
of an expense. HELD can mean missing evidence or a manager's business decision.
RETURNED_FOR_CORRECTION records a known mismatch without sending anything.
The private expected outcomes are planned labels, not observed AI results.
This six-case set does not establish general accuracy or whole-job automation.
All company policies, organizations, people and transactions are fictional.

Build: python3 tools/build_expense_demo_materials.py

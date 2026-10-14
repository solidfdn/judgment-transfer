# Judgment Transfer — by SOLIFAN

**Verify the task owner’s information. Test whether their judgment is reproducible and effective.**

Use the current task owner’s instructions and explanations to examine which parts of a job AI can handle. Review the conditions, test example cases, and see where a person must still decide. The same review can reveal gaps in instructions for the next person.

**Open the application:** https://judgment-transfer-unql76xapq-an.a.run.app
**Guided demo (1.0.19, after deployment):** https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html
**Read-only measured evidence:** https://judgment-transfer-unql76xapq-an.a.run.app/assets/review/index.html

The guided demo and evidence walkthrough are read-only and make no model calls. It displays the actual saved Google Cloud results, source text, prior human approval, case facts and before/after receipts. The operational application starts with a new-work entry point; a previous workspace opens only when the user chooses to continue it. It retains its separate materials / explanation / results workflow; starting a LIVE operation can make a model call within the existing limits. All sample data are fictional; actions affect only isolated case state.

## Measured result — 1.0.15 execution, 1.0.19 presentation

| Condition | Correct autonomous completion | Correct decision, including hold | Failed decisions | Critical errors |
|---|---:|---:|---:|---:|
| A: Original sources | 24/72 (33.3%) | 48/72 (66.7%) | 1 | 0 |
| B: Same task owner explanation as text | 48/72 (66.7%) | 72/72 (100%) | 0 | 0 |
| C: Approved structured rules | 48/72 (66.7%) | 69/72 (95.8%) | 3 | 0 |

24 synthetic cases × 3 conditions × 3 repeats = 216 nominal decisions. All four failed decisions remain in the denominator. C − A is +33.3 percentage points; C − B is zero. This result does **not** demonstrate C-over-B accuracy superiority. Policies were previously exposed; this is fresh-record revalidation, not independent blind validation or proof of production reliability.

Median latency among 212 completed decisions: 4.2 seconds. Recorded comparison model cost: USD 3.3286. All completed responses used Standard after a Priority request; failed unknown-usage calls retain conservative cost reservations. Infrastructure costs are separate. Approval and execution receipts, rather than an unproven accuracy claim, make the structured-rule behavior inspectable.

Past evaluation records are kept as evidence of what was actually tested, including incomplete calls. They are not automatically loaded into a new assessment and do not establish that a new job can be automated. The original sources, approvals and results retain their provenance. The completed study and original results are immutable. The exhausted authorized call grant is not reset by this release. Historical recovery commands remain for provenance and are not a request to repeat the experiment. For the completed deployment, `python3 ~/jt_release_119.py --deploy` installs only the reviewed UI release.

The prototype reads source evidence, proposes a declarative workflow, runs isolated cases, asks a targeted question about blocked development cases, and turns the task owner’s explanation into an **inactive rule proposal**. Human approval creates a new immutable workflow version. Replaying starts from independent copies of the same initial state. Declared state effects and receipts make the difference inspectable.

## Run

For the full Google Cloud Shell deployment, start with `START_HERE_ja.md`. Upload the ZIP once; run `bash jt 00` through `bash jt 08`. Progress and action receipts stay in `.jt/` under Cloud Shell's persistent HOME. The runbook never changes source code while running.

For a local offline demonstration:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
JT_MODE=MOCK .venv/bin/python app/main.py
```

Open `http://127.0.0.1:8080`. MOCK is a simulation and cannot substantiate performance claims. A LIVE deployment uses Application Default Credentials from its dedicated runtime service account, not service-account key files. Google account authorization, billing and organization permissions must be available.

## Architecture

| Layer | Responsibility |
|---|---|
| `app/web/` | Readable Sources / Teach / Results UI, typed case entry, approval controls, guided demo and recorded evidence |
| `app/main.py` | Same-origin Flask API; session ownership, CSRF, idempotency and error envelopes |
| `app/service.py` | Workflow versions, teaching, run leases, atomic state/receipt commits and exports |
| `app/core/models.py` | Business-agnostic contracts, three-valued conditions, declared state effects and deterministic scoring |
| `app/adapters/` | Actual Gemini multimodal/JSON calls; explicitly separate MOCK adapter; source validation |
| `app/storage/` | Local JSON repository for offline use; Firestore transactions and private Cloud Storage for LIVE |
| `app/fixtures/` | Two fictional domains, original source assets, development/holdout cases and private scorer labels |
| `steps/` | Fixed Cloud Shell setup, resumable deployment, formal benchmark and evidence export |

Python 3.12 / Flask / vanilla HTML, CSS and JavaScript / Cloud Run / Firestore Native / private Cloud Storage / Google GenAI SDK / Gemini 3.5 Flash, global. Exact Python dependencies are in `requirements.lock`. There are no customer-system connectors, payments, emails, access grants or fine-tuning operations.

## API

All routes use `/api/v1`. Mutations require `Idempotency-Key`, a valid session and `X-CSRF-Token`. The owner-only evaluation runner uses the Secret Manager administrator token instead. Every workspace-bound read and mutation verifies ownership.

| Route | Main input |
|---|---|
| `POST /workspaces` | goal; optional sample or sample_id |
| `POST /sources` | multipart workspace_id, file; optional source_id to replace a source |
| `POST /sources/extract` | workspace_id; one bounded model operation |
| `POST /domains/draft` | workspace_id, goal; or a human-edited domain object |
| `POST /domains/approve` | draft_id, base_version |
| `POST /domains/rollback` | workspace_id, target_version, base_version |
| `POST /cases/import` | workspace_id, cases; optional administrator-only expected labels |
| `POST /runs` | workspace_id, arm, split, repeats, optional case_ids and mode |
| `POST /runs/{id}/step` | one idempotent request per case step |
| `POST /runs/{id}/cancel` | stop new leases; an already leased step may finish once |
| `POST /questions` | run_id or dev_run_id; development cases only |
| `POST /teachings` | question_id, human_text, optional base_version |
| `POST /teachings/{id}/approve` | base_version |
| `POST /workspaces/freeze` | administrator workspace_id |
| `GET /session`, `/workspaces/{id}`, `/runs/{id}`, `/exports/{run_id}`, `/health` | owned saved state or public health metadata |

The source extraction endpoint splits reading and drafting into separate HTTP calls so each remains within the bounded model window. This is an additive transport binding, not a change to the accepted workflow. Strict DomainSpec/Case/Decision/Receipt contracts remain unchanged. Repository documents wrap those contracts with operational metadata.

## Execution semantics

Lower priority numbers run first. At a priority level, an unknown condition or conflicting allowed actions yields HOLD. Null does not become false or zero. A and B receive the same structural and sandbox checks; they are not blocked by C's business-rule guard. C must cite a matching approved rule before a non-hold operation can commit.

A task lease is 180 seconds; at most two tasks are leased per workspace. Decisions use a 20-second total model window with streamed generation and at most one transient retry when time remains. Rule drafting uses one generation attempt in a 120-second window; other model purposes allow up to two attempts, a 35-second call limit and a shared 50-second window. Token counting is included in those windows. Case state commit stops after 135 seconds; Cloud Run and Gunicorn allow 180 seconds. State, receipt and task completion are one storage transaction. Expired leases may be reclaimed once. Multi-step workflows have an explicit eight-step cap per case. No network/model operation runs inside a storage transaction.

Stop prevents new case steps; it does not abort or refund an already dispatched model request. An in-flight step may commit once. If it has not reached a terminal state when the run is cancelled, its saved receipt remains and the task becomes CANCELLED instead of waiting for a step that cannot start. Failed or unfinished runs are never labelled as successfully completed in the UI. These controls do not resolve provider latency or availability.

Public sessions expire after 60 minutes and allow 12 judgment calls / 24 total model calls. The completed, explicitly authorized recovery has used all 251 grant attempts and all 509 total owner-session model calls, including prior preparation. Its shared six-retry allowance is exhausted. These counters and the cumulative USD 20 model budget are preserved. Infrastructure is billed separately; budget alerts do not stop billing.

## Evaluation and honesty

- A: original source material. B: the same task owner explanation added as text. C: approved structured rules and the execution guard.
- 2 fictional domains × 12 unique holdout cases × 3 arms × 3 repeats = 216 nominal judgments. There are 24 unique holdout cases, not 72.
- Labels stay outside model prompts. Development feedback precedes a freeze of cases, labels, source versions, rules, model settings and code hash. Failures stay in the denominator.
- The target is C − A ≥25 percentage points, zero critical sample errors, and no more than three total task owner corrections. These are goals, not delivered results or an award guarantee.
- B can match or beat C. The report says so. Rule approval, traceability and execution control can be examined independently of completion rates.
- `domain_v1_reference.json` and `teaching_response_mock.json` are offline references. They are excluded from the LIVE Docker image. The public source includes them to reproduce offline tests; neither is read by the LIVE adapter.

## Verification

```bash
.venv/bin/python tests/acceptance.py --report .jt/offline-acceptance.json
```

The fixed suite has 23 offline checks mapped to the accepted P0 conditions. Actual Google provisioning, provider behavior, measured gains, zero critical LIVE errors and a fresh-browser deployed walkthrough require the runbook's LIVE gates. See the delivery verification report for what has actually run. Do not convert an unexecuted gate into a PASS.

## Reuse with another workflow

Choose **Use my own instructions**, add material and a goal, organize the instructions, and review/approve the proposed workflow. Add example cases using the generated fields before the first run. Blank fields remain unknown; starting state is supplied by the person entering the case. Technical JSON import remains available. Fields and actions are declared as data; core code does not select by business name. No external validation material is needed to start building. Custom materials and cases require review; the prototype does not claim universal autonomous correctness.

Do not commit `.jt/`, `.venv/`, tokens, personal source data or raw cloud logs. `bash jt 08` produces a public-source ZIP without those local files. Public hosting and repository publication are separate explicit actions.


## Completed study and release provenance

The final study is `watchdog115`, phase `COMPLETE`, cursor `216`. Its evaluation code hash is `b5ffd242d8256902e309bbe816e631da4c932e93c324a85a1a6edc36af6aa8d4`. The presentation release is 1.0.19 and does not reclassify old results as a new execution. Its only Python change is the displayed version; source, prompt, model adapter, budget checks and judgment logic are unchanged.

A recorded continuation preserved all 181 already-terminal task and trace records and all 180 already-committed receipts. It retained failed judgments and exhausted retry counters, and processed only the remaining 35 nominal decisions. See `evaluation/continuation-provenance.json`, `evaluation/EVALUATION_REPORT.md` and the six byte-exact exports in `app/web/review/`.

Historical recovery implementation and instructions in the changelog are provenance, not current operating instructions. Do not rerun recovery or reset its counters to reproduce a presentation. The completed evidence walkthrough is the no-cost review path. The 1.0.19 installer is a separate, reviewed direct update from either the exact 1.0.17 or 1.0.18 completed package. It does not require an intermediate deployment. Local preparation does not establish that a cloud deployment has completed.

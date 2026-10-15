# Release 1.0.36 — preparation transport and saved-step continuation

Category: transport defect fix and recovery of the inspected failed step.

The 1.0.35 USD baseline completed four cases, including the explicit approved
changed-stay stop with zero model calls. Question generation also succeeded.
Guidance generation failed with provider 504 DEADLINE_EXCEEDED after 117,760ms,
under a separate 120-second, single-attempt synchronous policy. No model answer
was saved. That failure is not caused by the separate 35-second question limit.

Question and guidance generation now use the existing per-attempt streaming
client and the decision policy: at most 60 seconds per attempt, one 1-second
backoff, at most one retry for transient transport/429/500/502/503/504 failures,
within the existing 125-second bounded window. Invalid output, bad references,
nontransient errors and budget refusals do not cause a transport retry. The
question/guidance business instructions, output schemas, exact-source binding
and human approval requirements are unchanged. No model or dependency upgrade.

The actual decision branch's request parameters, prompt fingerprint, model
settings and budget-reservation behavior are unchanged. Core evaluator,
executor, scoring, evidence validator, source hashes and approved-stop guard
are byte-identical to 1.0.35. Offline parameter comparisons exercise actual
old/new invoke bodies with explicit provider/schema/clock doubles.

Recovery admits only workspace ws_50ff4e8beabbf2fbbc101163b5a9fc3a,
baseline run_addccfdf5da82ce6cb9179c0f006939a and failed guidance trace
trace_ab46f91d01d04b8089c69649def15182. It copies the checkpoint into 1.0.36,
retains the original failed checkpoint and trace, reuses the four saved baseline
receipts and saved question, and sends only a new guidance request followed by
the remaining after/first-use executions. No original case/question regeneration.

Because the saved baseline stays on 1.0.35, comparison admits a narrowly audited,
directional pair: exact baseline code f4b530aabfbec8766e476e83e7a02e2ed3b13412c8d52fc6e435871a18cc5a1e
to the verified current 1.0.36 package only. Other equality, source, case,
workspace, model-setting and execution-completeness checks remain mandatory.
The publisher requires first-use and after runs to have the same 1.0.36 hash.
The exception rejects arbitrary packages, reversed pairs and future versions.
Both original hashes and the reason for the exception are displayed in evidence.

Original USD allowance stays 24 generation attempts including prior failures.
The reported calls 570 minus 11 USD attempts establishes its base at 559; the
installer's read-only usage sanity bound is corrected to 583 (=559+24), without
changing any server allowance or USD100 cumulative ceiling. Guidance preflight
reserves room for two attempts. All prior counters/approvals/results remain.

Affected: app/adapters/model.py; app/comparison.py; app/expense_demo.py;
app/config.py VERSION; steps/usd_recovery136.py; steps/usd_demo136.py;
steps/verify_display136.py; release metadata and focused verification.
No formal benchmark, earlier browser workflow or unrelated business scenario
is replayed. Live continuation is pending Cloud Shell execution; an offline
transport test does not establish general provider availability.

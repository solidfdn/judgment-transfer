# Release 1.0.39

## Published record checked on 17 October 2026

The [public comparison endpoint](https://judgment-transfer-unql76xapq-an.a.run.app/api/v1/demo/expense) now returns the recorded **PERSONAL_RECEIPT_139** scenario from release **1.0.39**.

- Recorded comparison timestamp: `2026-10-16T06:21:09.225441+00:00`. This is not a separately verified approval timestamp.
- Reviewer: **Shinji Okada**; approved guidance version **1**.
- Baseline run: `run_737373d46f5bf45d3dee76c9c5904997`.
- After-guidance run: `run_74a2471ced93203fd1679e58f52ea4a1`.
- Additional-case run: `run_8b5ab94c95fe2fbb1c6d93b99580cd06`.
- Protocol: `APPROVED_RULE_ENGINE_V1`; matching baseline/after code hashes, case facts and starting states.
- Recorded preparation: **2 model attempts**. The **4 + 4 + 2 case executions** make **0 model calls**.
- Alex remains complete; Sam changes from hold to complete; Jordan and Taylor remain held. Casey completes; Jamie is returned for correction ($424 claimed, $264 employee-paid, $160 excess).

These are observations of the existing published record, not a new model run, benchmark or cloud deployment. The [scenario design](RECEIPT139_DESIGN.md) specifies the employee-addressed receipt criteria. Case facts are author-reviewed PDF transcriptions; completion means documentary precheck complete before human business approval.

## Original release-preparation status

The notes below retain the verification scope and pending actions as recorded when the release was packaged.

The revised six-case USD receipt scenario is implemented. The shared rules engine, source validator, contracts, model adapter and dependency pins are unchanged. See RECEIPT139_DESIGN.md for the business conditions and case matrix.

Offline gate passed: actual source/schema/PDF validators, Service, local storage/blobs, immutable named history, same-code before/after executions, held-out freeze, comparison, publication and repeat-run idempotency. Explicit generation and HTTP test doubles are used; this is not live Gemini evidence. Old/new UI copy is verified independently. No benchmark replay or cloud/model call was made here.

Owner-run Cloud Shell gate: install/deploy while checking existing records/counters, then create the new workspace, generate the question/guidance (one request each, at most four internal attempts total), validate and approve conditions under the supplied reviewer name, execute 4+4+2 without model calls, fix records and publish the verified scenario. The existing USD100 ceiling and grant are not increased. An exhausted grant or invalid proposal stops with saved records. Earlier successes and failures remain available.

No new narration audio, video, slide screenshot or live result is claimed in this release. Those presentation assets must follow the newly verified scenario after its cloud gate passes.

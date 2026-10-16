# Release 1.0.39

The revised six-case USD receipt scenario is implemented. The shared rules engine, source validator, contracts, model adapter and dependency pins are unchanged. See RECEIPT139_DESIGN.md for the business conditions and case matrix.

Offline gate passed: actual source/schema/PDF validators, Service, local storage/blobs, immutable named history, same-code before/after executions, held-out freeze, comparison, publication and repeat-run idempotency. Explicit generation and HTTP test doubles are used; this is not live Gemini evidence. Old/new UI copy is verified independently. No benchmark replay or cloud/model call was made here.

Owner-run Cloud Shell gate: install/deploy while checking existing records/counters, then create the new workspace, generate the question/guidance (one request each, at most four internal attempts total), validate and approve conditions under the supplied reviewer name, execute 4+4+2 without model calls, fix records and publish the verified scenario. The existing USD100 ceiling and grant are not increased. An exhausted grant or invalid proposal stops with saved records. Earlier successes and failures remain available.

No new narration audio, video, slide screenshot or live result is claimed in this release. Those presentation assets must follow the newly verified scenario after its cloud gate passes.

# Repository distribution

| Item | Current edition |
|---|---|
| Application | **1.0.39** |
| Repository distribution | **1.0.39+docs.1** |
| Application code hash | `285bf2e577cecbcece2c9a178975d0fd908f4d9818d8109f1e149c861543b76b` |

This repository edition updates public documentation and its file-integrity record. The application code, execution protocol and recorded results retain their existing versions.

## New installations

Follow [Setup and operation](../START_HERE.md). The `package-manifest.json` file identifies this repository edition and records the SHA-256 of its application, runbook, documentation and evidence files. The numbered runbook checks these files before starting a step.

The manifest excludes itself and the historical, self-contained installers in `releases/`. Those installers retain their original payloads and checks.

## Existing installations

Use the update procedure prepared for the installed application and its saved checkpoint. The historical installers check the exact package they were built to update.

This documentation edition is for the published repository. It is not a Cloud Shell updater: keep an existing installation and its `.jt` state in their current directory, and use a separate checkout to inspect this edition.

## Traceability

The manifest records the preceding distribution version, its manifest hash and the source commit. `SPEC_LOCK.json` records the documentation revision while retaining the baseline specification and application version. The application code hash is calculated from the same `app/` file set used by the application packager.

When preparing another distribution revision, record the change in [CHANGELOG](../CHANGELOG.md), update the distribution metadata and file hashes together, and verify the runbook’s integrity check against the complete final file set.

[Change history](../CHANGELOG.md) · [README](../README.md)

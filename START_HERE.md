# Setup and operation

To try Judgment Transfer, [open the application](https://judgment-transfer-unql76xapq-an.a.run.app/). The [recorded example](https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html) shows the expense-document comparison and supporting records without making model calls.

## Use the application

1. Enter **Job and intended result**. Select **Upload file**, or write an **Explanation or comment** and select **Add explanation**.
2. Select **Organize the work** and review the clarification questions and evidence. Select **Prepare a practice test** to create proposed conditions.
3. Enter the **Responsible person**, review the conditions, and approve them. Read a case file or enter example cases manually; confirm each case’s facts and initial state.
4. Select **Try the original instructions**. In step 2, select **Find what needs explaining**, answer the question, and select **Draft the guidance**. Review and approve the proposed guidance.
5. Select **Try the same cases with the guidance**, then inspect the comparison and each case’s evidence. **Finalize this result** records the result with the responsible person, timestamp and optional note.

**Continue saved work** reopens work previously used in the same tab. **Saved tests** opens earlier runs. **Decision history** lets you inspect finalized records, compare versions, and delete a selected record or reset its history after confirmation.

## Run a local simulation

Requires Python 3.12. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
JT_MODE=MOCK .venv/bin/python app/main.py
```

Open `http://127.0.0.1:8080`. The **Simulation** label identifies the offline mode. Use the LIVE application for Gemini document reading and case execution.

Run the fixed offline acceptance suite with:

```bash
.venv/bin/python tests/acceptance.py --report .jt/offline-acceptance.json
```

## Deploy a new Google Cloud environment

Use [Google Cloud Shell](https://shell.cloud.google.com/) with an authorized Google account, an available billing account and permission to create the required resources. Clone the repository or unpack the complete release ZIP into Cloud Shell’s persistent HOME.

```bash
git clone https://github.com/solidfdn/judgment-transfer.git Judgment_Transfer_Runbook_v1.0
cd Judgment_Transfer_Runbook_v1.0
bash jt 00
```

Run each following step after the previous one reports `DONE`:

| Step | Command | Result |
|---|---|---|
| 00 | `bash jt 00` | Check package integrity, Cloud Shell and Python |
| 01 | `bash jt 01` | Select billing and save settings for a new dedicated project |
| 02 | `bash jt 02` | Provision Cloud Run dependencies, Firestore, private Storage, service accounts and secrets |
| 03 | `bash jt 03` | Install pinned dependencies and run offline acceptance checks |
| 04 | `bash jt 04` | Build and deploy the LIVE application with authenticated access |
| 05 | `bash jt 05` | Check the model connection and source reading |
| 06 | `bash jt 06` | Enable reviewer access and verify the application URL |

The runbook saves configuration and progress in `.jt/`. Completed steps are skipped. Model calls and infrastructure use incur charges; the saved deployment configuration controls the model ceiling. The runtime uses its service account through Application Default Credentials.

Steps 07 and 08 implement the original formal evaluation and its evidence export. They are separate from trying a new workflow in the application. Existing evaluation results are available in [evaluation/](evaluation/).

For an existing installation, use the versioned update script supplied for that installation. Its checks preserve the deployment configuration, saved evidence and usage counters.

## Resume and support

```bash
bash jt status
bash jt support
```

The support report includes the package version, step status and sanitized diagnostics. Resolve the reported cause before resuming the failed step. For example, `bash jt 04 --retry` resumes a stopped initial deployment. Use the update script’s own resume procedure for an interrupted version update.

`bash jt close` restores authenticated access without deleting the application’s data. Keep `.jt/`, credentials, personal materials and raw cloud logs out of source control.

# Ordinary browser acceptance - 1.0.33

The normal public UI completed the equipment-loan walkthrough on 2026-10-15. The source, approved workflow and three saved cases were reused. No source review or workflow was regenerated.

The same three cases and starting states produced ready / hold / hold before the explanation and ready / ready / hold after named approval. The seven-day case continues to require the desk manager. Both runs use code `6c8d6644a0b137d880e1cdf30f35f30eb999992c67e8b8ab5e1783a138213b2a` and identical model settings.

The first baseline request waited 60 seconds with zero chunks, then recovered on its one permitted retry. Six case requests used seven generation attempts and saved exactly six receipts. The unsuccessful attempt remains in the export.

The baseline and after result were finalized as SOLIFAN UI validation, with timestamps. The after record includes a note. Their finalized history was opened side by side. Reloading the page and choosing Continue saved work restored the completed comparison without AI requests.

`gate.json` and `stopped-baseline-132.json` retain the earlier stop unchanged. `baseline-133.json`, `after-133.json` and `comparison-133.json` contain the successful recovery evidence. The current acceptance summary is `../LIVE133_BROWSER_GATE.json`. No extra replay is needed for unchanged code.

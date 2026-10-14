"""Create submission material from saved LIVE exports only; never invent missing results."""
import json
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'deliverables'
ARMS=('A_SOURCE_ONLY','B_TEXT_ADDED','C_JT_RULES');DOMAINS=('invoice_routing','support_triage')
def main():
    exports={}
    for domain in DOMAINS:
        for arm in ARMS:
            path=OUT/'evidence'/(domain+'-'+arm+'.json')
            if not path.exists():raise SystemExit('Missing completed evidence export: '+path.name)
            value=json.loads(path.read_text())
            if value['run']['mode']!='LIVE' or not value['metrics']['complete']:raise SystemExit('Only complete LIVE exports can produce the measured report.')
            exports[(domain,arm)]=value
    # Different rule versions are intentional. Everything else must be comparable.
    for domain in DOMAINS:
        values=[exports[(domain,arm)] for arm in ARMS]
        for field in ('dataset_hash','model_settings','code_hash','case_ids','repeats'):
            if any(v['run'][field]!=values[0]['run'][field] for v in values):raise SystemExit('Unfair comparison: '+field+' differs.')
        if values[0]['run']['repeats']!=3 or len(values[0]['run']['case_ids'])!=12:raise SystemExit('The formal sample requires 12 holdout cases and 3 repeats per arm.')
    def combined(arm):
        values=[exports[(d,arm)]['metrics'] for d in DOMAINS];total=sum(v['total'] for v in values)
        return {'attempts':total,'unique_cases':sum(v['unique_cases'] for v in values),'correct_completion_rate':sum(v['correct_completion_rate']*v['total'] for v in values)/total,
                'critical_errors':sum(v['critical_errors'] for v in values),'failures':sum(v['counts']['FAILED']+v['counts']['CANCELLED'] for v in values),
                'holds':sum(v['holds'] for v in values),'cost_usd':sum(v['cost_usd'] for v in values),'latency_ms':sum(v['latency_ms'] for v in values)}
    summary={arm:combined(arm) for arm in ARMS};gain=(summary[ARMS[2]]['correct_completion_rate']-summary[ARMS[0]]['correct_completion_rate'])*100
    vs_b=(summary[ARMS[2]]['correct_completion_rate']-summary[ARMS[1]]['correct_completion_rate'])*100
    inputs=sum(exports[(d,ARMS[2])]['metrics']['human_inputs'] for d in DOMAINS)
    target_met=gain>=25 and summary[ARMS[2]]['critical_errors']==0 and inputs<=3
    measured={'status':'TARGET_MET' if target_met else 'QUALITY_GAP','results':summary,'c_minus_a_percentage_points':gain,'c_minus_b_percentage_points':vs_b,
              'expert_inputs_total':inputs,'interpretation':('Observed completion differences include unequal execution failures; these results do not establish a judgment-transfer benefit.' if any(v['failures'] for v in summary.values()) else 'C is stronger than B on this sample.' if vs_b>0 else 'No C-over-B completion advantage was measured; inspect approval, provenance and execution-control differences.'),
              'scope':'24 unique fictional holdout cases, repeated three times per arm. Repeats are not independent new cases. No confidence or generalization claim is made.'}
    (OUT/'measured-summary.json').write_text(json.dumps(measured,indent=2))
    lines=['# Judgment Transfer — by SOLIFAN','', '## Measured evaluation', '',
           'These are saved LIVE results, not targets. Failures and cancelled cases remain in the denominator.','',
           '| Arm | Correct autonomous completion | Critical errors | Failed/cancelled | Model cost |',
           '|---|---:|---:|---:|---:|']
    for arm in ARMS:
        m=summary[arm];lines.append(f"| {arm} | {m['correct_completion_rate']*100:.1f}% | {m['critical_errors']} | {m['failures']} | ${m['cost_usd']:.4f} |")
    lines+=['',f'C − A: {gain:+.1f} percentage points. C − B: {vs_b:+.1f} percentage points.', '',measured['interpretation'],'',measured['scope'],'',
            'Preparation/extraction calls are reported separately in each export and are not double-counted in arm decision costs. Failed calls without usage retain their conservative reserved cost. Infrastructure charges are separate.','',
            '## Release gate','',measured['status'],'','If QUALITY_GAP is shown, report that limitation. Do not tune the rules against these holdout results and reuse the same set as an unseen benchmark. A new experiment needs separately authored holdout cases and a new version.','',
            '## What the prototype does','',
            'A workflow is declared from evidence, an expert resolves a blocked development case, proposed rules require explicit human approval, and execution applies only declared effects to isolated case state. A receipt links the action to its approved rule and evidence version.','',
            '## Comparison design','',
            'A receives original source material. B receives exactly the same approved expert text in addition to the original material. C uses the approved structured rules and a deterministic execution guard. All arms use the same model settings, frozen cases, initial state and retry limits. Expected labels never enter solver or teaching prompts.','',
            '## Limits','',
            'Fictional test material; one developer; 24 unique holdout cases; no real customer-system actions; no award guarantee. The application does not fine-tune the model. Multimodal extraction and semantic rule quality still require human review.','']
    (OUT/'EVALUATION_REPORT.md').write_text('\n'.join(lines))
    demo='''# 170-second demo recording guide

Record the actual deployed LIVE application. Display LIVE, MOCK or RECORDED honestly.

| Time | Show | Say |
|---|---|---|
| 0–18 s | Sources and the workflow goal | An SOP can describe routine work while leaving the exception in an expert's head. |
| 18–43 s | Real source text and short original walkthrough; evidence locations | Judgment Transfer preserves where each observation came from and what remains uncertain. |
| 43–68 s | Three development cases; a held exception | The workflow reaches a decision boundary instead of inventing permission. |
| 68–98 s | Targeted question, expert answer, proposed conditions | One expert correction becomes a reviewable rule. It is still inactive until approved. |
| 98–123 s | Human approval and replay from the original state | The approved rule changes which isolated action may execute. The receipt shows the actual state change. |
| 123–151 s | Frozen A / B / C report; second business domain | State the measured values from EVALUATION_REPORT.md. If B ties C, say so. Show how the same engine handles the other domain. |
| 151–170 s | Result trace and final title | Transfer the judgment. Verify the change. Judgment Transfer, by SOLIFAN. |

Do not use the supplied source walkthrough as a recording of the finished application. Do not replace failed LIVE results with MOCK without relabelling the scene. Target 170 seconds; keep the final video below three minutes.
'''
    (OUT/'DEMO_RECORDING_GUIDE.md').write_text(demo)
    slides='''# Pitch content for the event's official template

Copy this content into the official template; preserve its required pages and fields.

1. **Judgment Transfer — by SOLIFAN.** Teach the missing judgment; verify the change.
2. **Problem.** Documented processes often stop short of the exception decisions experienced people make. Copying more text does not provide an explicit approval boundary or an execution receipt.
3. **Demonstration.** Source evidence → blocked development case → targeted expert answer → reviewed rule → replay with a state-change receipt.
4. **Google Cloud.** Cloud Run hosts the Python application; Gemini 3.5 Flash reads multimodal evidence and proposes decisions/rules; Firestore stores versions, leases and receipts; private Cloud Storage stores source assets.
5. **Evidence.** Insert the exact A/B/C values from EVALUATION_REPORT.md. State 24 unique fictional holdout cases, 3 repeats per arm, failures included. Report any tie or regression against B.
6. **Why it matters.** Expert corrections become explicit, reviewable and traceable across workflows. The prototype isolates execution effects and keeps human approval in the loop.
7. **Limits and next step.** Fictional materials, bounded prototype actions, external validation still pending. A new workflow uses the same declared schema and engine.

Add the public app URL, public repository URL, video URL, team information and any required event-specific fields. Export the completed official deck to PDF. Do not claim these draft notes are the completed required presentation.
'''
    (OUT/'PITCH_CONTENT.md').write_text(slides)
    checklist={'app_url':'MANUAL_CHECK','fresh_browser_demo':'MANUAL_CHECK','public_github_repository':'MANUAL_CHECK','video_under_3_minutes':'MANUAL_CHECK',
               'official_template_pdf':'MANUAL_CHECK','english_submission':'MANUAL_CHECK','team_and_eligibility':'MANUAL_CHECK','submission_receipt':'MANUAL_CHECK',
               'measured_quality':measured['status'],'submission_ready':False}
    (OUT/'SUBMISSION_CHECKLIST.json').write_text(json.dumps(checklist,indent=2))
    include=['app','requirements.lock','Dockerfile','.dockerignore','.gcloudignore','README.md','AGENTS.md','tests','steps','jt','START_HERE_ja.md','SPEC_LOCK.json','CHANGELOG.md','package-manifest.json']
    public_files={}
    with zipfile.ZipFile(OUT/'Judgment_Transfer_Public_Source_v1.0.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for item in include:
            base=ROOT/item
            for file in sorted(base.rglob('*')) if base.is_dir() else [base]:
                if file.is_file() and '__pycache__' not in file.parts and file.name!='package-manifest.json':
                    name=str(file.relative_to(ROOT));archive.write(file,name);public_files[name]=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest=json.loads((ROOT/'package-manifest.json').read_text());manifest['files']=public_files;manifest['distribution']='public-source';archive.writestr('package-manifest.json',json.dumps(manifest,indent=2))
    print(json.dumps({'evidence_files':len(exports),'quality_gate':measured['status'],'submission_ready':False}))

if __name__=='__main__':main()

"""Read-only verification of shipped expense results against saved live exports."""
import copy,hashlib,json
from pathlib import Path

def digest(value):
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()

def immutable(view):
    return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}

def verify(root,api,r,endpoint=False,evidence=None):
    root=Path(root);out=root/'deliverables/release132'
    if evidence is None:evidence=(root/'app/web/demo/evidence.js').read_text()
    demo=json.loads(evidence.split('=',1)[1].strip().removesuffix(';'))
    result=r.load(root/'.jt/upgrades/1.0.30/expense-comparison.json')
    if result.get('status')!='PASSED' or result.get('model_calls')!=6 or result.get('judgment_calls')!=6:
        raise r.Stop('LIVE_COMPARISON_REQUIRED','保存済み6件の実測合格が必要です。再実行はしません。')
    if (demo['baseline_run_id']!=result['report']['baseline_run_id'] or demo['after_run_id']!=result['after_run_id'] or
        demo['holdout_run_id']!=result['holdout_run_id'] or digest(demo['source'].encode())!=demo['source_hash'] or
        digest(demo['human_text'].encode())!=demo['human_hash']):raise r.Stop('DEMO_EVIDENCE_CHANGED','デモと保存済み実測の根拠が一致しません。')
    before=api.call('/recovery115');views={};intake=r.load(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json')
    readings={x['case_id']:x['case'] for x in intake['readings']}
    for kind,key,filename in [('baseline','baseline_run_id','baseline.json'),('after','after_run_id','after.json'),('holdout','holdout_run_id','holdout.json')]:
        view=api.call('/exports/'+demo[key]);saved=r.load(root/'deliverables/release130/comparison'/filename)
        if immutable(view)!=immutable(saved):raise r.Stop('SAVED_RESULT_CHANGED','保存済みの実行・根拠が変わっています: '+kind)
        views[kind]=view
    if len(demo['cases'])!=6 or {c['id'] for c in demo['cases']}!=set(readings):raise r.Stop('DEMO_CASE_SET_CHANGED','デモの6件が保存済み案件と一致しません。')
    for case in demo['cases']:
        view=views['after' if case['split']=='dev' else 'holdout'];task=next((t for t in view['tasks'] if t['case_id']==case['id']),{})
        reading=copy.deepcopy(readings[case['id']]);reading['initial_state']={'review_status':'NEW'}
        receipts=[x for x in view['receipts'] if x['case_id']==case['id']]
        if (case['facts']!=reading['facts'] or task.get('status')!='COMPLETED' or task.get('decision',{}).get('action_id')!=case['after'] or
            task['decision'].get('explanation')!=case['explanation'] or task.get('raw_decision',{}).get('action_id')!=case['after'] or
            task.get('trace_ids')!=[case['trace_id']] or len(receipts)!=1 or receipts[0]['case_hash']!=digest(reading)):
            raise r.Stop('DEMO_RESULT_CHANGED','デモの事実・説明・実行記録が一致しません: '+case['id'])
        if case['split']=='dev':
            original=next(t for t in views['baseline']['tasks'] if t['case_id']==case['id'])
            if original['decision']['action_id']!=case['before']:raise r.Stop('DEMO_RESULT_CHANGED','補足前の表示が一致しません。')
    if endpoint:
        comparison=api.call('/comparisons/'+demo['baseline_run_id']+'/'+demo['after_run_id'])
        if not comparison.get('comparable') or not comparison.get('code_review') or not all(comparison.get('checks',{}).values()):
            raise r.Stop('COMPARISON_DISPLAY_FAILED','読取専用の比較表示条件が合格していません。')
    after=api.call('/recovery115')
    if before!=after:raise r.Stop('USAGE_CHANGED','表示確認中に利用量が変わりました。')
    report={'status':'PASSED','phase':'after-deployment' if endpoint else 'before-deployment','read_only':True,'new_model_calls':0,'judgment_calls':0,
            'verified_cases':len(demo['cases']),'saved_results_preserved':True,'display_evidence_matches_live_records':True,'comparison_endpoint_verified':endpoint,
            'baseline_run_id':demo['baseline_run_id'],'after_run_id':demo['after_run_id'],'holdout_run_id':demo['holdout_run_id'],'ledger':after['budget']}
    r.save(out/('display-after.json' if endpoint else 'display-before.json'),report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True);return report

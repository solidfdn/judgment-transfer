#!/usr/bin/env python3
"""Read the stopped after run and its failed traces; no generation or replay."""
import json
import sys
from pathlib import Path

PROJECT='jt-261013-a79fce'
CODE_HASH='d45fc6052024e9852054fff188aec41b9558c1886d4950c1876bc6cc82f6d036'


def main():
    sys.dont_write_bytecode=True
    root=Path.cwd().resolve();sys.path.insert(0,str(root))
    from steps import runbook as r
    r.integrity()
    manifest=r.load(root/'package-manifest.json')
    if r.config().get('project_id')!=PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=('1.0.37',CODE_HASH):
        raise RuntimeError('Expected the installed 1.0.37 project/package.')
    p=r.load(root/'.jt/upgrades/1.0.37/usd-demo.json')
    rid=p.get('after_run_id')
    if p.get('status')!='FAILED' or not rid:
        raise RuntimeError('The saved stopped after run is required. No model request was sent.')
    api=r.API();before=api.call('/recovery115');view=api.call('/exports/'+rid)
    if view['run']['workspace_id']!=p['workspace_id'] or view['run']['code_hash']!=CODE_HASH:
        raise RuntimeError('The saved run identity differs.')
    ids={tid for t in view['tasks'] if t['status']=='FAILED' for tid in t.get('trace_ids',[])}
    failed=[t for t in view.get('traces',[]) if t['trace_id'] in ids]
    after=api.call('/recovery115');initial=p.get('initial_usd_calls')
    report={'read_only':True,'new_model_calls':0,'cloud_writes':0,
        'pending_step':p.get('pending'),'workspace_id':p['workspace_id'],'after_run_id':rid,
        'tasks':[{k:t.get(k) for k in ('case_id','status','decision_origin','error','trace_ids')}|
            {'action':t.get('decision',{}).get('action_id'),'state':t.get('state')} for t in view['tasks']],
        'saved_error':p.get('error'),
        'failed_traces':[{k:t.get(k) for k in ('trace_id','purpose','elapsed_ms','settings','runtime','attempts','error')}|
            {'saved_model_result_available':'result' in t,'raw_response_saved':bool(t.get('raw_response_text'))} for t in failed],
        'missing_failed_trace_ids':sorted(ids-{t['trace_id'] for t in failed}),
        'total_usd_attempts_including_previous':after['session']['calls']-initial if type(initial) is int else None,
        'usage_unchanged_during_read':before==after,'ledger':after['budget']}
    out=root/'deliverables/release137/usd'
    r.save(out/'stopped-after-export.json',view)
    r.save(out/'stop-diagnostic.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit('STOP USD_INSPECTION_FAILED / '+str(error))

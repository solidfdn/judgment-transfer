#!/usr/bin/env python3
"""Inspect the saved USD stop with GET requests only; no model or cloud writes."""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT='jt-261013-a79fce'
CODE_HASH='f4b530aabfbec8766e476e83e7a02e2ed3b13412c8d52fc6e435871a18cc5a1e'


def main():
    sys.dont_write_bytecode=True
    root=Path.cwd().resolve();sys.path.insert(0,str(root))
    from steps import runbook as r
    r.integrity()
    manifest=r.load(root/'package-manifest.json')
    if r.config().get('project_id')!=PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=('1.0.35',CODE_HASH):
        raise RuntimeError('Expected the installed 1.0.35 project/package.')
    p=r.load(root/'.jt/upgrades/1.0.35/usd-demo.json')
    if p.get('status')!='FAILED' or not p.get('baseline_run_id'):
        raise RuntimeError('The saved USD comparison stop is required. No request was generated.')
    error=p.get('error',{});trace_id=error.get('diagnostic',{}).get('trace_id')
    api=r.API();before=api.call('/recovery115');view=api.call('/exports/'+p['baseline_run_id'])
    trace={};trace_read_error=None
    if trace_id and re.fullmatch(r'trace_[a-f0-9]{32}',trace_id):
        proc=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True)
        if proc.returncode or not proc.stdout.strip():raise RuntimeError('Existing Cloud Shell authentication unavailable.')
        url='https://firestore.googleapis.com/v1/projects/'+PROJECT+'/databases/(default)/documents/jt_traces/'+trace_id
        req=urllib.request.Request(url,method='GET',headers={'Authorization':'Bearer '+proc.stdout.strip()})
        with urllib.request.urlopen(req,timeout=30) as response:doc=json.load(response)
        trace=json.loads(doc.get('fields',{}).get('payload',{}).get('stringValue','{}'))
        if trace.get('trace_id')!=trace_id:raise RuntimeError('The saved trace identity differs.')
    else:trace_read_error='No trace ID is present in the saved application error.'
    after=api.call('/recovery115')
    if before!=after:raise RuntimeError('Usage changed during the read-only check. No model request was sent by this script.')
    initial=p.get('initial_usd_calls')
    report={'read_only':True,'new_model_calls':0,'cloud_writes':0,
        'pending_step':p.get('pending'),'workspace_id':p.get('workspace_id'),'baseline_run_id':p['baseline_run_id'],
        'baseline_tasks':[{k:t.get(k) for k in ('case_id','status','decision_origin','error')}|{'action':t.get('decision',{}).get('action_id')} for t in view['tasks']],
        'question_saved':'question' in p.get('steps',{}),'teaching_saved':'teaching' in p.get('steps',{}),
        'saved_error':error,'failed_trace':{k:trace.get(k) for k in ('trace_id','purpose','elapsed_ms','settings','attempts','error')},
        'saved_model_result_available':'result' in trace,'trace_read_error':trace_read_error,
        'total_usd_attempts_including_previous':after['session']['calls']-initial if type(initial) is int else None,
        'ledger':after['budget']}
    out=root/'deliverables/release135/usd'
    r.save(out/'stop-diagnostic.json',report)
    if trace:r.save(out/'failed-generation-trace.json',trace)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit('STOP USD_INSPECTION_FAILED / '+str(error))

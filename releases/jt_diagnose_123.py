#!/usr/bin/env python3
"""Read-only diagnostics for the 1.0.23 source-review gate. No model calls."""
import datetime as dt
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXPECTED_PROJECT = 'jt-261013-a79fce'
SINCE = '2026-10-14T13:38:00+00:00'

def payload(document):
    return json.loads(document.get('fields', {}).get('payload', {}).get('stringValue', '{}'))

def trace_summary(document):
    trace = payload(document)
    created = document.get('createTime', document.get('updateTime', ''))
    if not created or dt.datetime.fromisoformat(created.replace('Z','+00:00')) < dt.datetime.fromisoformat(SINCE):
        return None
    if trace.get('purpose') != 'extract' or not trace.get('payload', {}).get('instruction', '').startswith('Review the supplied materials'):
        return None
    fields = ('attempt','stage','status','error_type','provider_code','error_code','elapsed_ms',
              'failed_stage_elapsed_ms','generation_timeout_ms','input_tokens','output_tokens',
              'thinking_tokens','cost_usd','reserved_usd','provider_error','validation_error')
    return {'trace_id':trace.get('trace_id'), 'created_at':created, 'error':trace.get('error'),
            'elapsed_ms':trace.get('elapsed_ms'), 'settings':trace.get('settings'),
            'attempts':[{k:a[k] for k in fields if k in a} for a in trace.get('attempts', [])]}

def main():
    config_path = Path.cwd()/'.jt/config.json'
    if not config_path.is_file():
        raise RuntimeError('Run this command inside Judgment_Transfer_Runbook_v1.0.')
    config = json.loads(config_path.read_text())
    project = config.get('project_id')
    if project != EXPECTED_PROJECT:
        raise RuntimeError('Project does not match the existing Judgment Transfer environment. No cloud request was sent.')
    process = subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True)
    if process.returncode or not process.stdout.strip():
        raise RuntimeError('The existing Cloud Shell login could not be used. No credentials were printed.')
    token = process.stdout.strip()
    base = 'https://firestore.googleapis.com/v1/projects/'+project+'/databases/(default)/documents/'
    def read(path):
        request = urllib.request.Request(base+path, headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,timeout=30) as response:
            return json.load(response)
    summaries=[]; page_token=None; scanned=0
    for page in range(20):
        query={'pageSize':'200','mask.fieldPaths':'payload'}
        if page_token: query['pageToken']=page_token
        result=read('jt_traces?'+urllib.parse.urlencode(query))
        for document in result.get('documents',[]):
            scanned+=1
            summary=trace_summary(document)
            if summary: summaries.append(summary)
        page_token=result.get('nextPageToken')
        if not page_token: break
    if page_token: raise RuntimeError('Read limit reached. No further pages were requested.')
    ledger=payload(read('jt_budget/global'))
    allowance=payload(read('jt_budget/validation123'))
    report={'diagnostic':'Judgment Transfer 1.0.23 source review', 'read_only':True,
            'new_model_calls':0,'cloud_writes':0,'trace_documents_scanned':scanned,
            'review_traces':sorted(summaries,key=lambda x:x['created_at'])[-5:],
            'model_ledger':{k:ledger.get(k) for k in ('spent_usd','calls','decisions','day')},
            'validation_allowance':{k:allowance.get(k) for k in ('authorized','authorized_at','base_calls','base_decisions','additional_calls','additional_decisions','retry_limit','retry_used','max_cost_usd')}}
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    try: main()
    except urllib.error.HTTPError as error:
        sys.exit('STOP CLOUD_READ_'+str(error.code)+' / Read-only diagnostics could not read the saved records. No access setting was changed.')
    except Exception as error:
        if isinstance(error,RuntimeError): sys.exit('STOP DIAGNOSTIC / '+str(error))
        sys.exit('STOP DIAGNOSTIC / '+type(error).__name__+'. No model request or cloud write was made.')

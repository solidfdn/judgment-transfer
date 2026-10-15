#!/usr/bin/env python3
"""Inspect the saved failed teaching answer. Cloud GET only; no model generation."""
import copy, hashlib, json, os, subprocess, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path
PROJECT='jt-261013-a79fce'
CODE_HASH='63800f5130d75799709f977a396baef4bd84790a37f4735102fe7c5eb465049d'
WORKSPACE='ws_1fc7f906adcf832815c6347e20fde077'
RUN='run_ed781abd29baa3dfb53fe0bc0abb7937'
QUESTION='question_92bd35172b4562b9ad52aa6d45d3f66d'
REQUEST='req_9d19e537361ab25719022c0d'
OPERATION='baseline129-teaching-draft'

def digest(value):
    if not isinstance(value,bytes): value=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(value).hexdigest()

def unpack(document):
    return json.loads(document.get('fields',{}).get('payload',{}).get('stringValue','{}'))

def analyze(domain,source,policy,trace,text,policy_bytes):
    from adapters.evidence import validate_ref
    from adapters.citations import resolve_reference
    from core.models import JTError, check, validate_domain
    class Blobs:
        def get(self,key):
            if key==source['blob_id']: return text.encode()
            if key==policy['blob_id']: return policy_bytes
            raise RuntimeError('Unexpected blob requested')
    blobs=Blobs();sources={source['source_id']:source,policy['source_id']:policy}
    def validate(ref):
        s=sources.get(ref.get('source_id'))
        if not s: raise JTError('INVALID_INPUT','Unknown evidence source.')
        validate_ref(ref,s,blobs)
    raw=copy.deepcopy(trace['result']);rules=raw.get('rules',[]);issues=[];shapes=[]
    for i,rule in enumerate(rules):
        try: check('Rule',rule)
        except JTError as e: shapes.append({'path':f'rules[{i}]','message':e.message})
        for j,ref in enumerate(rule.get('source_refs',[])):
            try:validate(ref)
            except JTError as e:
                item={'path':f'rules[{i}].source_refs[{j}]','reference':ref,'message':e.message}
                try:
                    resolved,provenance=resolve_reference(ref,sources.get(ref.get('source_id')),blobs)
                    item.update(whitespace_only_recoverable=True,exact_reference=resolved,method=(provenance or {}).get('method'))
                except (JTError,KeyError,TypeError):item['whitespace_only_recoverable']=False
                issues.append(item)
    merged=copy.deepcopy(domain);ids={r['rule_id'] for r in rules};merged['rules']=[r for r in merged['rules'] if r['rule_id'] not in ids]+rules
    merged['source_hashes'][source['source_id']]=source['version_hash']
    for rule in rules:rule['approved_by']=None
    try:validate_domain(merged,validate);validation={'status':'PASSED_IN_MEMORY','saved_to_cloud':False}
    except JTError as e:validation={'status':'REPRODUCED_FAILURE','code':e.code,'message':e.message}
    return {'revalidation':validation,'rule_schema_errors':shapes,'invalid_reference_count':len(issues),'invalid_references':issues,
            'human_source':{'source_id':source['source_id'],'version_hash':source['version_hash'],'expected_locator':'human:1','text':text},
            'proposed_rules':raw.get('rules',[])}

def main():
    sys.dont_write_bytecode=True;root=Path.cwd().resolve()
    config=json.loads((root/'.jt/config.json').read_text());manifest=json.loads((root/'package-manifest.json').read_text())
    if config.get('project_id')!=PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=('1.0.29',CODE_HASH):
        raise RuntimeError('Expected the installed Judgment Transfer 1.0.29 project/package')
    venv=root/'.venv'
    if Path(sys.prefix).resolve()!=venv.resolve():
        exe=venv/'bin/python'
        if not exe.is_file():raise RuntimeError('Existing .venv missing')
        os.execv(str(exe),[str(exe),str(Path(__file__).resolve())])
    sys.path[:0]=[str(root),str(root/'app')]
    from steps import runbook as r
    r.integrity()
    checkpoint=r.load(root/'.jt/upgrades/1.0.29/baseline-teaching.json')
    if (checkpoint.get('status')!='FAILED' or checkpoint.get('run_id')!=RUN or checkpoint.get('baseline_rule_compliance') is not True or
        len(checkpoint.get('baseline_results',[]))!=4 or checkpoint.get('question',{}).get('question_id')!=QUESTION or
        checkpoint.get('error',{}).get('request_id')!=REQUEST):raise RuntimeError('Saved checkpoint does not match the reported stop')
    out=root/'deliverables/release129/teaching-inspection'
    explanation=r.load(root/'deliverables/release129/baseline/reviewed-explanation.json');text=explanation['human_text']
    proc=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True)
    if proc.returncode or not proc.stdout.strip():raise RuntimeError('Existing Cloud Shell login unavailable')
    token=proc.stdout.strip();base='https://firestore.googleapis.com/v1/projects/'+PROJECT+'/databases/(default)/documents/'
    def read(path):
        request=urllib.request.Request(base+path,method='GET',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
    ws=unpack(read('jt_workspaces/'+WORKSPACE))
    if ws.get('workspace_id')!=WORKSPACE or ws.get('version')!=0 or ws.get('teaching_ids'):
        raise RuntimeError('Workspace or approval state changed')
    request_key=digest([ws['owner'],'/api/v1/teachings',OPERATION])
    record=unpack(read('jt_requests/'+request_key));error=(record.get('result') or {}).get('error',{})
    if error.get('request_id')!=REQUEST or error.get('code')!='INVALID_INPUT':raise RuntimeError('Saved request differs')
    sid='human_'+digest([ws['owner'],OPERATION,''])[:32]
    source=unpack(read('jt_sources/'+WORKSPACE+'-'+sid))
    if (source.get('version_hash')!=digest(text.encode()) or source.get('source_id')!=sid or not source.get('human')):
        raise RuntimeError('Saved explanation differs')
    domain=unpack(read('jt_domains/'+WORKSPACE+'-v0'))['domain']
    policy_id='expense_policy_124';policy=unpack(read('jt_sources/'+WORKSPACE+'-'+policy_id))
    policy_bytes=(root/'app/web/samples/expense_policy.txt').read_bytes()
    if policy.get('version_hash')!=digest(policy_bytes):raise RuntimeError('Local policy differs from saved evidence')
    matches=[];page_token=None;scanned=0
    for _ in range(20):
        query={'pageSize':'200','mask.fieldPaths':'payload'}
        if page_token:query['pageToken']=page_token
        page=read('jt_traces?'+urllib.parse.urlencode(query))
        for doc in page.get('documents',[]):
            scanned+=1;t=unpack(doc)
            if (t.get('purpose')=='draft_rules' and t.get('source_hashes')=={sid:source['version_hash']} and
                t.get('payload',{}).get('human_text')==text and t.get('payload',{}).get('question',{}).get('question_id')==QUESTION):matches.append(t)
        page_token=page.get('nextPageToken')
        if not page_token:break
    if page_token or len(matches)!=1 or not isinstance(matches[0].get('result'),dict):
        raise RuntimeError('Expected exactly one saved answer; matched '+str(len(matches)))
    trace=matches[0]
    if trace['payload'].get('domain')!=domain:raise RuntimeError('Saved proposal used a different domain')
    report={'diagnostic':'Judgment Transfer 1.0.29 saved teaching validation','read_only':True,'new_model_calls':0,'cloud_writes':0,
            'run_id':RUN,'trace_id':trace['trace_id'],'trace_documents_scanned':scanned,'saved_application_error':error,
            'model_attempt_statuses':[a.get('status') for a in trace.get('attempts',[])]}
    report.update(analyze(domain,source,policy,trace,text,policy_bytes))
    r.save(out/'saved-trace.json',trace);r.save(out/'diagnostic.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except urllib.error.HTTPError as e:sys.exit('STOP CLOUD_READ_'+str(e.code)+' / No access settings changed.')
    except Exception as e:sys.exit('STOP READ_ONLY_INSPECTION / '+(str(e) if isinstance(e,RuntimeError) else type(e).__name__)+'. No model call or cloud write.')

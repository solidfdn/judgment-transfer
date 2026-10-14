"""Installer baseline and interrupted LIVE-gate transport checks; no cloud calls."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import urllib.error
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from steps import verify_source124 as gate
spec=importlib.util.spec_from_file_location('release124',ROOT/'releases/jt_release_124.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def ok(n,v=True):
    assert v,n
    checks.append(n)
def reject(n,fn,code):
    try: fn()
    except Exception as e:
        assert getattr(e,'code',None)==code or str(e).startswith('STOP '+code),(n,str(e))
        checks.append(n)
    else: raise AssertionError(n)
def manifest(v):return {'version':v,'code_hash':m.sha(v.encode()),'files':{'app/entry.txt':m.sha(v.encode())}}
baselines={f'1.0.{v}':manifest(f'1.0.{v}') for v in range(17,24)};new=manifest('1.0.24')
m.DATA={'baselines':baselines,'new':new,'files':{'app/entry.txt':base64.b64encode(b'1.0.24').decode(),
    'package-manifest.json':base64.b64encode(json.dumps(new).encode()).decode()}}
ok('exact 117 through 123 payload baselines',len(m.payload())==2)
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);(root/'app').mkdir();p=root/'app/entry.txt';p.write_text('1.0.23');baseline=baselines['1.0.23']
    ok('123 baseline accepted',m.verify_package(root,baseline,None)==baseline)
    progress={'payload_hash':m.sha(m.DATA),'baseline_hash':m.sha(baseline),'from_version':'1.0.23','phase':'PREPARED'}
    p.write_text('1.0.24')
    reject('unrecorded mixed version rejected',lambda:m.verify_package(root,baseline,None),'PACKAGE_CHANGED')
    ok('recorded same-payload resume accepted',m.verify_package(root,baseline,progress)==baseline)
    reject('other baseline resume rejected',lambda:m.verify_package(root,baselines['1.0.22'],progress),'UPDATE_CONFLICT')
    progress['phase']='DEPLOYED';ok('completed 124 installation resumes',m.verify_package(root,new,progress)==baseline)

class API:
    def __init__(self,mode):
        self.mode=mode;self.generations=0;self.review=None;self.calls=[]
        self.status={'session':{'calls':509,'decisions':498},'budget':{'calls':510,'decisions':251,'spent_usd':16.69},
            'additional_decisions_used':251,'extra_retry_attempts':{'limit':6,'used':6},'study':{'phase':'COMPLETE','cursor':216}}
    def call(self,path,data=None,key=None,files=None):
        self.calls.append((path,key))
        if path=='/health':return {'package_version':'1.0.24','code_hash':'test124','mode':'LIVE','max_cost_usd':100}
        if path=='/workspaces':return {'workspace_id':'ws_test'}
        if path=='/sources':
            self.source_hash=hashlib.sha256(files[2]).hexdigest();return {'version_hash':self.source_hash}
        if path=='/workspaces/ws_test':return {'requirements_review':copy.deepcopy(self.review)}
        if path=='/recovery115':return copy.deepcopy(self.status)
        if path=='/requirements/review':
            self.generations+=1;assert self.generations==1,'duplicate generation'
            self.status['session']['calls']+=1;self.status['budget']['calls']+=1;self.status['budget']['spent_usd']+=.01
            if self.mode=='400':
                e=gate.r.Stop('APP_REQUEST_FAILED','Provider rejected request')
                e.detail={'code':'MODEL_FAILED','request_id':'req_400','diagnostic':{'trace_id':'trace_400','attempts':[{'provider_code':'400'}]}}
                raise e
            self.review={'checks':[{'aspect':a} for a in sorted(gate.ASPECTS)],'questions':[{'question':'Clarify company-addressed receipts'}],
                'observations':[{'status':'OBSERVED'}], 'source_hashes':{'expense_policy_124':self.source_hash},'goal':gate.GOAL,'trace_id':'trace_success'}
            if self.mode=='lost':raise gate.r.Stop('NETWORK_INTERRUPTED','Lost response')
            if self.mode=='incomplete':self.review['checks'].pop()
            return copy.deepcopy(self.review)
        raise AssertionError(path)

for mode in ('pass','400','lost','incomplete'):
    with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
        root=Path(folder);source=root/'app/web/samples/expense_policy.txt';source.parent.mkdir(parents=True);source.write_text('Fictional policy\n')
        api=API(mode)
        run=lambda:gate.run(api,root,'test124','Offline verification')
        if mode=='pass':
            report=run();ok('single review gate passes and records actual call delta',report['status']=='PASSED' and report['model_calls']==1 and report['judgment_calls']==0)
            run();ok('completed gate rerun makes no new generation',api.generations==1)
        elif mode=='400':
            reject('400 fails the gate',run,'SOURCE_GATE_FAILED')
            report=gate.r.load(root/'.jt/upgrades/1.0.24/source-review-gate.json')
            ok('400 diagnostic saved without another read script',report['diagnostic']['trace_id']=='trace_400')
            reject('failed gate rerun stops with saved failure',run,'SOURCE_GATE_FAILED')
            ok('failed gate does not silently retry',api.generations==1)
        elif mode=='lost':
            reject('lost response remains pending',run,'SOURCE_GATE_PENDING')
            report=run();ok('lost response resumes from saved review without regeneration',api.generations==1 and report['status']=='PASSED')
        else:
            reject('incomplete successful HTTP response cannot pass gate',run,'SOURCE_GATE_FAILED')
            ok('incomplete response records failed state',gate.r.load(root/'.jt/upgrades/1.0.24/source-review-gate.json')['status']=='FAILED')
        ok(mode+' has no approval, judgment or reset API call',all(path in ('/health','/workspaces','/sources','/requirements/review','/workspaces/ws_test','/recovery115') for path,_ in api.calls))
before=API('pass').status;after=copy.deepcopy(before);after['session']['decisions']+=1
reject('unexpected judgment usage rejected',lambda:gate.check_usage(before,after),'VALIDATION_USAGE_CHANGED')
after=copy.deepcopy(before);after['session']['calls']+=3;after['budget']['calls']+=3
reject('more than two generation attempts rejected',lambda:gate.check_usage(before,after),'VALIDATION_USAGE_CHANGED')

# The actual stdlib API client retains diagnostics on first and cached errors.
client=gate.r.API.__new__(gate.r.API);client.url='https://offline.invalid';client.headers={}
detail={'code':'MODEL_FAILED','message':'Stopped','diagnostic':{'trace_id':'trace_test'}}
for cached in (False, True):
    response=io.BytesIO(json.dumps({'error':detail}).encode())
    error=urllib.error.HTTPError('https://offline.invalid',503,'Stopped',{},response)
    with patch.object(gate.r.urllib.request,'urlopen',return_value=response,side_effect=None if cached else error):
        try: client.call('/requirements/review',{'workspace_id':'ws_test'},key='source-review124-check')
        except gate.r.Stop as e:ok(('cached' if cached else 'HTTP failure')+' API error preserves bounded diagnostic',e.detail==detail)
        else:raise AssertionError('API error accepted')

report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'limitation':'Explicit HTTP double; real deployed source gate remains required.'}
(ROOT/'verification/release_gate_124.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

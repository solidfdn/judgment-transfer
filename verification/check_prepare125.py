"""Bounded controller checks with an explicit API double; no LIVE claims."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'app')]
from steps import runbook as r
spec = importlib.util.spec_from_file_location('prepare125', ROOT/'releases/jt_prepare_125.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def ok(name, value=True):
    assert value, name
    checks.append(name)
def rejects(name, fn, code):
    try: fn()
    except r.Stop as error: assert error.code == code, (name, error.code)
    else: raise AssertionError(name)
    checks.append(name)

class API:
    def __init__(self, root, mode='pass'):
        self.mode=mode; self.posts=[]; self.calls=[]; self.requests={}; self.generations=0; self.lost=False
        self.policy=(ROOT/'app/web/samples/expense_policy.txt').read_bytes()
        p=root/'app/web/samples/expense_policy.txt';p.parent.mkdir(parents=True);p.write_bytes(self.policy)
        self.source_hash=m.digest(self.policy)
        r.save(root/'.jt/upgrades/1.0.25/source-review-gate.json', {'status':'PASSED',
            'code_hash':m.CODE_HASH, 'workspace_id':m.WORKSPACE, 'trace_id':m.SOURCE_TRACE})
        self.ws={'workspace_id':m.WORKSPACE,'source_ids':[m.SOURCE], 'sources':[
            {'source_id':m.SOURCE,'version_hash':self.source_hash}], 'version':-1, 'domain':None,
            'run_ids':[], 'case_ids':[], 'teaching_ids':[], 'human_source_ids':[], 'question_ids':[],
            'approved_count':0, 'frozen':False,'goal':'Check supplied expense evidence.',
            'status':'EMPTY', 'shared_trace_ids':[m.SOURCE_TRACE],
            'requirements_review':{'trace_id':m.SOURCE_TRACE,'source_hashes':{m.SOURCE:self.source_hash},
                'goal':'Check supplied expense evidence.','questions':[{'question':'When is a company-addressed folio accepted?'}]}}
        self.ledger={'session':{'calls':512,'decisions':498},
            'budget':{'calls':512,'decisions':251,'spent_usd':16.8250371,'day':'2026-10-14'},
            'study':{'phase':'COMPLETE','cursor':216},'additional_decisions_used':251,
            'extra_retry_attempts':{'limit':6,'used':6}}
    def call(self,path,data=None,key=None,files=None):
        self.calls.append(path)
        if path=='/health':return {'package_version':'1.0.25','code_hash':m.CODE_HASH,'mode':'LIVE','max_cost_usd':100}
        if path=='/workspaces/'+m.WORKSPACE:return copy.deepcopy(self.ws)
        if path=='/recovery115':return copy.deepcopy(self.ledger)
        if path!='/domains/draft':raise AssertionError(path)
        assert data == {'workspace_id':m.WORKSPACE,'goal':self.ws['goal']}, 'Fixture/reference leaked into model input'
        assert key==m.REQUEST_KEY
        self.posts.append(key)
        if key not in self.requests:
            self.generations+=1
            self.ledger['session']['calls']+=1;self.ledger['budget']['calls']+=1
            self.ledger['budget']['spent_usd']+=.05
            if self.mode=='failure':
                self.requests[key]={'error':{'code':'MODEL_FAILED','message':'Provider rejected request.',
                    'request_id':'req_test','diagnostic':{'trace_id':'trace_test','attempts':[{'status':'FAILED','provider_code':'400'}]}}}
            else:
                domain=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text())
                domain['source_hashes']={m.SOURCE:self.source_hash}
                for rule in domain['rules']:
                    for ref in rule['source_refs']:ref['source_id']=m.SOURCE
                self.requests[key]={'draft_id':'draft_test','workspace_id':m.WORKSPACE,'base_version':-1,
                    'origin':'LIVE','domain':domain,'trace_ids':['trace_test']}
                self.ws['draft']=copy.deepcopy(self.requests[key]);self.ws['draft_id']='draft_test'
                self.ws['shared_trace_ids'].append('trace_test')
                if self.mode=='extra_usage':self.ledger['budget']['calls']+=1
                if self.mode=='changed_study':self.ledger['study']['cursor']=217
                if self.mode=='approved':self.ws['version']=0
                if self.mode=='wrong_origin':
                    self.requests[key]['origin']='HUMAN_EDIT';self.ws['draft']['origin']='HUMAN_EDIT'
                if self.mode=='wrong_trace':self.ws['shared_trace_ids'].append('unrelated_trace')
            if self.mode=='lost' and not self.lost:
                self.lost=True;raise r.Stop('NETWORK_INTERRUPTED','Lost response')
        value=self.requests[key]
        if 'error' in value:
            error=r.Stop('APP_REQUEST_FAILED','Saved failure');error.detail=value['error'];raise error
        return copy.deepcopy(value)

for mode in ('pass','failure','lost','extra_usage','changed_study','approved','wrong_origin','wrong_trace'):
    with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
        root=Path(folder);api=API(root,mode);call=lambda:m.run(api,root,r)
        if mode=='pass':
            report=call();ok('actual returned unapproved draft is recorded', report['status']=='DRAFT_READY_FOR_REVIEW' and report['model_calls']==1 and not report['approval_created'])
            old=len(api.calls);call();ok('completed re-entry performs no application request',len(api.calls)==old)
            ok('full condition expressions and quotes remain reviewable',report['workflow_preview']['rules']==api.ws['draft']['domain']['rules'])
        elif mode=='lost':
            rejects('lost response stays pending',call,'WORKFLOW_PREPARE_PENDING')
            report=call();ok('same-key reconciliation uses original one generation',api.generations==1 and api.posts==[m.REQUEST_KEY,m.REQUEST_KEY] and report['model_calls']==1)
        else:
            rejects(mode+' stops instead of passing',call,'WORKFLOW_PREPARE_FAILED')
            state=r.load(root/'.jt/upgrades/1.0.25/workflow-prepare.json')
            ok(mode+' retains failed checkpoint',state['status']=='FAILED')
            if mode=='failure':
                ok('provider diagnostic retained',state['diagnostic']['trace_id']=='trace_test' and state['error_message']=='Provider rejected request.')
                rejects('failed re-entry does not regenerate',call,'WORKFLOW_PREPARE_FAILED')
                ok('failed request attempted once',api.generations==1)
            if mode=='approved':ok('unexpected approval reported honestly',state['approval_created'] is True)
        ok(mode+' has no approval, upload, judgment, reset or old study replay request',
           set(api.calls).issubset({'/health','/workspaces/'+m.WORKSPACE,'/recovery115','/domains/draft'}))

for mode in ('source_changed','wrong_source_trace','existing_draft','missing_gate'):
    with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
        root=Path(folder);api=API(root)
        expected='WORKSPACE_CHANGED'
        if mode=='source_changed':api.ws['sources'][0]['version_hash']='changed'
        elif mode=='wrong_source_trace':api.ws['requirements_review']['trace_id']='other'
        elif mode=='existing_draft':api.ws['draft']={'draft_id':'other'};expected='EXISTING_DRAFT'
        else:(root/'.jt/upgrades/1.0.25/source-review-gate.json').unlink();expected='SOURCE_GATE_REQUIRED'
        rejects(mode+' stops before generation',lambda:m.run(api,root,r),expected)
        ok(mode+' generates nothing',api.generations==0)

# Exercise read-only failure diagnosis with an exact saved trace and the actual
# installed domain/evidence validators. This is explicitly synthetic test data.
with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
    root=Path(folder);api=API(root,'failure')
    try:m.run(api,root,r)
    except r.Stop:pass
    wanted='workflow_'+m.digest(['test-owner',m.REQUEST_KEY,''])[:32]
    domain=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text())
    domain['source_hashes']={m.SOURCE:api.source_hash}
    for rule in domain['rules']:
        for ref in rule['source_refs']:ref['source_id']=m.SOURCE
    domain['rules'][0]['source_refs'][0]['quote']='Not in the source.'
    trace={'trace_id':'trace_test','purpose':'draft_domain','payload':{'domain_id':wanted},
           'source_hashes':{m.SOURCE:api.source_hash},'result':domain,'attempts':[{'status':'OK'}]}
    from adapters.evidence import inspect_file
    meta,_=inspect_file('policy.txt',api.policy,'text/plain')
    source={**meta,'source_id':m.SOURCE,'blob_id':'test_blob','human':False}
    def response(req,timeout):
        assert req.method=='GET'
        path=req.full_url.split('/documents/')[1]
        value={'jt_workspaces/'+m.WORKSPACE:{'owner':'test-owner'},
               'jt_traces/trace_test':trace,
               'jt_sources/'+m.WORKSPACE+'-'+m.SOURCE:source}[path]
        return io.BytesIO(json.dumps({'fields':{'payload':{'stringValue':json.dumps(value)}}}).encode())
    with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='TEST_ONLY_TOKEN')), patch.object(m.urllib.request,'urlopen',response):
        m.diagnose(root,r)
    report=r.load(root/'.jt/upgrades/1.0.25/workflow-prepare.json')
    d=report['saved_answer_diagnostic']
    ok('failure diagnosis reuses saved answer with actual exact validator',d['revalidation']['status']=='REPRODUCED_FAILURE' and len(d['invalid_references'])==1)
    ok('diagnosis creates no model call and preserves raw answer',api.generations==1 and r.load(root/'deliverables/release125/workflow-failed-trace.json')==trace)

report={'status':'PASSED','checks':checks,'count':len(checks),'live_calls':0,'cloud_writes':0,
        'scope':'Standalone controller with explicit API/Firestore doubles; no deployed workflow success claimed.'}
(ROOT/'verification/prepare125_offline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASSED','checks':len(checks),'live_calls':0}))

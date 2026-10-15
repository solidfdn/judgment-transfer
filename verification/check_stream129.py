"""Actual stream/controller code with SDK doubles. Zero network/model calls."""
import ast
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
from core.models import JTError
from service import Service
from storage.repository import LocalRepository,Blobs
checks=[]
def ok(name,condition=True):
    assert condition,name
    checks.append(name)

tree=ast.parse((ROOT/'app/adapters/model.py').read_text())
tree.body=[n for n in tree.body if not(isinstance(n,ast.Import) and any(x.name=='httpx' for x in n.names))]
httpx=types.SimpleNamespace(**{n:type(n,(Exception,),{}) for n in
    ('ReadTimeout','TimeoutException','NetworkError','RemoteProtocolError')})
scope={'httpx':httpx,'__name__':'stream129_test'}
exec(compile(tree,'actual-model-adapter','exec'),scope)
Adapter=scope['LiveAdapter']
class Item(types.SimpleNamespace):
    @classmethod
    def from_text(cls,**kw):return cls(**kw)
class Response(Item):
    @property
    def text(self):return ''.join(p.text for c in self.candidates for p in c.content.parts)
class Cancelled(Exception):
    code=499;status='CANCELLED';message='The operation was cancelled.'

class StreamClient:
    def __init__(self,mode,value):
        self.mode,self.value=mode,value;self.closed=self.async_closed=self.stream_closed=False
        self.aio=Item(models=self,aclose=self.aclose);self.requests=[]
    async def aclose(self):self.async_closed=True
    def close(self):self.closed=True
    async def generate_content_stream(self,**kw):
        self.requests.append(kw)
        async def chunks():
            try:
                if self.mode=='cancelled':raise Cancelled()
                if self.mode=='silent':await asyncio.sleep(.2)
                raw=json.dumps(self.value);pivot=len(raw)//2
                yield Item(candidates=[Item(finish_reason=None,content=Item(parts=[Item(text=raw[:pivot])]))],usage_metadata=None)
                if self.mode=='partial':raise Cancelled()
                if self.mode=='stalled':await asyncio.sleep(.2)
                yield Item(candidates=[Item(finish_reason='MAX_TOKENS' if self.mode=='cutoff' else 'STOP',
                    content=Item(parts=[Item(text=raw[pivot:])]))],usage_metadata=Item(prompt_token_count=100,
                        candidates_token_count=500,thoughts_token_count=0,traffic_type='ON_DEMAND'))
            finally:self.stream_closed=True
        return chunks()

with tempfile.TemporaryDirectory() as folder:
    repo=LocalRepository(folder);blobs=Blobs(folder);adapter=Adapter.__new__(Adapter)
    adapter.repo,adapter.blobs,adapter.budget=repo,blobs,scope['Budget'](repo)
    adapter.types=Item(Part=Item,Content=Item,Candidate=Item,GenerateContentResponse=Response,
        HttpOptions=Item,HttpRetryOptions=Item,CountTokensConfig=Item,GenerateContentConfig=Item,ThinkingConfig=Item)
    def forbidden(**kw):raise AssertionError('Workflow unexpectedly used unary generation')
    adapter.client=Item(models=Item(count_tokens=lambda **kw:Item(total_tokens=100),generate_content=forbidden))
    service=Service(repo,blobs,adapter);ctx={'owner':'offline126','admin':True,'operation':'workflow126-test'}
    wid=service.create_workspace({'goal':'Check fictional expense evidence'},ctx)['workspace_id']
    data=(ROOT/'app/fixtures/expense_review/source_sop.txt').read_bytes()
    source=service.add_source(wid,'policy.txt',data,'text/plain',ctx,'expense_sop')
    ws=service.workspace(wid,ctx);ws['extraction']={'observations':[],'source_hashes':{'expense_sop':source['version_hash']}}
    repo.put('workspaces',wid,ws)
    domain=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text())
    clients=[];mode='pass';value=domain
    def new_client():
        c=StreamClient(mode,copy.deepcopy(value));clients.append(c);return c
    adapter._new_stream_client=new_client
    draft=service.draft_domain({'workspace_id':wid},ctx)
    trace=repo.get('traces',draft['trace_ids'][0]);entry=trace['attempts'][0]
    ok('complete streamed answer becomes an unapproved source-grounded draft',
       draft['origin']=='LIVE' and service.workspace(wid,ctx)['version']==-1 and
       all(r['approved_by'] is None for r in draft['domain']['rules']) and entry['complete_stream'] and entry['finish_reason']=='STOP')
    cfg=clients[-1].requests[0]['config']
    ok('workflow schema remains exact and is sent only through API',cfg.response_json_schema==scope['schema']('DomainSpec') and cfg.system_instruction==scope['SYSTEM'])
    ok('one attempt has 120-second total bound and 35-second first-text bound',
       trace['settings']['attempts']==1 and trace['settings']['model_window_seconds']==120 and
       35000 < entry['generation_timeout_ms'] <= 120000 and entry['first_text_timeout_ms']==35000)
    ok('stream progress is saved without treating fragments as a result',entry['chunk_count']==2 and
       entry['received_text_chars']>0 and entry['first_text_ms'] is not None and entry['last_text_ms'] is not None)
    original_draft=copy.deepcopy(service.workspace(wid,ctx)['draft_id'])
    for failure_mode in ('cancelled','partial','cutoff','invalid'):
        mode=failure_mode;value=copy.deepcopy(domain)
        if mode=='invalid':value.pop('input_fields')
        ctx['operation']='test126-'+mode;before=len(clients)
        try:service.draft_domain({'workspace_id':wid},ctx)
        except JTError as error:
            ok(mode+' cannot save a draft or automatically retry',error.code=='MODEL_FAILED' and len(clients)==before+1 and service.workspace(wid,ctx)['draft_id']==original_draft)
            if mode=='partial':ok('cancelled partial stream retains progress only',error.trace['attempts'][0]['received_text_chars']>0 and 'result' not in error.trace)
            if mode=='invalid':ok('invalid complete JSON retained for diagnosis',bool(error.trace['raw_response_text']) and bool(error.trace['attempts'][0]['validation_errors']))
        else:raise AssertionError(mode+' accepted')
    for mode,total,first,flag in [('silent',.08,.01,'local_first_text_deadline_reached'),('stalled',.02,.01,'local_total_deadline_reached')]:
        value=domain;entry={'attempt':1}
        try:asyncio.run(adapter._stream_response(Item(),Item(),entry,total,first_text_seconds=first))
        except httpx.ReadTimeout:ok(mode+' has an actual bounded cancellation',entry.get(flag) is True)
        else:raise AssertionError(mode+' did not stop')
    ok('all per-request clients and streams close on success and failure',all(c.closed and c.async_closed and c.stream_closed for c in clients))
    mode='pass';value=domain;entry={'attempt':1}
    asyncio.run(adapter._stream_response(Item(),Item(),entry,60))
    ok('new decision first-text deadline is thirty-five seconds',entry['first_text_timeout_ms']==35000)
    mode='pass';value={'case_id':'decision_probe','outcome':'HOLD','action_id':'hold_case','rule_ids':[],
        'source_refs':[],'missing_fields':[],'explanation':'Explicit test double.'}
    before=len(clients)
    _,decision_trace=adapter.invoke('decide',{'case':{'case_id':'decision_probe'},'arm':'C_JT_RULES'},scope['schema']('Decision'),[source],ctx['owner'],True)
    ok('decision uses one bounded sixty-second attempt',len(clients)==before+1 and decision_trace['settings']['attempts']==1 and decision_trace['settings']['model_window_seconds']==60 and 35000<decision_trace['attempts'][0]['generation_timeout_ms']<=60000)
    ok('decision keeps exact contract and business prompt',clients[-1].requests[0]['config'].response_json_schema==scope['schema']('Decision') and clients[-1].requests[0]['config'].system_instruction==scope['SYSTEM'])
    mode='cancelled';before=len(clients)
    try:adapter.invoke('decide',{'case':{'case_id':'decision_probe'},'arm':'C_JT_RULES'},scope['schema']('Decision'),[source],ctx['owner'],True)
    except JTError as error:ok('failed decision does not auto-retry',len(clients)==before+1 and len(error.trace['attempts'])==1 and 'result' not in error.trace)
    else:raise AssertionError('cancellation accepted')
    mode='pass'
    # A completed response with invalid provenance must keep its trace attached.
    value=copy.deepcopy(domain);value['rules'][0]['source_refs'][0]['quote']='Absent from this source.'
    ctx['operation']='test126-bad-evidence'
    try:service.draft_domain({'workspace_id':wid},ctx)
    except JTError as error:
        ok('post-generation evidence failure includes trace and validation stage',error.validation['stage']=='workflow_validation' and error.trace['result']==value)
    else:raise AssertionError('invalid evidence accepted')

# Reuse the real error response function without requiring Flask installation.
tree=ast.parse((ROOT/'app/main.py').read_text());factory=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_app')
fn=next(n for n in factory.body if isinstance(n,ast.FunctionDef) and n.name=='error_body')
g=Item(ctx={'admin':True},request_id='req_test');ns={'g':g}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-error-body','exec'),ns)
error=JTError('MODEL_FAILED','Stopped');error.trace={'trace_id':'trace_test','elapsed_ms':33072,
    'raw_response_text':'DO NOT EXPOSE','settings':{'attempts':1,'model_window_seconds':120},
    'attempts':[{'status':'FAILED','provider_code':'499','failed_stage_elapsed_ms':32530,'received_text_chars':123}]}
detail=ns['error_body'](error)
ok('administrator gets failure timing without raw response',detail['error']['diagnostic']['attempts'][0]['failed_stage_elapsed_ms']==32530 and 'DO NOT EXPOSE' not in json.dumps(detail))
g.ctx={'admin':False};ok('public error still hides diagnostics','diagnostic' not in ns['error_body'](error)['error'])

spec=importlib.util.spec_from_file_location('release126',ROOT/'releases/jt_release_126.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
with patch.object(release.subprocess,'run',return_value=Item(returncode=0)) as run:
    release.verify_workflow(Path('/installed'))
    ok('installer uses pinned interpreter and one workflow gate',run.call_args.args[0]==['/installed/.venv/bin/python','/installed/steps/prepare_workflow126.py'])
with patch.object(release.subprocess,'run',return_value=Item(returncode=1)):
    try:release.verify_workflow(Path('/installed'))
    except RuntimeError as e:ok('failed workflow gate stops release command','WORKFLOW_GATE_STOPPED' in str(e))
    else:raise AssertionError('failed gate ignored')

report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'scope':'Actual adapter, service, async stream and diagnostic code with SDK/HTTP doubles; LIVE acceptance pending.'}
(ROOT/'verification/stream129_offline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':len(checks),'new_model_calls':0}))

"""Bounded transient recovery in the actual adapter/service; no network calls."""
import asyncio,copy,json,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'app')]
import config,httpx
from adapters.model import LiveAdapter,Budget,schema
from core.models import JTError,digest
from service import Service
from storage.repository import LocalRepository,Blobs
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
class Item(types.SimpleNamespace):
 @classmethod
 def from_text(cls,**kw):return cls(**kw)
class Response(Item):
 @property
 def text(self):return ''.join(p.text for c in self.candidates for p in c.content.parts)
class ProviderError(Exception):
 def __init__(self,code):self.code=code;super().__init__('Explicit provider double')
class StreamClient:
 def __init__(self,mode,value):
  self.mode,self.value=mode,value;self.closed=self.async_closed=self.stream_closed=False;self.requests=[]
  self.aio=Item(models=self,aclose=self.aclose)
 async def aclose(self):self.async_closed=True
 def close(self):self.closed=True
 async def generate_content_stream(self,**kw):
  self.requests.append(kw)
  async def chunks():
   try:
    if self.mode=='silent':await asyncio.sleep(.2)
    if self.mode=='timeout':raise httpx.ReadTimeout('Explicit timeout double')
    if isinstance(self.mode,int):raise ProviderError(self.mode)
    text=json.dumps(self.value) if self.mode!='invalid_json' else '{invalid'
    yield Item(candidates=[Item(finish_reason='MAX_TOKENS' if self.mode=='cutoff' else 'STOP',content=Item(parts=[Item(text=text)]))],usage_metadata=Item(prompt_token_count=100,candidates_token_count=100,thoughts_token_count=0,traffic_type='ON_DEMAND'))
   finally:self.stream_closed=True
  return chunks()
with tempfile.TemporaryDirectory() as folder:
 repo=LocalRepository(folder);blobs=Blobs(folder);a=LiveAdapter.__new__(LiveAdapter);a.repo,a.blobs,a.budget=repo,blobs,Budget(repo)
 a.types=Item(Part=Item,Content=Item,Candidate=Item,GenerateContentResponse=Response,HttpOptions=Item,HttpRetryOptions=Item,CountTokensConfig=Item,GenerateContentConfig=Item,ThinkingConfig=Item)
 counts=[]
 def count(**kw):counts.append(kw);return Item(total_tokens=100)
 a.client=Item(models=Item(count_tokens=count));clients=[];modes=[]
 decision={'case_id':'probe','outcome':'HOLD','action_id':'hold','rule_ids':[],'source_refs':[],'missing_fields':[],'explanation':'Explicit test-double hold.'}
 def new_client():
  client=StreamClient(modes.pop(0),copy.deepcopy(decision));clients.append(client);return client
 a._new_stream_client=new_client
 def invoke(owner):return a.invoke('decide',{'case':{'case_id':decision['case_id']},'arm':'C_JT_RULES'},schema('Decision'),[],owner,False)
 ok('production policy is two attempts within 125 seconds',config.SETTINGS['attempts']==2 and config.SETTINGS['model_window_seconds']==125 and config.SETTINGS['call_limit_seconds']==60 and config.SETTINGS['first_text_timeout_seconds']==60)
 modes[:]=['silent','pass'];before_counts=len(counts)
 with patch.dict(config.SETTINGS,{'first_text_timeout_seconds':.02}):result,trace=invoke('recovered')
 ok('zero-text first attempt recovers once',result==decision and [x['status'] for x in trace['attempts']]==['FAILED','OK'] and trace['attempts'][0]['chunk_count']==0 and trace['attempts'][0]['local_first_text_deadline_reached'])
 ok('retry retains an ample independent generation window',trace['attempts'][1]['generation_timeout_ms']>35000)
 ok('same invocation reuses token count',len(counts)==before_counts+1 and trace['attempts'][1]['count_reused_within_same_invocation'])
 ok('both attempts consume the unchanged call budget',repo.get('budget',digest('recovered')[:40])=={'calls':2,'decisions':2} and Budget.PUBLIC_CALLS==24)
 ok('failed attempt retains reserved cost',trace['attempts'][0]['cost_usd']==trace['attempts'][0]['reserved_usd'] and trace['attempts'][0]['cost_usd']>0)
 ok('stream clients and generators close before reuse',all(c.closed and c.async_closed and c.stream_closed for c in clients))
 for code in (429,500,502,503,504):
  modes[:]=[code,'pass'];_,t=invoke('retry-'+str(code));ok(str(code)+' gets exactly one recovery',[x['status'] for x in t['attempts']]==['FAILED','OK'])
 for mode in ('timeout',400,401,403,499,'invalid_json','cutoff'):
  modes[:]=[mode,mode];start=len(clients)
  try:invoke('stop-'+str(mode))
  except JTError as e:ok(str(mode)+' stops without adopting a result',e.code=='MODEL_FAILED' and 'result' not in e.trace and len(clients)-start==(2 if mode=='timeout' else 1))
  else:raise AssertionError(mode)
 owner='last-slot';repo.put('budget',digest(owner)[:40],{'calls':23,'decisions':3});modes[:]=['timeout','pass'];start=len(clients)
 try:invoke(owner)
 except JTError as e:ok('retry cannot exceed 24 model calls',e.code=='CALL_LIMIT' and len(clients)==start+1 and repo.get('budget',digest(owner)[:40])['calls']==24)
 else:raise AssertionError('budget bypass')
 # Real Service commits exactly one receipt after the recovered complete answer.
 svc=Service(repo,blobs,a);ctx={'owner':'service-check','admin':False,'operation':'create'}
 wid=svc.create_workspace({'goal':'Check isolated document evidence'},ctx)['workspace_id']
 source=svc.add_source(wid,'policy.txt',(ROOT/'app/fixtures/expense_review/source_sop.txt').read_bytes(),'text/plain',ctx,'expense_sop')
 domain=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text());case=json.loads((ROOT/'app/fixtures/expense_review/cases.json').read_text())[2]
 for rule in domain['rules']:rule['approved_by']='human:offline'
 repo.put('domains',wid+'-v0',{'domain':domain});ws=svc.workspace(wid,ctx);ws.update(version=0,status='READY');repo.put('workspaces',wid,ws)
 svc.import_cases({'workspace_id':wid,'cases':[case],'reviewer_name':'Offline validation'},dict(ctx,operation='import'))
 run=svc.create_run({'workspace_id':wid,'arm':'C_JT_RULES','reviewer_name':'Offline validation'},dict(ctx,operation='run'))
 decision.update(case_id=case['case_id'],action_id=domain['default_action_id']);modes[:]=['timeout','pass'];stepctx=dict(ctx,operation='step')
 applied=svc.step(run['run_id'],stepctx);view=svc.run_view(run['run_id'],ctx)
 ok('recovered hold commits once and ends the task',view['tasks'][0]['status']=='COMPLETED' and len(view['tasks'][0]['receipt_ids'])==1 and view['tasks'][0]['decision']['outcome']=='HOLD')
 start=len(clients);duplicate=svc.step(run['run_id'],stepctx)
 ok('replayed successful step is idempotent',duplicate.get('duplicate') and len(clients)==start and duplicate['receipt']['receipt_id']==applied['receipt']['receipt_id'])
 second=svc.create_run({'workspace_id':wid,'arm':'C_JT_RULES','reviewer_name':'Offline validation'},dict(ctx,operation='run-fail'));modes[:]=['timeout','timeout']
 svc.step(second['run_id'],dict(ctx,operation='step-fail'));failed=svc.run_view(second['run_id'],ctx)['tasks'][0]
 ok('two failures keep initial state with no receipt',failed['status']=='FAILED' and failed['state']==case['initial_state'] and not failed['receipt_ids'])
 before=len(clients);svc.step(second['run_id'],dict(ctx,operation='step-fail'))
 ok('replaying a failed request sends no further generation',len(clients)==before)
 # Current owner retains its counters; preflight includes both possible attempts.
 owner='existing-owner';repo.put('budget',digest(owner)[:40],{'calls':4,'decisions':2});snap=repo.get('budget',digest(owner)[:40]);remaining=Budget(repo).public_allowance(owner)
 ok('existing usage is retained under aligned decision sublimit',remaining['model_calls']==20 and remaining['judgment_calls']==22 and repo.get('budget',digest(owner)[:40])==snap)
 from run_capacity import plan
 planned=plan(svc,{'plan_comparison':True},{'owner':owner,'admin':False},(ws,domain,[case]*3,'C_JT_RULES','dev',1))
 ok('same three-case pair reserves capacity for all retries',planned['can_start'] and planned['required']=={'judgment_calls':12,'model_calls':15})
 ok('125-second generation window fits unchanged 135-second commit window',config.SETTINGS['model_window_seconds']<135)
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual async stream, adapter, Budget, service, commit idempotency and capacity code with explicit SDK/transport doubles and isolated local storage. Not a live reliability benchmark.'}
(ROOT/'verification/retry133_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

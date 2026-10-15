"""Bounded tests of actual invoke control flow and saved USD recovery."""
import ast,copy,datetime,hashlib,importlib.util,json,sys,tempfile,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];checks=[]
def digest(v):return hashlib.sha256(v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def ok(name,value=True):assert value,name;checks.append(name)
class JTError(Exception):
    def __init__(self,code,message,*args):self.code=code;super().__init__(message)
class NetworkError(Exception):pass
class TimeoutErrorDouble(NetworkError):pass
class ProtocolError(NetworkError):pass
class ServerError(Exception):
    def __init__(self,code):self.code=code
class SchemaValidator:
    def __init__(self,schema):pass
    def iter_errors(self,value):return []
class Clock:
    def __init__(self):self.now=0;self.sleeps=[]
    def monotonic(self):return self.now
    def sleep(self,n):self.sleeps.append(n);self.now+=n
class Budget:
    def __init__(self):self.reservations=[];self.denied=False
    def reserve(self,*a,**kw):
        if self.denied:raise JTError('BUDGET_LIMIT','budget double')
        self.reservations.append((a,kw));return .15
    def settle(self,*a):pass
class Repo:
    def __init__(self):self.traces=[]
    def put(self,*a):self.traces.append(copy.deepcopy(a[-1]))
def invoke_from(text,clock):
    tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and any(isinstance(v,ast.FunctionDef) and v.name=='invoke' for v in n.body))
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='invoke')
    import asyncio
    scope={'json':json,'time':clock,'digest':digest,'uuid':uuid,'asyncio':asyncio,'JTError':JTError,'SYSTEM':'same system instruction',
        'runtime_diagnostic':lambda c:{'client_scope':'process_shared'},'provider_diagnostic':lambda e:{'code':getattr(e,'code',0)},
        'Draft202012Validator':SchemaValidator,'httpx':types.SimpleNamespace(TimeoutException=TimeoutErrorDouble,NetworkError=NetworkError,RemoteProtocolError=ProtocolError),
        'config':types.SimpleNamespace(MODEL='gemini-3.5-flash',CODE_HASH='new-code',REQUEST_TIER='priority',INPUT_PRICE=2.7,OUTPUT_PRICE=16.2,REQUEST_HEADERS={},
            SETTINGS={'model':'gemini-3.5-flash','attempts':2,'model_window_seconds':125,'call_limit_seconds':60,'first_text_timeout_seconds':60,'retry_policy':'one_bounded_transient_retry'})}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-invoke','exec'),scope);return scope['invoke']
class FakeAdapter:
    def __init__(self,clock,events):
        self.clock,self.events=clock,list(events);self.repo=Repo();self.budget=Budget();self.stream=[];self.sync=[]
        ctor=lambda **kw:types.SimpleNamespace(**kw)
        self.types=types.SimpleNamespace(**{k:ctor for k in ('Content','HttpOptions','HttpRetryOptions','CountTokensConfig','GenerateContentConfig','ThinkingConfig')})
        def count(**kw):return types.SimpleNamespace(total_tokens=100)
        def sync(**kw):self.sync.append(kw);raise AssertionError('unexpected sync generation')
        self.client=types.SimpleNamespace(models=types.SimpleNamespace(count_tokens=count,generate_content=sync))
    def parts(self,*a):return ['unchanged parts']
    async def _stream_response(self,content,generation,entry,seconds,first_text_seconds=None):
        self.stream.append({'seconds':seconds,'schema':copy.deepcopy(generation.response_json_schema),'system':generation.system_instruction})
        event=self.events.pop(0);self.clock.now+=60 if isinstance(event,Exception) else .2
        if isinstance(event,Exception):raise event
        entry.update(finish_reason='STOP',chunk_count=1,complete_stream=True)
        return types.SimpleNamespace(text=event,usage_metadata=types.SimpleNamespace(prompt_token_count=100,candidates_token_count=10,thoughts_token_count=0,traffic_type='ON_DEMAND_PRIORITY'),model_version='gemini-3.5-flash')

new=(ROOT/'app/adapters/model.py').read_text();old=(ROOT/'verification/reference/model135.py').read_text()
for name in ('decide','propose_question','draft_rules','_stream_response','parts'):
    def method(s):
        tree=ast.parse(s);return next(ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    ok(name+' business prompt/schema/stream implementation unchanged',method(new)==method(old))
for purpose in ('draft_rules','propose_question'):
    clock=Clock();adapter=FakeAdapter(clock,[ServerError(504),'{"rules":[]}']);invoke=invoke_from(new,clock)
    result,trace=invoke(adapter,purpose,{'instruction':'same instruction'},{'type':'object'},[],'owner',True)
    ok(purpose+' retries 504 once using two bounded streamed attempts',len(adapter.stream)==2 and all(x['seconds']<=60 for x in adapter.stream) and not adapter.sync and clock.sleeps==[1])
    ok(purpose+' records actual transport/deadline and both attempts',trace['settings']['transport']=='streamGenerateContent' and trace['settings']['call_limit_seconds']==60 and [a['status'] for a in trace['attempts']]==['FAILED','OK'])
for error in (TimeoutErrorDouble(),NetworkError(),ProtocolError(),ServerError(429),ServerError(500),ServerError(503)):
    clock=Clock();adapter=FakeAdapter(clock,[error,'{}']);invoke_from(new,clock)(adapter,'draft_rules',{}, {},[],'o',True)
    ok(type(error).__name__+' '+str(getattr(error,'code',''))+' receives at most one transient retry',len(adapter.stream)==2)
for error in (ServerError(400),ValueError('bad JSON')):
    clock=Clock();adapter=FakeAdapter(clock,[error])
    try:invoke_from(new,clock)(adapter,'draft_rules',{}, {},[],'o',True)
    except JTError as e:ok('nontransient '+type(error).__name__+' is not retried',e.code=='MODEL_FAILED' and len(adapter.stream)==1 and not clock.sleeps)
    else:raise AssertionError('error accepted')
clock=Clock();adapter=FakeAdapter(clock,['{'])
try:invoke_from(new,clock)(adapter,'draft_rules',{}, {},[],'o',True)
except JTError:ok('malformed model answer never triggers a transport retry',len(adapter.stream)==1)
clock=Clock();adapter=FakeAdapter(clock,['{}']);adapter.budget.denied=True
try:invoke_from(new,clock)(adapter,'draft_rules',{}, {},[],'o',True)
except JTError as e:ok('budget refusal makes no generation attempt',e.code=='BUDGET_LIMIT' and not adapter.stream)
logs=[]
for source in (old,new):
    clock=Clock();adapter=FakeAdapter(clock,['{}']);_,trace=invoke_from(source,clock)(adapter,'decide',{}, {},[],'o',True)
    logs.append((adapter.stream,trace['settings'],trace['prompt_hash'],adapter.budget.reservations))
ok('decision invocation parameters/prompt/settings/reservation behavior are identical',logs[0]==logs[1])

# Load actual cross-package guard with an explicit current-package identity.
scope={'config':types.SimpleNamespace(VERSION='1.0.36',CODE_HASH='new-code')}
tr=ast.parse((ROOT/'app/comparison.py').read_text());nodes=[n for n in tr.body if isinstance(n,(ast.Assign,ast.FunctionDef))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual-comparison','exec'),scope)
a={'code_hash':scope['PREPARATION_BASELINE']};b={'code_hash':'new-code'}
ok('only the reviewed 35-to-current-36 pair is admitted',scope['preparation_transport_pair'](a,b))
ok('arbitrary old/new packages and reversed pair remain rejected',not scope['preparation_transport_pair']({'code_hash':'other'},b) and not scope['preparation_transport_pair'](a,{'code_hash':'other'}) and not scope['preparation_transport_pair'](b,a))
scope['config'].VERSION='1.0.37'
ok('future release is not admitted by this exception',not scope['preparation_transport_pair'](a,b))
scope['config'].VERSION='1.0.36'
base={'workspace_id':'ws','mode':'LIVE','split':'dev','dataset_hash':'same-cases','repeats':1,'case_ids':['c'],'model_settings':{'seconds':60},
    'code_hash':scope['PREPARATION_BASELINE'],'domain':{'version':0,'source_hashes':{'s':'hash'}},'arm':'C_JT_RULES','source_hashes':{'s':'hash'}}
after=copy.deepcopy(base);after.update(code_hash='new-code',domain={'version':1,'source_hashes':{'s':'hash'}})
views={'a':{'run':base,'metrics':{'complete':True,'stale':False}},'b':{'run':after,'metrics':{'complete':True,'stale':False}}}
service=types.SimpleNamespace(run_view=lambda key,ctx:copy.deepcopy(views[key]))
ok('actual comparison accepts the audited pair with every other check passing',scope['compare'](service,'a','b',{})['comparable'])
for field,value in [('dataset_hash','other'),('workspace_id','other'),('model_settings',{'seconds':35})]:
    original=after[field];after[field]=value
    ok('audited pair still rejects changed '+field,not scope['compare'](service,'a','b',{})['comparable'])
    after[field]=original

sys.modules['core']=types.ModuleType('core');sys.modules['core.models']=types.SimpleNamespace(digest=digest)
sys.modules['steps.approved_stop135']=types.SimpleNamespace(previous_records=lambda *a:None)
spec=importlib.util.spec_from_file_location('recovery136',ROOT/'steps/usd_recovery136.py');recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
class API:
    def __init__(self,view):self.view=view;self.requests=[];self.used=22
    def call(self,path,data=None,**kw):
        self.requests.append((path,data))
        if path=='/recovery115':return {'session':{'calls':100+self.used}}
        if path.startswith('/exports/'):return copy.deepcopy(self.view)
        if path.startswith('/workspaces/'):return {'version':0,'frozen':False,'teaching_ids':[],'run_ids':[recovery.BASELINE],'question_ids':['q']}
        return {}
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
    r=types.SimpleNamespace(Stop=JTError,load=lambda p:json.loads(p.read_text()) if p.exists() else {},save=save)
    view={'run':{'code_hash':recovery.BASELINE_CODE},'tasks':[{'status':'COMPLETED'}]*4}
    immutable={k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}
    oldp={'status':'FAILED','pending':'teaching','reviewer_name':'Reviewer','workspace_id':recovery.WORKSPACE,'baseline_run_id':recovery.BASELINE,'baseline_hash':digest(immutable),
        'steps':{'question':{'question':{'question_id':'q'}},'baseline-0':{'saved':'receipt'}},'error':{'code':'MODEL_FAILED','diagnostic':{'trace_id':recovery.FAILED_TRACE}}}
    oldpath=root/'.jt/upgrades/1.0.35/usd-demo.json';save(oldpath,oldp);before=oldpath.read_bytes()
    save(root/'deliverables/release135/usd/failed-generation-trace.json',{'trace_id':recovery.FAILED_TRACE,'purpose':'draft_rules','attempts':[{'provider_code':'504'}]})
    save(root/'.jt/upgrades/1.0.35/approved-stop.json',{'status':'PASSED','report':{'new_model_calls':0}})
    api=API(view);p=recovery.seed(root,api,r,'Reviewer')
    ok('recovery copies completed results and question without regenerating them',p['steps']==oldp['steps'] and all(data is None for _,data in api.requests))
    ok('original failed checkpoint remains byte-for-byte unchanged',oldpath.read_bytes()==before and p['prior_failure']==oldp['error'])
    ok('same recovery checkpoint is reopened rather than replaced',recovery.seed(root,api,r,'Reviewer')==p)
    # Exercise the actual nested controller functions: cached question and
    # completed baseline must return before any POST or new run creation.
    fixture=ROOT/'app/fixtures/expense_review_usd';cases=json.loads((fixture/'cases.json').read_text())[:4]
    targets=['ready_for_approval','hold_case','hold_case','hold_case']
    saved_view={'run':{'dataset_hash':digest(cases)},'tasks':[],'receipts':[]}
    for case,target in zip(cases,targets):
        saved_view['tasks'].append({'task_id':case['case_id'],'case_id':case['case_id'],'status':'COMPLETED','decision':{'action_id':target},'raw_decision':{'action_id':target}})
        saved_view['receipts'].append({'task_id':case['case_id'],'case_hash':digest(case),'before_state':case['initial_state']})
    immutable={k:saved_view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}
    controller=ast.parse((ROOT/'steps/usd_demo136.py').read_text());run_node=next(n for n in controller.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    nested=[n for n in run_node.body if isinstance(n,ast.FunctionDef) and n.name in ('call','check_results','execute')]
    fake_api=API(saved_view);localp={'baseline_run_id':recovery.BASELINE,'baseline_hash':digest(immutable),'steps':oldp['steps']}
    context={'p':localp,'api':fake_api,'digest':digest,'r':r,'immutable':lambda v:{k:v.get(k) for k in immutable}}
    exec(compile(ast.Module(body=nested,type_ignores=[]),'actual-resume-controller','exec'),context)
    context['execute']('baseline',cases,targets)
    context['call']('question','/questions',{'run_id':recovery.BASELINE})
    ok('actual continuation performs only GET for the saved baseline and no question request',fake_api.requests==[('/exports/'+recovery.BASELINE,None)])
    bounded=recovery.BoundedAPI(api,r,100);bounded.call('/teachings',{})
    api.used=23
    try:bounded.call('/teachings',{})
    except JTError as e:ok('two-attempt guidance stays inside the original total 24 ceiling',e.code=='USD_ATTEMPT_LIMIT')
    else:raise AssertionError('excess attempt admitted')
report={'status':'PASSED','passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'scope':'Actual invocation, recovery and audited comparison logic with explicit provider/schema/clock/storage/API doubles. Unchanged core/evidence checks reused; live continuation remains pending.'}
(ROOT/'verification/preparation136_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

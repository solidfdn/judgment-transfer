"""Actual run creation, capacity gate and checkpoint recovery regression checks."""
import ast,copy,datetime as dt,hashlib,importlib.util,json,math,sys,tempfile,time,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def rejects(name,fn,code):
    try:fn()
    except Exception as e:ok(name,getattr(e,'code',None)==code)
    else:raise AssertionError(name)
core=types.ModuleType('core.models');core.__dict__.update(copy=copy,hashlib=hashlib,json=json,math=math,Path=Path,check=lambda n,v:v)
tree=ast.parse((ROOT/'app/core/models.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and getattr(n,'name','')!='check'],type_ignores=[]),'actual-core','exec'),core.__dict__)
sys.modules['core']=types.ModuleType('core');sys.modules['core.models']=core
config=types.ModuleType('config');config.VERSION='1.0.37';config.CODE_HASH='current137';config.SETTINGS={'attempts':2}
sys.modules['config']=config
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
comparison=module('comparison',ROOT/'app/comparison.py');capacity=module('run_capacity',ROOT/'app/run_capacity.py')
sys.modules['history']=types.SimpleNamespace(actor=lambda body:{'reviewer_name':body['reviewer_name'],'memo':body.get('memo','')})
scope=dict(core.__dict__,config=config,dt=dt,time=time,uuid=uuid,ARMS=('A_SOURCE_ONLY','B_TEXT_ADDED','C_JT_RULES'))
tree=ast.parse((ROOT/'app/service.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))],type_ignores=[]),'actual-service','exec'),scope)
class Repo:
    def __init__(self):self.data={}
    def get(self,*key):return copy.deepcopy(self.data.get(key))
    def put(self,kind,key,value):self.data[(kind,key)]=copy.deepcopy(value)
    def atomic(self,keys,fn):
        v={k:copy.deepcopy(self.data.get(k)) for k in keys};r=fn(v);self.data.update(copy.deepcopy(v));return copy.deepcopy(r)
fixture=ROOT/'app/fixtures/expense_review_usd';cases=json.loads((fixture/'cases.json').read_text());domain=json.loads((fixture/'domain_v0.json').read_text());domain['version']=1
body={'workspace_id':'ws','mode':'LIVE','arm':'C_JT_RULES','split':'dev','repeats':1,'case_ids':[c['case_id'] for c in cases[:4]],'baseline_run_id':'baseline','reviewer_name':'Reviewer'}
ctx={'owner':'owner','operation':'after137','admin':True}
baseline={'run':{'workspace_id':'ws','mode':'LIVE','arm':'C_JT_RULES','split':'dev','code_hash':comparison.PREPARATION_BASELINE,'model_settings':copy.deepcopy(config.SETTINGS),'domain':{'version':0},'case_ids':body['case_ids']},'metrics':{'complete':True,'stale':False}}
def setup():
    repo=Repo();adapter=types.SimpleNamespace(mode='LIVE',budget=types.SimpleNamespace(public_allowance=lambda owner:{'judgment_calls':24,'model_calls':24}))
    service=scope['Service'](repo,None,adapter)
    ws={'workspace_id':'ws','owner':'owner','status':'READY','version':1,'case_ids':[c['case_id'] for c in cases],
        'source_ids':['expense_sop'],'human_source_ids':[],'teaching_ids':['teaching'],'shared_trace_ids':['guidance_trace'],'approved_count':1,'run_ids':['baseline'],'leases':{},'frozen':False}
    repo.put('workspaces','ws',ws);repo.put('domains','ws-v1',{'domain':domain})
    repo.put('teachings','teaching',{'teaching':{'approval_state':'APPROVED','human_text':'Saved approved explanation'}})
    for case in cases:repo.put('cases','ws-'+case['case_id'],case)
    repo.put('sources','ws-expense_sop',{'source_id':'expense_sop','version_hash':domain['source_hashes']['expense_sop']})
    view=copy.deepcopy(baseline);service.run_view=lambda rid,context:copy.deepcopy(view)
    return service,repo,view
s,repo,v=setup();created=s.create_run(body,ctx);saved=repo.get('runs',created['run_id'])
ok('actual Service.create_run crosses run_inputs/select_cases/plan and creates the after run',created['total']==4 and saved['code_hash']==config.CODE_HASH and saved['baseline_run_id']=='baseline')
ok('all four new tasks start from the saved initial state',all(repo.get('tasks',tid)['state']==cases[i]['initial_state'] for i,tid in enumerate(saved['task_ids'])))
ok('baseline record remains separate from new tasks',repo.get('workspaces','ws')['run_ids']==['baseline',created['run_id']])
for name,mutate,code in [
    ('unreviewed package',lambda v:v['run'].update(code_hash='other'),'RUN_PROTOCOL_CHANGED'),
    ('changed model settings',lambda v:v['run'].update(model_settings={'attempts':1}),'RUN_PROTOCOL_CHANGED'),
    ('changed mode',lambda v:v['run'].update(mode='MOCK'),'RUN_PROTOCOL_CHANGED'),
    ('other workspace',lambda v:v['run'].update(workspace_id='other'),'INVALID_INPUT'),
    ('incomplete baseline',lambda v:v['metrics'].update(complete=False),'INVALID_INPUT'),
    ('stale source evidence',lambda v:v['metrics'].update(stale=True),'INVALID_INPUT')]:
    s,repo,v=setup();mutate(v);rejects(name+' still blocks run creation',lambda:s.create_run(body,ctx),code)
    ok(name+' creates no run or task',repo.get('workspaces','ws')['run_ids']==['baseline'])
s,repo,v=setup();rejects('changed case order is still refused',lambda:s.create_run({**body,'case_ids':list(reversed(body['case_ids']))},ctx),'INVALID_INPUT')
s,repo,v=setup();config.VERSION='1.0.38';rejects('an unaudited future package is refused',lambda:s.create_run(body,ctx),'RUN_PROTOCOL_CHANGED');config.VERSION='1.0.37'
s,repo,v=setup();v['run']['code_hash']=config.CODE_HASH
ok('same-package baseline behavior is retained',s.create_run(body,ctx)['total']==4)
s,repo,v=setup();plan=capacity.plan(s,{'plan_comparison':True},{**ctx,'admin':False},({'owner':'owner'},domain,cases[:3],'C_JT_RULES','dev',1))
ok('comparison capacity includes two question and two guidance attempts',plan['required']=={'judgment_calls':12,'model_calls':16})
s.adapter.budget.public_allowance=lambda owner:{'judgment_calls':24,'model_calls':15}
plan=capacity.plan(s,{'plan_comparison':True},{**ctx,'admin':False},({'owner':'owner'},domain,cases[:3],'C_JT_RULES','dev',1))
ok('capacity no longer undercounts the new preparation retry',not plan['can_start'] and plan['max_cases']==2)

sys.modules['steps.usd_recovery136']=types.SimpleNamespace(BoundedAPI=object,previous_records=lambda *a:None,BASELINE='baseline',WORKSPACE='ws',BASELINE_CODE=comparison.PREPARATION_BASELINE)
recovery=module('recovery137_test',ROOT/'steps/usd_recovery137.py')
class API:
    def __init__(self,view,ws):self.view,self.ws,self.requests=view,ws,[]
    def call(self,path,data=None,**kw):
        assert data is None,'unexpected cloud mutation';self.requests.append(path)
        return copy.deepcopy(self.view if path.startswith('/exports/') else self.ws)
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    r=types.SimpleNamespace(Stop=core.JTError,load=lambda p:json.loads(p.read_text()) if p.exists() else {},save=save)
    view={'run':{'code_hash':comparison.PREPARATION_BASELINE},'tasks':[{'status':'COMPLETED'}]*4}
    imm={k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}
    old={'status':'FAILED','pending':'create-after','error':{'code':'RUN_PROTOCOL_CHANGED','request_id':'old-request'},'reviewer_name':'Reviewer','workspace_id':'ws','baseline_run_id':'baseline','baseline_hash':core.digest(imm),
        'steps':{'question':{'saved':'question'},'teaching':{'teaching':{'teaching_id':'t'}},'approve-teaching':{'domain':domain}},'prior_failure':{'code':'MODEL_FAILED'}}
    path=root/'.jt/upgrades/1.0.36/usd-demo.json';save(path,old);raw=path.read_bytes()
    ws={'version':1,'frozen':False,'run_ids':['baseline'],'teaching_ids':['t'],'domain':domain,'teachings':[{'teaching':{'teaching_id':'t','approval_state':'APPROVED'}}]}
    api=API(view,ws);p=recovery.seed(root,api,r,'Reviewer')
    ok('recovery retains question, guidance and approval without a new request',p['steps']==old['steps'] and api.requests==['/exports/baseline','/workspaces/ws'])
    ok('both previous failures and original checkpoint bytes are preserved',path.read_bytes()==raw and p['prior_failures']==[old['prior_failure'],old['error']])
    ok('same recovery checkpoint is reused',recovery.seed(root,api,r,'Reviewer')==p)
    tree=ast.parse((ROOT/'steps/usd_demo137.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    call=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='call')
    context={'p':p,'api':api};exec(compile(ast.Module(body=[call],type_ignores=[]),'actual-cached-call','exec'),context)
    count=len(api.requests)
    for name,url in [('question','/questions'),('teaching','/teachings'),('approve-teaching','/teachings/t/approve')]:context['call'](name,url,{})
    ok('actual continuation sends no question/guidance/approval POST for saved steps',len(api.requests)==count)
report={'status':'PASSED','passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'scope':'Actual Service.create_run through run_inputs/select_cases/plan, actual cached-call and recovery logic with explicit schema/storage/history/API doubles. Live continuation pending.'}
(ROOT/'verification/run_start137_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

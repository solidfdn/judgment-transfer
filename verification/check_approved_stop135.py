"""Focused control-flow regression checks; explicit storage/model/schema doubles."""
import ast,copy,datetime as dt,hashlib,importlib.util,json,math,sys,time,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def ok(name,value=True):
    assert value,name
    checks.append(name)
def rejects(name,fn,code):
    try:fn()
    except Exception as error:ok(name,getattr(error,'code',None)==code)
    else:raise AssertionError(name)

# Reuse the actual unchanged rule evaluator/executor and actual Service.step.
# Schema validation, persistence and provider transport have explicit doubles;
# this check does not claim a new schema, Firestore or LIVE model test.
core=types.ModuleType('core.models')
core.__dict__.update(copy=copy,hashlib=hashlib,json=json,math=math,Path=Path,check=lambda n,v:v)
tree=ast.parse((ROOT/'app/core/models.py').read_text())
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and getattr(n,'name','')!='check']
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual-core','exec'),core.__dict__)
sys.modules['core']=types.ModuleType('core');sys.modules['core.models']=core
spec=importlib.util.spec_from_file_location('approved_stop',ROOT/'app/approved_stop.py')
guard=importlib.util.module_from_spec(spec);sys.modules['approved_stop']=guard;spec.loader.exec_module(guard)
domain=json.loads((ROOT/'app/fixtures/expense_review_usd/domain_v0.json').read_text())
cases=json.loads((ROOT/'app/fixtures/expense_review_usd/cases.json').read_text())
for rule in domain['rules']:rule['approved_by']='human:test'
arm='C_JT_RULES';case=cases[3]
raw=guard.decision(domain,case,case['initial_state'],arm)
ok('explicit changed-stay hold uses approved rules',raw and raw['outcome']=='HOLD' and raw['action_id']=='hold_case')
ok('positive/default-unknown cases still request the model',all(guard.decision(domain,c,c['initial_state'],arm) is None for c in cases[:3]))
ok('A and B study arms still request the model',all(guard.decision(domain,case,case['initial_state'],a) is None for a in ('A_SOURCE_ONLY','B_TEXT_ADDED')))
unapproved=copy.deepcopy(domain);unapproved['rules'][0]['approved_by']=None
ok('unapproved stop is never executed directly',guard.decision(unapproved,case,case['initial_state'],arm) is None)
unreferenced=copy.deepcopy(domain);unreferenced['rules'][0]['source_refs']=[]
ok('stop without evidence is never executed directly',guard.decision(unreferenced,case,case['initial_state'],arm) is None)
unknown=copy.deepcopy(case);unknown['facts']['receipt_stay_end']=None
ok('unknown condition is not treated as a matched stop',guard.decision(domain,unknown,unknown['initial_state'],arm) is None)
conflict=copy.deepcopy(domain);other=copy.deepcopy(conflict['rules'][0]);other.update(rule_id='conflict',action_id='ready_for_approval');conflict['rules'].append(other)
ok('conflicting rules do not become a direct stop',guard.decision(conflict,case,case['initial_state'],arm) is None)
renamed=copy.deepcopy(domain);renamed['default_action_id']='ask_person'
for action in renamed['actions']:
    if action['action_id']=='hold_case':action['action_id']='ask_person'
for rule in renamed['rules']:
    if rule['action_id']=='hold_case':rule['action_id']='ask_person'
ok('no expense-specific action name in guard',guard.decision(renamed,case,case['initial_state'],arm)['action_id']=='ask_person')

class Repo:
    def __init__(self):self.data={}
    def get(self,*key):return copy.deepcopy(self.data.get(key))
    def put(self,kind,key,value):self.data[(kind,key)]=copy.deepcopy(value)
    def atomic(self,keys,fn):
        values={k:copy.deepcopy(self.data.get(k)) for k in keys};result=fn(values)
        self.data.update(copy.deepcopy(values));return copy.deepcopy(result)
class Adapter:
    mode='LIVE'
    def __init__(self):self.calls=0
    def decide(self,*args):
        self.calls+=1
        raise core.JTError('MODEL_FAILED','explicit failing provider double',503)
config=types.SimpleNamespace(CODE_HASH='release135',SETTINGS={'call_limit_seconds':60,'attempts':2})
scope=dict(core.__dict__,dt=dt,time=time,uuid=uuid,config=config)
st=ast.parse((ROOT/'app/service.py').read_text())
exec(compile(ast.Module(body=[n for n in st.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))],type_ignores=[]),'actual-service','exec'),scope)
def service(c=case):
    repo=Repo();adapter=Adapter();s=scope['Service'](repo,None,adapter)
    repo.put('workspaces','ws',{'workspace_id':'ws','owner':'owner','version':0,'status':'READY','leases':{}})
    repo.put('runs','run',{'workspace_id':'ws','code_hash':config.CODE_HASH,'model_settings':copy.deepcopy(config.SETTINGS),'mode':'LIVE',
        'task_ids':['task'],'cancelled':False,'active_version':0,'domain':copy.deepcopy(domain),'domain_hash':core.digest(domain),
        'source_ids':['expense_sop'],'arm':arm,'human_text':''})
    repo.put('tasks','task',{'task_id':'task','case_id':c['case_id'],'repeat':0,'status':'PENDING','lease_until':0,'lease_token':None,
        'attempts':0,'state':copy.deepcopy(c['initial_state']),'step_index':0,'receipt_ids':[],'trace_ids':[]})
    repo.put('cases','ws-'+c['case_id'],c);repo.put('sources','ws-expense_sop',{'source_id':'expense_sop'})
    s.checked=[]
    s.source_check=lambda wid,ref:s.checked.append(copy.deepcopy(ref))
    return s,repo,adapter
ctx={'owner':'owner','operation':'step1','admin':True}
s,repo,adapter=service();result=s.step('run',ctx);task=repo.get('tasks','task');trace=repo.get('traces',task['trace_ids'][0])
ok('actual Service.step completes the approved hold without a provider call',adapter.calls==0 and task['status']=='COMPLETED' and task['state']=={'status':'HELD'})
ok('actual source validation remains on the direct path',s.checked==raw['source_refs'])
ok('rule-engine provenance has no invented model attempt',task['decision_origin']=='APPROVED_RULE' and trace['mode']=='RULE_ENGINE' and trace['purpose']=='approved_rule_hold' and trace['attempts']==[] and trace['result']==raw)
ok('one receipt retains the exact case and starting state',result['receipt']['case_hash']==core.digest(case) and result['receipt']['before_state']==case['initial_state'] and len(task['receipt_ids'])==1)
duplicate=s.step('run',ctx)
ok('replayed request returns the same receipt without extra execution',duplicate['duplicate'] and duplicate['receipt']==result['receipt'] and adapter.calls==0 and len(repo.get('tasks','task')['receipt_ids'])==1)
s,repo,adapter=service(cases[0]);r=s.step('run',ctx)
ok('provider failure remains technical FAILED, never a business hold',r['failed'] and repo.get('tasks','task')['status']=='FAILED' and not repo.get('tasks','task')['receipt_ids'] and adapter.calls==1)
s,repo,adapter=service();run=repo.get('runs','run');run['code_hash']='old';repo.put('runs','run',run)
rejects('saved run cannot execute under a changed package',lambda:s.step('run',ctx),'RUN_PROTOCOL_CHANGED')
ok('changed package does not call provider',adapter.calls==0)
s,repo,adapter=service();ws=repo.get('workspaces','ws');ws['status']='STALE';repo.put('workspaces','ws',ws)
rejects('stale workflow still blocks direct execution',lambda:s.step('run',ctx),'STALE')
s,repo,adapter=service()
def invalid(wid,ref):raise core.JTError('INVALID_INPUT','invalid evidence double')
s.source_check=invalid;r=s.step('run',ctx)
ok('invalid source evidence cannot commit a direct hold',r['failed'] and not repo.get('tasks','task')['receipt_ids'] and adapter.calls==0)
s,repo,adapter=service()
rejects('other owner cannot inspect or execute the run',lambda:s.step('run',{**ctx,'owner':'other'}),'NOT_FOUND')

scope2={};tree=ast.parse((ROOT/'app/expense_demo.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='recorded_decision_matches'],type_ignores=[]),'actual-publication-check','exec'),scope2)
matches=scope2['recorded_decision_matches']
s,repo,adapter=service();s.step('run',ctx);task=repo.get('tasks','task');run=repo.get('runs','run');trace=repo.get('traces',task['trace_ids'][0])
view={'run':run,'traces':[trace]}
ok('publisher independently recomputes direct approved hold',matches(view,task,case,'hold_case'))
tampered=copy.deepcopy(view);tampered['traces'][0]['result']['action_id']='ready_for_approval'
ok('publisher rejects a forged direct-rule result',not matches(tampered,task,case,'hold_case'))
tampered=copy.deepcopy(view);tampered['traces'][0]['attempts']=[{'status':'OK'}]
ok('publisher rejects fake provider attempts on a rule trace',not matches(tampered,task,case,'hold_case'))
ok('publisher cannot accept a positive result as direct hold',not matches(view,task,case,'ready_for_approval'))

# Actual attempt-ceiling wrapper, without executing its live setup functions.
sc={'Path':Path,'digest':core.digest,'time':time};tr=ast.parse((ROOT/'steps/approved_stop135.py').read_text())
exec(compile(ast.Module(body=[n for n in tr.body if isinstance(n,ast.ClassDef)],type_ignores=[]),'actual-bound','exec'),sc)
class API:
    used=22
    def __init__(self):self.requests=[]
    def call(self,path,data=None,**kw):
        if path=='/recovery115':return {'session':{'calls':100+self.used}}
        self.requests.append(path);return {}
api=API();bounded=sc['BoundedAPI'](api,types.SimpleNamespace(Stop=core.JTError),100)
bounded.call('/runs/x/step',{});api.used=23
rejects('original plus resumed attempts cannot exceed 24',lambda:bounded.call('/runs/x/step',{}),'USD_ATTEMPT_LIMIT')
ok('exhausted allowance makes no extra execution request',len(api.requests)==1)
bounded.call('/teachings',{});api.used=24
rejects('guidance also respects the original total ceiling',lambda:bounded.call('/teachings',{}),'USD_ATTEMPT_LIMIT')
bounded.call('/exports/x')
ok('read-only exports remain accessible at the ceiling',api.requests[-1]=='/exports/x')
report={'status':'PASSED','passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'scope':'Actual evaluator, executor, Service.step, publication guard and allowance wrapper; explicit schema, repository, evidence and provider doubles. Live zero-model check is packaged separately and has not been run here.'}
(ROOT/'verification/approved_stop135_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

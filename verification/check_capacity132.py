"""Bounded regression: case selection must fit without consuming AI or fixing cases."""
import ast, copy, datetime as dt, json, sys, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
import config
from core.models import JTError, digest
from service import Service

parsed=ast.parse((ROOT/'app/adapters/model.py').read_text())
scope={'dt':dt,'digest':digest,'config':config,'JTError':JTError}
exec(compile(ast.Module(body=[n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='Budget'],type_ignores=[]),'actual_budget_class','exec'),scope)
Budget=scope['Budget']

class Repository:
    def __init__(self):self.data={}
    def get(self,kind,key):return copy.deepcopy(self.data.get((kind,key)))
    def put(self,kind,key,value):self.data[kind,key]=copy.deepcopy(value)
    def atomic(self,keys,fn):
        values={k:copy.deepcopy(self.data.get(k)) for k in keys};result=fn(values)
        self.data.update({k:copy.deepcopy(v) for k,v in values.items() if v is not None})
        return copy.deepcopy(result)

checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def reject(name,fn,code):
    try:fn()
    except JTError as error:ok(name,error.code==code)
    else:raise AssertionError(name)

repo=Repository();owner='capacity-test-owner';ctx={'owner':owner,'admin':False,'operation':'capacity-create'}
adapter=types.SimpleNamespace(mode='LIVE',budget=Budget(repo));service=Service(repo,None,adapter)
domain=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text())
template=json.loads((ROOT/'app/fixtures/expense_review/cases.json').read_text())[0]
cases=[]
for i in range(40):
    case=copy.deepcopy(template);case.update(case_id='capacity_case_'+str(i),split='dev',stratum=('normal','transfer','must_hold')[i%3]);cases.append(case)
wid='capacity-workspace';workspace={'workspace_id':wid,'owner':owner,'version':0,'status':'READY','case_ids':[c['case_id'] for c in cases],
    'source_ids':[],'human_source_ids':[],'teaching_ids':[],'run_ids':[],'shared_trace_ids':[],'approved_count':0,'frozen':False,'leases':{}}
repo.put('workspaces',wid,workspace);repo.put('domains',wid+'-v0',{'domain':domain})
for case in cases:repo.put('cases',wid+'-'+case['case_id'],case)
body={'workspace_id':wid,'arm':'A_SOURCE_ONLY','reviewer_name':'Offline validation','plan_comparison':True}
snapshot=copy.deepcopy(repo.data);plan=service.plan_run(body,ctx)
ok('default selection is one routine, gap and hold case',plan['selected_case_ids']==[c['case_id'] for c in cases[:3]])
ok('pair includes six decisions, two question attempts and one guidance attempt',plan['required']=={'judgment_calls':6,'model_calls':9})
ok('preflight changes no stored record',repo.data==snapshot)
all_cases={**body,'case_ids':[c['case_id'] for c in cases]}
ok('forty imported cases cannot start an over-limit comparison',not service.plan_run(all_cases,ctx)['can_start'])
reject('server rejects over-limit create before task creation',lambda:service.create_run(all_cases,ctx),'RUN_CAPACITY')
ok('rejected run does not lock or create cases or budget records',repo.data==snapshot)
single={**all_cases,'plan_comparison':False}
reject('direct caller cannot bypass per-run allowance',lambda:service.create_run(single,ctx),'RUN_CAPACITY')
for bad in ([], 'capacity_case_0', [cases[0]['case_id']]*2, [None], [{'id':'x'}]):
    reject('invalid case selection '+repr(bad),lambda bad=bad:service.plan_run({**body,'case_ids':bad},ctx),'INVALID_INPUT')
reject('outside split selection rejected',lambda:service.plan_run({**body,'case_ids':['unknown']},ctx),'INVALID_INPUT')
reject('invalid pair option rejected',lambda:service.plan_run({**body,'plan_comparison':'true'},ctx),'INVALID_INPUT')
reject('other owner cannot inspect plan',lambda:service.plan_run(body,{**ctx,'owner':'other'}),'NOT_FOUND')
sk=('budget',digest(owner)[:40]);repo.put(*sk,{'decisions':7,'calls':10})
ok('existing session usage reduces selection allowance',not service.plan_run(body,ctx)['can_start'])
two={**body,'case_ids':[c['case_id'] for c in cases[:2]]}
ok('smaller selected pair fits remaining allowance',service.plan_run(two,ctx)['can_start'])
repo.put(*sk,{'decisions':0,'calls':18})
ok('preparation usage can prevent pair before decision limit',not service.plan_run(body,ctx)['can_start'])
repo.put(*sk,{'decisions':0,'calls':0})
repo.put('budget','global',{'day':dt.datetime.now(dt.timezone.utc).date().isoformat(),'decisions':598,'calls':1000,'spent_usd':1.0})
ok('daily judgment remainder also limits preflight',service.plan_run(body,ctx)['remaining']['judgment_calls']==2)
repo.put('budget','global',{'day':'2000-01-01','decisions':600,'calls':1000,'spent_usd':1.0})
ok('previous day usage does not consume today allowance',service.plan_run(body,ctx)['remaining']['judgment_calls']==12)
multi=copy.deepcopy(domain);multi['actions'][0]['terminal']=False;repo.put('domains',wid+'-v0',{'domain':multi})
one={**body,'case_ids':[cases[0]['case_id']]}
plan=service.plan_run(one,ctx)
ok('nonterminal action budgets eight steps per case in both runs',plan['max_steps_per_case']==8 and plan['required']=={'judgment_calls':16,'model_calls':19} and not plan['can_start'])
ok('one multistep standalone run can fit',service.plan_run({**one,'plan_comparison':False},ctx)['can_start'])
repo.put('domains',wid+'-v0',{'domain':domain});attempts=config.SETTINGS['attempts'];config.SETTINGS['attempts']=2
try:ok('configured retry attempts counted',service.plan_run(body,ctx)['required']=={'judgment_calls':12,'model_calls':15})
finally:config.SETTINGS['attempts']=attempts
created=service.create_run(two,ctx);rid=created['run_id']
ok('accepted run stores only explicitly chosen cases',repo.get('runs',rid)['case_ids']==two['case_ids'] and created['total']==2)
for tid in repo.get('runs',rid)['task_ids']:
    task=repo.get('tasks',tid);task['status']='COMPLETED';repo.put('tasks',tid,task)
w=repo.get('workspaces',wid);w['version']=1;w['approved_count']=1;repo.put('workspaces',wid,w)
new_domain=copy.deepcopy(domain);new_domain['version']=1;repo.put('domains',wid+'-v1',{'domain':new_domain})
after={'workspace_id':wid,'arm':'C_JT_RULES','baseline_run_id':rid,'reviewer_name':'Offline validation'}
ok('after selection comes from saved baseline',service.plan_run(after,ctx)['selected_case_ids']==two['case_ids'])
reject('after selection cannot silently add a case',lambda:service.plan_run({**after,'case_ids':body.get('case_ids',[c['case_id'] for c in cases[:3]])},ctx),'INVALID_INPUT')
reject('after selection cannot reorder cases',lambda:service.plan_run({**after,'case_ids':list(reversed(two['case_ids']))},ctx),'INVALID_INPUT')
reject('other owner cannot use saved baseline',lambda:service.plan_run(after,{**ctx,'owner':'other'}),'NOT_FOUND')
repo.put(*sk,{'decisions':12,'calls':24});saved=copy.deepcopy(repo.data)
ok('same successful creation remains readable after usage is exhausted',service.create_run(two,ctx)['run']['run_id']==rid)
ok('idempotent read creates no new tasks or counter changes',repo.data==saved)
ok('administrator retains existing run selection and controller allowance',service.plan_run(all_cases,{**ctx,'admin':True})['can_start'])
adapter.mode='MOCK';ok('explicit simulation does not claim live session allowance',service.plan_run(all_cases,ctx)['remaining'] is None)
adapter.mode='LIVE';repo.put(*sk,{'decisions':0,'calls':0})
repo.put(*sk,{'decisions':12,'calls':24})
reject('per-call atomic budget remains authoritative after a plan',lambda:adapter.budget.reserve(owner,False,'decide',1,1),'CALL_LIMIT')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'scope':'Actual service and run_capacity code plus actual AST-loaded Budget; isolated repository double. No cloud calls.'}
(ROOT/'verification/capacity132_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

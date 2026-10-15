"""Bounded actual service/controller/publisher flow with explicit storage/history/schema doubles."""
import ast,copy,datetime as dt,hashlib,importlib.util,json,math,shutil,sys,tempfile,time,types,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def rejects(name,fn,code):
    try:fn()
    except Exception as e:ok(name,getattr(e,'code',None)==code)
    else:raise AssertionError(name)
contract=json.loads((ROOT/'app/contracts/jt_contracts.schema.json').read_text())
def schema_double(name,value):
    if name=='Decision':
        schema=contract['$defs'][name]
        assert set(value)==set(schema['required'])
        assert value['outcome'] in schema['properties']['outcome']['enum']
    return value
core=types.ModuleType('core.models');core.__dict__.update(copy=copy,hashlib=hashlib,json=json,math=math,Path=Path,ROOT=ROOT/'app',check=schema_double)
tree=ast.parse((ROOT/'app/core/models.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name!='check'],type_ignores=[]),'actual-core','exec'),core.__dict__)
sys.modules['core']=types.ModuleType('core');sys.modules['core.models']=core
config=types.ModuleType('config');config.VERSION='1.0.38';config.CODE_HASH='engine138';config.SETTINGS={'attempts':2}
sys.modules['config']=config

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
engine=module('approved_execution',ROOT/'app/approved_execution.py')
comparison=module('comparison',ROOT/'app/comparison.py');capacity=module('run_capacity',ROOT/'app/run_capacity.py')
actor=lambda b:{'reviewer_name':b['reviewer_name'],'memo':b.get('memo','')}
def prepared(service,ws,ctx,body,kind,content,sources):
    key=('history',ctx['operation']);record={'record_id':ctx['operation'],'reviewer_name':body['reviewer_name'],'memo':body.get('memo','')}
    return key,record,lambda values:values.update({key:record})
sys.modules['history']=types.SimpleNamespace(actor=actor,prepared=prepared)
scope=dict(core.__dict__,config=config,dt=dt,time=time,uuid=uuid,ARMS=('A_SOURCE_ONLY','B_TEXT_ADDED','C_JT_RULES'))
tree=ast.parse((ROOT/'app/service.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))],type_ignores=[]),'actual-service','exec'),scope)
sys.modules['service']=types.SimpleNamespace(now=scope['now'])
sys.modules['case_intake']=types.SimpleNamespace(case_evidence=lambda *a:None)
publisher=module('expense_demo',ROOT/'app/expense_demo.py')
class Repo:
    def __init__(self):self.data={}
    def get(self,*key):return copy.deepcopy(self.data.get(key))
    def put(self,kind,key,value):self.data[(kind,key)]=copy.deepcopy(value)
    def atomic(self,keys,fn):
        values={k:self.get(*k) for k in keys};result=fn(values);self.data.update(copy.deepcopy(values));return copy.deepcopy(result)
class Adapter:
    mode='LIVE'
    def __init__(self):self.calls=0;self.budget=types.SimpleNamespace(public_allowance=lambda owner:{'judgment_calls':24,'model_calls':24})
    def decide(self,*a):self.calls+=1;raise core.JTError('MODEL_FAILED','Explicit failed-provider double',503)
fixture=ROOT/'app/fixtures/expense_review_usd';d0=json.loads((fixture/'domain_v0.json').read_text());cases=json.loads((fixture/'cases.json').read_text());labels=json.loads((fixture/'expected_private_to_scorer.json').read_text())
for rule in d0['rules']:rule['approved_by']='human:test'
d1=copy.deepcopy(d0);d1['version']=1
text='\n'.join((fixture/'expert_teaching_reference.txt').read_text().splitlines()[2:]);human_hash=core.digest(text.encode());d1['source_hashes']['human_source']=human_hash
ref={'source_id':'human_source','version_hash':human_hash,'locator':'human:1','quote':text.splitlines()[0]}
# Explicit test-only candidate; production reuses the actual saved Gemini proposal.
def cond(field,op='eq',value=None,rhs=None):return {'field_id':field,'operator':op,**({'rhs_field_id':rhs} if rhs else {'value':value})}
company=[cond('receipt_addressee_name',value='Cedarline Services'),cond('employee_payment_status',value='PAID')]
for rid,priority,when,action in [('company_amount',40,company+[cond('claimed_amount_usd','ne',rhs='employee_payment_amount_usd')],'return_for_correction'),('company_ready',80,company+[cond('claimant_name',rhs='receipt_guest_name'),cond('approved_stay_start',rhs='receipt_stay_start'),cond('approved_stay_end',rhs='receipt_stay_end'),cond('claimed_amount_usd',rhs='employee_payment_amount_usd')],'ready_for_approval')]:
    d1['rules'].append({'rule_id':rid,'priority':priority,'when':{'all':when,'any':[]},'action_id':action,'statement':rid,'source_refs':[ref],'approved_by':'human:test'})
for i,c in enumerate(cases):
    raw=engine.decision(d1,c,c['initial_state']);decision,state,terminal=core.execute(d1,c,c['initial_state'],raw)
    ok('engine/executor reaches reviewed target '+str(i+1),decision['action_id']==labels[i]['expected_action_id'] and state==labels[i]['expected_state'] and terminal)
for field,value in [('employee_payment_amount_usd',None),('employee_payment_status',None),('employee_payment_status','UNPAID'),('receipt_stay_end','2026-09-11')]:
    c=copy.deepcopy(cases[1]);c['facts'][field]=value
    ok('unsafe/missing '+field+' '+str(value)+' holds',engine.decision(d1,c,c['initial_state'])['outcome']=='HOLD')
u=copy.deepcopy(d1);u['rules'][0]['approved_by']=None
rejects('unapproved conditions do not execute',lambda:engine.decision(u,cases[0],cases[0]['initial_state']),'APPROVAL_REQUIRED')
u=copy.deepcopy(d1);u['rules'][0]['source_refs']=[]
rejects('missing evidence does not execute',lambda:engine.decision(u,cases[0],cases[0]['initial_state']),'APPROVAL_REQUIRED')
u=copy.deepcopy(d1);u['rules'][0]['source_refs'][0]['version_hash']='wrong'
rejects('source hash mismatch does not execute',lambda:engine.decision(u,cases[0],cases[0]['initial_state']),'INVALID_INPUT')
# Nonidentical overlapping conditions at the same priority must hold, not pick one.
u=copy.deepcopy(d0);rule=copy.deepcopy(u['rules'][-1]);rule.update(rule_id='conflicting',action_id='return_for_correction');rule['when']['all']=rule['when']['all'][:-1];u['rules'].append(rule)
ok('conflicting permissions hold without a fictitious match',engine.decision(u,cases[0],cases[0]['initial_state'])['rule_ids']==[] and engine.decision(u,cases[0],cases[0]['initial_state'])['outcome']=='HOLD')

# A different task, field and action proves that the execution path is declarative.
g=copy.deepcopy(d0);g.update(domain_id='room_check',rules=[],default_action_id='ask_owner')
g['input_fields']=[{'field_id':'door_locked','label':'Door locked','type':'boolean','description':'Verified sensor reading','required':True}]
g['state_fields']=[{'field_id':'stage','label':'Stage','type':'string','description':'Test state','required':True}]
g['actions']=[{'action_id':name,'label':name,'description':name,'effects':[{'field_id':'stage','value':state}],'terminal':True} for name,state in [('ask_owner','HELD'),('record_secure','SECURE')]]
g['rules']=[{'rule_id':'secure_door','priority':1,'when':{'all':[cond('door_locked',value=True)],'any':[]},'action_id':'record_secure','statement':'Record secure only when the door is confirmed locked.','source_refs':d0['rules'][0]['source_refs'],'approved_by':'human:test'}]
gc={'case_id':'room_01','domain_id':'room_check','split':'dev','stratum':'normal','facts':{'door_locked':True},'initial_state':{'stage':'NEW'}}
gr=engine.decision(g,gc,gc['initial_state'])
ok('unrelated task executes from its own declared fields and actions',core.execute(g,gc,gc['initial_state'],gr)[1]=={'stage':'SECURE'})

W='ws_50ff4e8beabbf2fbbc101163b5a9fc3a';ctx={'owner':'owner','admin':True,'operation':'test'}
def setup():
    repo=Repo();adapter=Adapter();s=scope['Service'](repo,None,adapter)
    ws={'workspace_id':W,'owner':'owner','status':'READY','version':1,'case_ids':[c['case_id'] for c in cases], 'source_ids':['expense_sop'],'human_source_ids':['human_source'],'teaching_ids':['teaching'],'question_ids':['question'],'shared_trace_ids':[],'approved_count':1,'run_ids':[],'leases':{},'frozen':False,'sample':None}
    repo.put('workspaces',W,ws)
    for d in (d0,d1):repo.put('domains',W+'-v'+str(d['version']),{'domain':d,'approved_at':'2026-10-15T00:00:00Z','reviewer_name':'Reviewer'})
    repo.put('sources',W+'-expense_sop',{'source_id':'expense_sop','version_hash':d0['source_hashes']['expense_sop']})
    repo.put('sources',W+'-human_source',{'source_id':'human_source','version_hash':human_hash})
    repo.put('teachings','teaching',{'workspace_id':W,'source_id':'human_source','teaching':{'teaching_id':'teaching','question_id':'question','human_text':text,'approval_state':'APPROVED'}})
    repo.put('questions','question',{'workspace_id':W,'question':{'question_id':'question','text':'How should company receipts be checked?'}})
    for c,l in zip(cases,labels):repo.put('cases',W+'-'+c['case_id'],c);repo.put('expected',W+'-'+c['case_id'],l)
    s.validated=[]
    def check_ref(wid,ref):
        s.validated.append(ref)
        if ref['quote']=='bad':raise core.JTError('INVALID_INPUT','Explicit invalid-quote evidence double')
    s.source_check=check_ref
    return s,repo,adapter
s,repo,adapter=setup()
body={'workspace_id':W,'arm':'C_JT_RULES','approved_version':0,'split':'dev','reviewer_name':'Reviewer'}
plan=s.plan_run({**body,'plan_comparison':True},{**ctx,'admin':False})
ok('ordinary comparison budgets four preparation attempts and zero execution generations',plan['required']=={'judgment_calls':0,'model_calls':4})
for value in (-1,2,True,'0'):
    rejects('invalid approved version '+str(value),lambda:s.create_run({**body,'approved_version':value},ctx),'INVALID_INPUT')
base=s.create_run(body,{**ctx,'operation':'base'})['run_id']
run=repo.get('runs',base)
ok('historical approved v0 replay excludes future human explanation and source',run['domain']['version']==0 and run['human_text']=='' and run['source_ids']==['expense_sop'] and run['shared_trace_ids']==[] and run['human_inputs']==0)
for i in range(4):s.step(base,{**ctx,'operation':'base-step'+str(i)})
v=s.run_view(base,ctx,True)
ok('actual four baseline executions have zero provider calls and real receipts',adapter.calls==0 and len(v['receipts'])==4 and all(t['status']=='COMPLETED' for t in v['tasks']))
duplicate=s.step(base,{**ctx,'operation':'base-step0'})
ok('idempotent step reuses its one receipt',duplicate.get('duplicate') and len(s.run_view(base,ctx,True)['receipts'])==4)
after=s.create_run({**body,'approved_version':1,'baseline_run_id':base},{**ctx,'operation':'after'})['run_id']
for i in range(4):s.step(after,{**ctx,'operation':'after-step'+str(i)})
va=s.run_view(after,ctx,True)
ok('actual same-engine comparison passes',comparison.compare(s,base,after,ctx)['comparable'])
ok('publisher recomputes actual engine trace for every after case',all(publisher.recorded_decision_matches(va,t,c,l['expected_action_id']) for t,c,l in zip(va['tasks'],cases,labels)))
bad=copy.deepcopy(va);bad['traces'][0]['attempts']=[{'status':'OK'}]
ok('fabricated model attempt rejected by engine evidence verifier',not publisher.recorded_decision_matches(bad,bad['tasks'][0],cases[0],labels[0]['expected_action_id']))
bad=repo.get('runs',base);bad.pop('execution_protocol');repo.put('runs',base,bad)
ok('mixed model/rule execution is not comparable',not comparison.compare(s,base,after,ctx)['comparable'])
bad['execution_protocol']=engine.PROTOCOL;repo.put('runs',base,bad)
# A/B still use the original provider path; a provider failure cannot become a successful business hold.
for arm in ('A_SOURCE_ONLY','B_TEXT_ADDED'):
    rid=s.create_run({'workspace_id':W,'arm':arm,'reviewer_name':'Reviewer','case_ids':[cases[0]['case_id']]},{**ctx,'operation':arm})['run_id']
    result=s.step(rid,{**ctx,'operation':arm+'-step'})
    task=s.run_view(rid,ctx)['tasks'][0]
    ok(arm+' technical failure is preserved without a receipt',result.get('failed') and task['status']=='FAILED' and not task['receipt_ids'])
ok('only the explicit A/B tests reached the failed-provider double',adapter.calls==2)
# Corrupt/changed evidence blocks execution with no receipt.
s2,r2,a2=setup();rid=s2.create_run(body,{**ctx,'operation':'bad-source'})['run_id'];source=r2.get('sources',W+'-expense_sop');source['version_hash']='changed';r2.put('sources',W+'-expense_sop',source)
res=s2.step(rid,{**ctx,'operation':'bad-source-step'})
ok('source change cannot commit a rule decision',res.get('failed') and not s2.run_view(rid,ctx,True)['receipts'] and a2.calls==0)

# Execute the actual release controller through actual Service methods, comparison and publisher.
steps=types.ModuleType('steps');steps.__path__=[str(ROOT/'steps')];sys.modules['steps']=steps
controller=module('steps.usd_demo138',ROOT/'steps/usd_demo138.py')
s,repo,adapter=setup();oldbase=controller.OLD_BASELINE;oldafter=controller.OLD_AFTER
ws=repo.get('workspaces',W);ws['run_ids']=[oldbase,oldafter];repo.put('workspaces',W,ws)
oldviews={oldbase:{'run':{'run_id':oldbase},'tasks':[{'status':'COMPLETED'}]*4},oldafter:{'run':{'run_id':oldafter},'tasks':[{'status':v} for v in ('COMPLETED','FAILED','PENDING','PENDING')]}}
usage={'session':{'calls':575},'budget':{'calls':575,'spent_usd':19.9433211,'decisions':38}}
class API:
    def __init__(self):self.posts=[]
    def call(self,path,data=None,key=None,files=None):
        c={**ctx,'operation':key or 'read'}
        if data is not None:self.posts.append(path)
        if path=='/health':return {'package_version':'1.0.38','code_hash':config.CODE_HASH,'mode':'LIVE'}
        if path=='/recovery115':return copy.deepcopy(usage)
        if path=='/workspaces/'+W:return {k:v for k,v in s.workspace(W,c).items()}|{'domain':s.domain(s.workspace(W,c))}
        if path=='/runs':return s.create_run(data,c)
        if path.startswith('/runs/') and path.endswith('/step'):return s.step(path.split('/')[2],c)
        if path.startswith('/exports/'):
            rid=path.split('/')[-1];return copy.deepcopy(oldviews[rid]) if rid in oldviews else s.run_view(rid,c,True)
        if path=='/workspaces/freeze':return s.freeze(data,c)
        if path=='/history/fix':return {'record_id':key,'reviewer_name':data['reviewer_name']}
        if path=='/demo/expense/publish':return publisher.publish(s,data,c)
        if path=='/demo/expense':return repo.get('public_demo','expense_usd134')
        raise AssertionError(path)
api=API()
with tempfile.TemporaryDirectory() as td:
    root=Path(td);shutil.copytree(fixture,root/'app/fixtures/expense_review_usd')
    def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    def load(path):return json.loads(path.read_text()) if path.exists() else {}
    save(root/'package-manifest.json',{'code_hash':config.CODE_HASH})
    old={'status':'FAILED','pending':'after-1','reviewer_name':'Reviewer','workspace_id':W,'baseline_run_id':oldbase,'after_run_id':oldafter,'steps':{'approve-teaching':{'domain':d1}}}
    oldpath=root/'.jt/upgrades/1.0.37/usd-demo.json';save(oldpath,old);original=oldpath.read_bytes()
    save(root/'.jt/upgrades/1.0.34/usd-demo.json',{'before':{'session':{'calls':559}}})
    r=types.SimpleNamespace(Stop=core.JTError,load=load,save=save,API=lambda **kw:api)
    result=controller.run(root,api,r,'Reviewer')
    ok('actual controller reaches publication with ten real service executions',result['status']=='PASSED' and result['report']['case_executions']==10 and adapter.calls==0)
    ok('prior checkpoints and failed/pending run are unchanged',oldpath.read_bytes()==original and api.call('/exports/'+oldafter)==oldviews[oldafter])
    ok('no source generation, question, teaching, approval or allowance POST',not any(p in ('/questions','/teachings','/sources','/domains/approve','/validation123/authorize') for p in api.posts))
    ok('published demo contains USD and honest zero-model execution provenance',api.call('/demo/expense')['currency']=='USD' and api.call('/demo/expense')['model_calls']==0 and api.call('/demo/expense')['execution_protocol']==engine.PROTOCOL)
    n=len(api.posts);controller.run(root,api,r,'Reviewer')
    ok('repeated controller run sends no new mutation',len(api.posts)==n)
    published=repo.get('public_demo','expense_usd134');pubbody={k+'_run_id':result[k+'_run_id'] for k in ('baseline','after','holdout')}|{'publish_fictional_usd_demo':True,'reviewer_name':'Reviewer'}
    tampered=repo.get('runs',result['after_run_id']);tampered['execution_protocol']='MODEL';repo.put('runs',result['after_run_id'],tampered)
    rejects('mixed execution publication is refused',lambda:publisher.publish(s,pubbody,ctx),'DEMO_RESULT_MISMATCH')
    ok('failed publication leaves the public snapshot unchanged',repo.get('public_demo','expense_usd134')==published)
report={'status':'PASSED','passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual engine, evaluator/executor, Service run creation/step/freeze, comparison, full release controller and publication. Explicit in-memory persistence, evidence-validator, schema and history doubles; candidate rules test-only. Live deployment remains pending.'}
(ROOT/'verification/approved_execution138_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

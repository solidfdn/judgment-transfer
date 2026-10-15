"""Real services and actual PDFs; all model and HTTP responses are explicit doubles."""
import contextlib,copy,importlib.util,io,json,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_intake128.py')}
exec(compile((ROOT/'verification/check_intake128.py').read_text().split('# Keep verbose controller output')[0],'existing-setup','exec'),ns)
R,Stop,m=ns['R'],ns['Stop'],ns['m'];baseAPI=ns['API'];setup=ns['setup']
from core.models import permitted,digest
from case_intake import confirm_case
from history import fix_result
spec=importlib.util.spec_from_file_location('baseline128',ROOT/'releases/jt_baseline_128.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
checks=[]
def ok(n,v=True):assert v,n;checks.append(n)
class API(baseAPI):
 def __init__(self,other):
  self.__dict__.update(other.__dict__);self.new_calls=0;self.decisions=0;self.payloads=[];self.bad_rules=False;self.fail_case=False
  self.svc.adapter.decide=self.decide;self.svc.adapter.propose_question=self.question;self.svc.adapter.draft_rules=self.teach
 def trace(self,purpose,result,payload):
  self.new_calls+=1;self.decisions+=int(purpose=='decide');self.payloads.append((purpose,copy.deepcopy(payload)))
  trace={'trace_id':'trace_baseline_double_'+str(self.new_calls),'mode':'TEST_DOUBLE','result':copy.deepcopy(result),'purpose':purpose,'attempts':[],'elapsed_ms':0}
  self.svc.repo.put('traces',trace['trace_id'],trace);return result,trace
 def decide(self,domain,case,state,arm,text,sources,owner,admin):
  if self.fail_case:
   self.fail_case=False;from core.models import JTError;raise JTError('MODEL_FAILED','explicit failed model double')
  action,rules,why=permitted(domain,{**case['facts'],**state})
  return self.trace('decide',{'case_id':case['case_id'],'outcome':'HOLD' if action=='hold' else 'PROPOSE','action_id':action,'rule_ids':rules,'source_refs':[],
    'missing_fields':[k for k,v in case['facts'].items() if v is None],'explanation':'TEST DOUBLE '+why},{'case':case,'domain':domain})
 def question(self,domain,failures,sources,owner,admin):
  return self.trace('propose_question',{'question_id':'question_double','text':'Which evidence and exceptions must still be checked?',
   'affected_dev_case_ids':[f['case_id'] for f in failures],'missing_field_ids':[],'source_refs':[],'why_needed':'TEST DOUBLE'}, {'failures':failures})
 def teach(self,domain,question,text,source,owner,admin):
  rules=[]
  for name in ('amount_mismatch','precheck_complete'):
   rule=copy.deepcopy(next(x for x in domain['rules'] if x['rule_id']==name));rule['rule_id']='company_'+name
   for c in rule['when']['all']:
    if c['field_id']=='receipt_addressed_to':c.pop('rhs_field_id');c['value']='Cedarline Services'
   rule['source_refs']=[{'source_id':source['source_id'],'version_hash':source['version_hash'],'locator':'human:1','quote':text}]
   rule['approved_by']=None;rules.append(rule)
  if self.bad_rules:rules=rules[:1]
  return self.trace('draft_rules',{'rules':rules},{'domain':domain,'question':question,'human_text':text})
 def call(self,path,data=None,key=None,files=None):
  if path=='/recovery115':
   n=len(self.adapter.calls)+self.new_calls
   return {'session':{'calls':516+n,'decisions':498+self.decisions},'budget':{'calls':516+n,'day':'2026-10-15','decisions':self.decisions,'spent_usd':17.1859638+n*.01},
    'study':{'phase':'COMPLETE','historical':'unchanged'},'additional_decisions_used':self.decisions,'extra_retry_attempts':{'used':0,'limit':6}}
  if path.startswith('/exports/'):return self.svc.run_view(path.split('/')[-1],self.ctx,True)
  if path.startswith('/runs/') and data is None:return self.svc.run_view(path.split('/')[-1],self.ctx)
  if data is None or path in ('/cases/read','/domains/draft','/domains/approve'):return super().call(path,data,key,files)
  if key in self.cache:return copy.deepcopy(self.cache[key])
  self.ctx['operation']=key;self.posts.append((path,copy.deepcopy(data)))
  if path=='/cases/confirm':value=confirm_case(self.svc,data,self.ctx)
  elif path=='/cases/import':value=self.svc.import_cases(data,self.ctx)
  elif path=='/runs':value=self.svc.create_run(data,self.ctx)
  elif path.endswith('/step'):value=self.svc.step(path.split('/')[2],self.ctx)
  elif path=='/history/fix':value=fix_result(self.svc,data,self.ctx)
  elif path=='/questions':value=self.svc.question(data,self.ctx)
  elif path=='/teachings':value=self.svc.teach(data,self.ctx)
  else:raise AssertionError('unexpected '+path)
  self.cache[key]=copy.deepcopy(value)
  if self.lose==path:self.lose=None;raise Stop('NETWORK_INTERRUPTED','lost response double')
  return value

def ready(folder):
 root,original=setup(folder)
 intake=m.run(original,root,R,'Offline Reviewer',True)
 R.save(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json',intake)
 b.TRACES=[x['trace_id'] for x in intake['readings']];b.APPROVED_DRAFT=intake['approved_draft_id']
 return root,API(original),intake
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api,intake=ready(f);before=len(api.posts);result=b.run(api,root,R,'Offline Reviewer',True,True)
  ok('six real case confirmations retain PDF evidence',len(api.svc.workspace(m.WORKSPACE,api.ctx)['case_ids'])==6 and len(api.svc.run_view(result['run_id'],api.ctx,True)['case_evidence'])==4)
  ok('four baseline decisions, one question and one draft only',result['status']=='TEACHING_DRAFT_READY_FOR_REVIEW' and api.new_calls==6 and api.decisions==4)
  ok('one ready and three held under current rules',[x['action'] for x in result['baseline_results']]==['ready_for_business_approval','hold','hold','hold'])
  ok('candidate passes four dev cases and five exception checks',len(result['candidate_checks'])==9 and all(x['expected_action']==x['permitted_action'] for x in result['candidate_checks']))
  ws=api.svc.workspace(m.WORKSPACE,api.ctx)
  ok('no new teaching approval, freeze or holdout run',ws['version']==0 and ws['approved_count']==0 and not ws['frozen'] and len(ws['run_ids'])==1)
  ok('private labels attached without replacing verified values',all(api.svc.case(m.WORKSPACE,d['case_id'])['facts']==d['transcription'] for d in m.DOCS))
  ok('held-out identities absent from all new model payloads',all(d['case_id'] not in json.dumps(api.payloads) for d in m.DOCS[4:]))
  ok('private target labels never enter model payloads','expected_action_id' not in json.dumps(api.payloads) and b.LABEL_NOTE not in json.dumps(api.payloads))
  ok('named immutable baseline FIX exists',any(api.svc.repo.get('history',i)['kind']=='test_result' and api.svc.repo.get('history',i)['reviewer_name']=='Offline Reviewer' for i in ws['history_ids']))
  count=len(api.posts);b.run(api,root,R,'Offline Reviewer',True,True);ok('completed restart no writes',len(api.posts)==count)
 for lost in ('/cases/confirm','/runs','STEP','/teachings'):
  with tempfile.TemporaryDirectory() as f:
   root,api,intake=ready(f)
   if lost=='STEP':
    oldcall=api.call
    def drop(path,*args,**kwargs):
     if path.endswith('/step') and not getattr(api,'lost_step',False):api.lose=path;api.lost_step=True
     return oldcall(path,*args,**kwargs)
    api.call=drop
   else:api.lose=lost
   try:b.run(api,root,R,'Offline Reviewer',True,True)
   except Stop as e:ok('pause lost '+lost,e.code=='BASELINE_PENDING')
   else:raise AssertionError('not paused')
   result=b.run(api,root,R,'Offline Reviewer',True,True)
   ok('reuse receipt '+lost,api.new_calls==6 and api.decisions==4 and result['status']=='TEACHING_DRAFT_READY_FOR_REVIEW')
 with tempfile.TemporaryDirectory() as f:
  root,api,intake=ready(f);api.bad_rules=True
  try:b.run(api,root,R,'Offline Reviewer',True,True)
  except Stop as e:ok('ineffective supplement stops unapproved',e.code=='BASELINE_GATE_FAILED' and api.svc.workspace(m.WORKSPACE,api.ctx)['version']==0)
 with tempfile.TemporaryDirectory() as f:
  root,api,intake=ready(f);api.fail_case=True
  try:b.run(api,root,R,'Offline Reviewer',True,True)
  except Stop as e:ok('failed baseline case prevents question and teaching',e.code=='BASELINE_GATE_FAILED' and api.new_calls==0)
  count=len(api.posts)
  try:b.run(api,root,R,'Offline Reviewer',True,True)
  except Stop:ok('failed restart no new writes',len(api.posts)==count)
 with tempfile.TemporaryDirectory() as f:
  root,api,intake=ready(f);count=len(api.posts)
  try:b.run(api,root,R,'Offline Reviewer',False,True)
  except Stop as e:ok('case confirmation requires explicit review',e.code=='REVIEW_REQUIRED' and len(api.posts)==count)
result={'passed':True,'checks':checks,'real_model_calls':0,'cloud_writes':0,'scope':'Actual services and PDF evidence, explicit generated decision/question/teaching doubles; identity pins substituted only for offline tests.'}
(ROOT/'verification/baseline128_offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'real_model_calls':0}))

"""Run the recovery controller on real local services with an explicit failed-generation double."""
import contextlib,copy,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_baseline128.py')}
exec(compile((ROOT/'verification/check_baseline128.py').read_text().split('with contextlib.redirect_stdout(io.StringIO()):')[0],'baseline-test-setup','exec'),ns)
R,Stop,ready,baseline=ns['R'],ns['Stop'],ns['ready'],ns['b']
from core.models import JTError,digest
from teaching_evidence import recover_teaching
spec=importlib.util.spec_from_file_location('controller130',ROOT/'steps/recover_teaching130.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def setup(folder):
 root,api,intake=ready(folder);original=api.teach
 def fail_quote(domain,question,text,source,owner,admin):
  result,trace=original(domain,question,text,source,owner,admin)
  for rule,line in zip(result['rules'],[2,1]):rule['source_refs'][0].update(locator='line:'+str(line),quote=text.splitlines()[line-1])
  trace.update(mode='LIVE',result=copy.deepcopy(result),source_hashes={source['source_id']:source['version_hash']},attempts=[{'status':'OK'}],payload={'domain':domain,'question':question,'human_text':text})
  api.svc.repo.put('traces',trace['trace_id'],trace);api.failed_trace=trace
  raise JTError('INVALID_INPUT','Explicit pre-fix citation failure')
 api.svc.adapter.draft_rules=fail_quote;original_call=api.call
 def call(path,data=None,key=None,files=None):
  if path=='/teachings':key='baseline129-teaching-draft'
  try:return original_call(path,data,key,files)
  except JTError as e:
   error=Stop('APP_REQUEST_FAILED',str(e));error.detail={'request_id':'req_recover130_test'};raise error
 api.call=call
 try:baseline.run(api,root,R,'Offline Reviewer',True,True)
 except Stop as e:assert e.code=='BASELINE_GATE_FAILED'
 old=R.load(root/'.jt/upgrades/1.0.28/baseline-teaching.json');R.save(root/'.jt/upgrades/1.0.29/baseline-teaching.json',old)
 c.RUN=old['run_id'];c.QUESTION=old['question']['question_id'];c.TRACE=api.failed_trace['trace_id'];c.REQUEST='req_recover130_test'
 error={'code':'INVALID_INPUT','request_id':c.REQUEST};api.svc.repo.put('requests',digest([api.ctx['owner'],'/api/v1/teachings','baseline129-teaching-draft']),{'result':{'error':error}})
 R.save(root/'deliverables/release129/teaching-inspection/diagnostic.json',{'trace_id':c.TRACE});R.save(root/'deliverables/release129/teaching-inspection/saved-trace.json',api.failed_trace)
 policy=root/'app/web/samples/expense_policy.txt';policy.parent.mkdir(parents=True,exist_ok=True);policy.write_bytes((ROOT/'app/web/samples/expense_policy.txt').read_bytes())
 R.save(root/'package-manifest.json',{'code_hash':'offline-controller-test'})
 previous_call=api.call;api.recovery_posts=0
 def recover_call(path,data=None,key=None,files=None):
  if path=='/health':return {'package_version':'1.0.30','code_hash':'offline-controller-test','mode':'LIVE','max_cost_usd':100}
  if path=='/teachings/recover':
   api.recovery_posts+=1;api.ctx['operation']=key
   value=recover_teaching(api.svc,data,api.ctx)
   if getattr(api,'lose_recovery',False):api.lose_recovery=False;raise Stop('NETWORK_INTERRUPTED','response lost')
   return value
  return previous_call(path,data,key,files)
 api.call=recover_call
 def forbidden(*a,**kw):raise AssertionError('Recovery must not generate')
 api.svc.adapter.draft_rules=forbidden
 return root,api,old
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api,old=setup(f);before=api.new_calls;oldbytes=(root/'.jt/upgrades/1.0.29/baseline-teaching.json').read_bytes()
  result=c.run(api,root,R,'Offline Reviewer')
  ok('controller reaches an unapproved recovered draft without new calls',result['status']=='TEACHING_DRAFT_READY_FOR_REVIEW' and api.new_calls==before and result['new_model_calls']==0)
  ok('all four cases and five boundaries checked before save',len(result['candidate_checks'])==9 and all(x['expected_action']==x['permitted_action'] for x in result['candidate_checks']))
  ok('prior checkpoint byte preserved',(root/'.jt/upgrades/1.0.29/baseline-teaching.json').read_bytes()==oldbytes)
  count=api.recovery_posts;c.run(api,root,R,'Offline Reviewer');ok('terminal rerun adds no write',api.recovery_posts==count)
 with tempfile.TemporaryDirectory() as f:
  root,api,old=setup(f);api.lose_recovery=True
  try:c.run(api,root,R,'Offline Reviewer')
  except Stop as e:assert e.code=='NETWORK_INTERRUPTED'
  result=c.run(api,root,R,'Offline Reviewer')
  ok('lost response resumes one saved draft',len(api.svc.workspace(c.WORKSPACE,api.ctx)['teaching_ids'])==1)
 with tempfile.TemporaryDirectory() as f:
  root,api,old=setup(f)
  try:c.run(api,root,R,'Different Reviewer')
  except Stop as e:ok('wrong checkpoint reviewer stops before writing',e.code=='SAVED_ANSWER_MISMATCH' and api.recovery_posts==0)
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Real local services, model failure and HTTP doubles; identity pins substituted only in test.'}
(ROOT/'verification/recover130_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

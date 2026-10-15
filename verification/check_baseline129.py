"""Preserve failed protocol, reuse confirmed facts, create a distinct new run."""
import contextlib,copy,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_baseline128.py')}
exec(compile((ROOT/'verification/check_baseline128.py').read_text().split('with contextlib.redirect_stdout(io.StringIO()):')[0],'baseline-double-setup','exec'),ns)
R,Stop,ready,old=ns['R'],ns['Stop'],ns['ready'],ns['b']
import config
from core.models import JTError
spec=importlib.util.spec_from_file_location('baseline129',ROOT/'steps/baseline129.py');new=importlib.util.module_from_spec(spec);spec.loader.exec_module(new)
checks=[]
def ok(n,v=True):assert v,n;checks.append(n)
def setup(folder):
 root,api,intake=ready(folder);new.TRACES=old.TRACES;new.APPROVED_DRAFT=old.APPROVED_DRAFT
 decide=api.decide
 def fail_third(domain,case,*args):
  if case['case_id'].endswith('dev_03'):
   api.new_calls+=2;api.decisions+=2
   trace={'trace_id':new.FAILED_TRACE,'mode':'TEST_DOUBLE','purpose':'decide','elapsed_ms':20051,'attempts':[
     {'status':'FAILED','chunk_count':0,'local_first_text_deadline_reached':True},
     {'status':'FAILED','chunk_count':0,'local_total_deadline_reached':True}],'error':'MODEL_FAILED'}
   api.svc.repo.put('traces',new.FAILED_TRACE,trace);e=JTError('MODEL_FAILED','Explicit time-limit double');e.trace=trace;raise e
  return decide(domain,case,*args)
 api.svc.adapter.decide=fail_third
 config.CODE_HASH=new.OLD_CODE_HASH
 try:old.run(api,root,R,'Offline Reviewer',True,True)
 except Stop as e:assert e.code=='BASELINE_GATE_FAILED'
 else:raise AssertionError('failed run missing')
 prior=R.load(root/'.jt/upgrades/1.0.28/baseline-teaching.json');new.OLD_RUN=prior['run_id']
 api.svc.adapter.decide=decide;config.CODE_HASH=new.helper().CODE_HASH
 basecall=api.call
 def call(path,*args,**kwargs):
  if path=='/health':return {'package_version':'1.0.29','code_hash':new.helper().CODE_HASH,'mode':'LIVE','max_cost_usd':100}
  return basecall(path,*args,**kwargs)
 api.call=call
 return root,api,intake,prior
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api,intake,prior=setup(f);before=len(api.posts);original=(root/'.jt/upgrades/1.0.28/baseline-teaching.json').read_bytes()
  result=new.run(api,root,R,'Offline Reviewer',True,True)
  ok('six previous confirmations reused without new confirmation or import',not any(path in ('/cases/confirm','/cases/import') for path,_ in api.posts[before:]))
  ok('new baseline contains four cases and four new decision calls',result['status']=='TEACHING_DRAFT_READY_FOR_REVIEW' and result['judgment_calls']==4 and result['model_calls']==6)
  ok('old run and new run remain separate',len(api.svc.workspace(new.helper().WORKSPACE,api.ctx)['run_ids'])==2 and result['run_id']!=prior['run_id'])
  oldview=api.svc.run_view(prior['run_id'],api.ctx,True)
  ok('old successful failed and pending records preserved',[t['status'] for t in oldview['tasks']]==['COMPLETED','COMPLETED','FAILED','PENDING'])
  ok('old checkpoint byte preserved',(root/'.jt/upgrades/1.0.28/baseline-teaching.json').read_bytes()==original)
  ok('new protocol records sixty seconds and one attempt',api.svc.run_view(result['run_id'],api.ctx)['run']['model_settings']['model_window_seconds']==60 and api.svc.run_view(result['run_id'],api.ctx)['run']['model_settings']['attempts']==1)
  count=len(api.posts);new.run(api,root,R,'Offline Reviewer',True,True);ok('finished restart no additional writes',len(api.posts)==count)
 with tempfile.TemporaryDirectory() as f:
  root,api,intake,prior=setup(f);api.lose='/runs'
  try:new.run(api,root,R,'Offline Reviewer',True,True)
  except Stop as e:ok('lost new-run response pauses',e.code=='BASELINE_PENDING')
  result=new.run(api,root,R,'Offline Reviewer',True,True)
  ok('lost new-run response resumes same run',result['judgment_calls']==4 and len(api.svc.workspace(new.helper().WORKSPACE,api.ctx)['run_ids'])==2)
 with tempfile.TemporaryDirectory() as f:
  root,api,intake,prior=setup(f);trace=api.svc.repo.get('traces',new.FAILED_TRACE);trace['attempts'][0]['local_first_text_deadline_reached']=False;api.svc.repo.put('traces',new.FAILED_TRACE,trace);count=len(api.posts)
  try:new.run(api,root,R,'Offline Reviewer',True,True)
  except Stop as e:ok('different failure refuses new model work',e.code=='PREVIOUS_FAILURE_CHANGED' and len(api.posts)==count)
result={'passed':True,'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Real service and PDF provenance, explicit model/HTTP doubles and substituted test identity pins.'}
(ROOT/'verification/baseline129_offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'new_model_calls':0}))

"""Bounded approval/after/holdout controller test using real local services."""
import contextlib,copy,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_recover130.py')}
exec(compile((ROOT/'verification/check_recover130.py').read_text().split('\nwith contextlib.redirect_stdout(io.StringIO()):')[0],'recovery-setup','exec'),ns)
R,Stop,setup,recover_controller=ns['R'],ns['Stop'],ns['setup'],ns['c']
from core.models import digest,JTError
from history import fix_result
import config
spec=importlib.util.spec_from_file_location('compare130',ROOT/'releases/jt_compare_130.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def prepared(folder):
 root,api,old=setup(folder);recovery=recover_controller.run(api,root,R,'Offline Reviewer')
 c.TEACHING=recovery['teaching_id'];c.BASELINE=recovery['run_id'];c.RULES_HASH=digest(recovery['proposed_rules'])
 before=api.svc.run_view(c.BASELINE,api.ctx,True);c.BASE_CODE=before['run']['code_hash'];c.CODE_HASH='comparison-current-test';config.CODE_HASH=c.CODE_HASH
 oldcall=api.call
 def call(path,data=None,key=None,files=None):
  if path=='/health':return {'package_version':'1.0.30','code_hash':c.CODE_HASH,'mode':'LIVE','max_cost_usd':100}
  if path.endswith('/approve') or path=='/workspaces/freeze':
   if key in api.cache:return copy.deepcopy(api.cache[key])
   api.ctx['operation']=key;api.posts.append((path,copy.deepcopy(data)))
   value=api.svc.freeze(data,api.ctx) if path=='/workspaces/freeze' else api.svc.approve_teaching(c.TEACHING,data,api.ctx)
   api.cache[key]=copy.deepcopy(value)
   if api.lose==path:api.lose=None;raise Stop('NETWORK_INTERRUPTED','response lost')
   return value
  try:return oldcall(path,data,key,files)
  except JTError as e:raise Stop(e.code,str(e)) from e
 api.call=call
 return root,api,before
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api,before=prepared(f);count=api.new_calls;result=c.run(api,root,R,'Offline Reviewer',True)
  ok('exactly six decisions with no rereading or generation',result['status']=='PASSED' and result['model_calls']==result['judgment_calls']==6 and api.new_calls-count==6)
  ok('named approval and version one',api.svc.workspace(c.WORKSPACE,api.ctx)['version']==1 and api.svc.workspace(c.WORKSPACE,api.ctx)['approved_count']==1)
  ok('same four development cases compared',len(result['report']['dev_changes'])==4 and result['report']['dev_changes'][1]['before_action']=='hold' and result['report']['dev_changes'][1]['after_action']=='ready_for_business_approval')
  ok('two first-use holdouts ready and correction',[x['action'] for x in result['holdout_results']]==['ready_for_business_approval','return_for_correction'])
  ok('original baseline immutable despite dynamic export metadata',c.immutable(api.svc.run_view(c.BASELINE,api.ctx,True))==c.immutable(before))
  ok('both package hashes disclosed',result['report']['baseline_code_hash']!=result['report']['after_code_hash'])
  ws=api.svc.workspace(c.WORKSPACE,api.ctx);records=[api.svc.repo.get('history',rid) for rid in ws['history_ids']]
  ok('named approval freeze and two result histories',sum(r['kind']=='test_result' for r in records)==3 and any(r['kind']=='evaluation_lock' for r in records) and any(r['kind']=='teaching_approval' for r in records) and all(r['reviewer_name']=='Offline Reviewer' for r in records))
  n=len(api.posts);c.run(api,root,R,'Offline Reviewer',True);ok('terminal rerun adds no write or call',len(api.posts)==n and api.new_calls-count==6)
 for lost in ('approve','/workspaces/freeze','/runs','step'):
  with tempfile.TemporaryDirectory() as f:
   root,api,before=prepared(f);count=api.new_calls
   if lost in ('approve','/workspaces/freeze'):api.lose='/teachings/'+c.TEACHING+'/approve' if lost=='approve' else lost
   elif lost=='/runs':api.lose=lost
   else:
    previous=api.call
    def lose_step(path,*args,**kw):
     if path.endswith('/step') and not getattr(api,'lost_step',False):api.lose=path;api.lost_step=True
     return previous(path,*args,**kw)
    api.call=lose_step
   try:c.run(api,root,R,'Offline Reviewer',True)
   except Stop as e:ok('pause on lost '+lost,e.code=='COMPARISON_PENDING')
   else:raise AssertionError('missing pause '+lost)
   result=c.run(api,root,R,'Offline Reviewer',True)
   ok('resume same writes and six decisions '+lost,result['model_calls']==6 and api.new_calls-count==6)
 with tempfile.TemporaryDirectory() as f:
  root,api,before=prepared(f);api.fail_case=True;count=api.new_calls
  try:c.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('real failed task stops before freeze',e.code=='COMPARISON_GATE_FAILED' and not api.svc.workspace(c.WORKSPACE,api.ctx)['frozen'])
  else:raise AssertionError('failure accepted')
  n=api.new_calls
  try:c.run(api,root,R,'Offline Reviewer',True)
  except Stop:pass
  ok('failed result never automatically reruns',api.new_calls==n)
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Real local approval, run, freeze and history services with explicit decision/API doubles; identity pins substituted only in test.'}
(ROOT/'verification/compare130_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

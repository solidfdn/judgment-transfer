"""Reproduce Cloud Shell standard vs deployed Priority without any cloud call."""
import contextlib,copy,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_compare130.py')}
exec(compile((ROOT/'verification/check_compare130.py').read_text().split('\nwith contextlib.redirect_stdout(io.StringIO()):')[0],'compare-service-setup','exec'),ns)
R,Stop,prepared,c,config=ns['R'],ns['Stop'],ns['prepared'],ns['c'],ns['config']
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def deployed(folder):
 root,api,before=prepared(folder);assert config.SETTINGS['request_tier']=='standard'
 oldrun=api.svc.repo.get('runs',c.BASELINE);oldrun['model_settings']={**oldrun['model_settings'],'request_tier':'priority'};api.svc.repo.put('runs',c.BASELINE,oldrun)
 call=api.call
 def priority_api(path,data=None,key=None,files=None):
  if path=='/health':return {'package_version':'1.0.30','code_hash':c.CODE_HASH,'mode':'LIVE','max_cost_usd':100,'request_tier':'priority'}
  settings=config.SETTINGS
  try:
   config.SETTINGS={**settings,'request_tier':'priority'}
   return call(path,data,key,files)
  finally:config.SETTINGS=settings
 api.call=priority_api;return root,api
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api=deployed(f);before=api.new_calls;result=c.run(api,root,R,'Offline Reviewer',True)
  ok('local standard does not reject recorded Priority',result['status']=='PASSED' and config.SETTINGS['request_tier']=='standard')
  ok('after and holdout run under deployed Priority',all(api.svc.repo.get('runs',result[k])['model_settings']['request_tier']=='priority' for k in ('after_run_id','holdout_run_id')))
  ok('six intended calls only',api.new_calls-before==6 and result['model_calls']==6)
 with tempfile.TemporaryDirectory() as f:
  root,api=deployed(f);saved=api.svc.repo.get('runs',c.BASELINE);saved['model_settings']['model_window_seconds']=20;api.svc.repo.put('runs',c.BASELINE,saved);count=len(api.posts)
  try:c.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('real protocol change still stops before approval',e.code=='BASELINE_CHANGED' and len(api.posts)==count)
  else:raise AssertionError('protocol mismatch accepted')
  ok('mismatch details saved without another diagnosis call',(root/'deliverables/release130/comparison/baseline-preflight-mismatch.json').is_file())
 with tempfile.TemporaryDirectory() as f:
  root,api=deployed(f);call=api.call
  def wrong_tier(path,*args,**kw):
   value=call(path,*args,**kw)
   if path=='/health':value['request_tier']='standard'
   return value
  api.call=wrong_tier;count=len(api.posts)
  try:c.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('deployed standard is refused',e.code=='DEPLOY_MISMATCH' and len(api.posts)==count)
  else:raise AssertionError('wrong tier accepted')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual controller/local services with separate simulated server settings and fixed original records. No LIVE result claimed.'}
(ROOT/'verification/compare130_environment_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

"""Regression for observed explicit absence; no LIVE model/cloud operations."""
import contextlib,copy,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Reuse the existing real service/PDF setup without rerunning its scenario suite.
ns={'__file__':str(ROOT/'verification/check_intake128.py')}
src=(ROOT/'verification/check_intake128.py').read_text().split('# Keep verbose controller output')[0]
exec(compile(src,'existing-intake-test-setup','exec'),ns)
m,setup,R,Stop=ns['m'],ns['setup'],ns['R'],ns['Stop']
spec=importlib.util.spec_from_file_location('resume128',ROOT/'releases/jt_resume_intake_128.py');resume=importlib.util.module_from_spec(spec);spec.loader.exec_module(resume)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def failed(root,api):
 original=api.adapter.invoke
 def observed(*args,**kwargs):
  answer,trace=original(*args,**kwargs)
  for o in answer['observations']:
   if o['value'] is None:o['status']='OBSERVED'
  return answer,trace
 api.adapter.invoke=observed
 try:m.run(api,root,R,'Offline Reviewer',True)
 except Stop as e:assert e.code=='CASE_READ_GATE_FAILED'
 else:raise AssertionError('Original defect not reproduced')
 p=R.load(root/resume.OLD_CHECKPOINT)
 assert len(p['readings'])==3 and len(api.adapter.calls)==3
 # Identity pins are replaced ONLY for this explicit local test double.
 resume.TRACES=[x['trace_id'] for x in p['readings']];resume.APPROVED_DRAFT=p['approved_draft_id']
 return p
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as folder:
  root,api=setup(folder);old=failed(root,api);before=(root/resume.OLD_CHECKPOINT).read_bytes();post_count=len(api.posts)
  ok('original gate incorrectly rejects grounded observed null',old['case_previews'][2]['review_issues'] and all(x['value'] is None and x['status']=='OBSERVED' for x in old['readings'][2]['observations'] if x['field_id'] in resume.ABSENCE))
  result=resume.run(api,root,R,'Offline Reviewer')
  ok('remaining three actual PDFs use real service and references with extraction doubles',result['status']=='READINGS_READY_FOR_REVIEW' and result['resumed_model_calls']==3 and len(api.adapter.calls)==6)
  ok('original failed checkpoint byte preserved',(root/resume.OLD_CHECKPOINT).read_bytes()==before)
  ok('original raw model status and null preserved',result['readings'][:3]==old['readings'])
  ok('only three new case-read calls, no repeated approval or confirmation',[x[0] for x in api.posts[post_count:]]==['/cases/read']*3)
  ok('both absence interpretations separately recorded',len(result['absence_interpretations'][m.DOCS[2]['case_id']])==2)
  count=len(api.posts);resume.run(api,root,R,'Offline Reviewer');ok('completed reentry no new posts',len(api.posts)==count)
  pdf=m.files(root,R)[m.DOCS[2]['case_id']];answer=old['readings'][2];doc=m.DOCS[2];domain=old['approved_domain']
  for name,alter in [('invented absence quote',lambda o:o['source_refs'][0].update(quote='Employee card payment status: Not stated invented')),
    ('wrong source',lambda o:o['source_refs'][0].update(source_id='different')),
    ('total settlement substituted',lambda o:o['source_refs'][0].update(quote='Total settlement status: PAID')),
    ('amount filled despite absence',lambda o:o.update(value=31200)),
    ('wrong page',lambda o:o['source_refs'][0].update(locator='page:1'))]:
   bad=copy.deepcopy(answer);target=next(o for o in bad['observations'] if o['field_id']=='receipt_payment_status');alter(target)
   issues,notes=resume.validate_absence(bad,doc,domain,pdf,m.read_issues)
   ok('reject '+name,bool(issues))
 with tempfile.TemporaryDirectory() as folder:
  root,api=setup(folder);old=failed(root,api);api.lose='/cases/read'
  try:resume.run(api,root,R,'Offline Reviewer')
  except Stop as e:ok('lost fourth response pauses',e.code=='INTAKE_PENDING')
  else:raise AssertionError('missing pause')
  result=resume.run(api,root,R,'Offline Reviewer');ok('resume saved fourth receipt without regeneration',len(api.adapter.calls)==6 and result['resumed_model_calls']==3)
 with tempfile.TemporaryDirectory() as folder:
  root,api=setup(folder);old=failed(root,api);old['error']['code']='MODEL_FAILED';R.save(root/resume.OLD_CHECKPOINT,old);before=len(api.posts)
  try:resume.run(api,root,R,'Offline Reviewer')
  except Stop as e:ok('different failure cannot be resumed',e.code=='SAVED_RESULT_CHANGED' and len(api.posts)==before)
 with tempfile.TemporaryDirectory() as folder:
  root,api=setup(folder);old=failed(root,api);ws=api.svc.workspace(m.WORKSPACE,api.ctx);ws['goal']='Changed';api.svc.repo.put('workspaces',m.WORKSPACE,ws);before=len(api.posts)
  try:resume.run(api,root,R,'Offline Reviewer')
  except Stop as e:ok('workspace drift blocks restart',e.code=='WORKSPACE_CHANGED' and len(api.posts)==before)
 with tempfile.TemporaryDirectory() as folder:
  root,api=setup(folder);pdfs=m.files(root,R);guard=resume.RemainingOnly(api,m,R,pdfs)
  for path,data in [('/domains/approve',{'draft_id':'any'}),('/cases/read',{'case_id':m.DOCS[0]['case_id']}),('/cases/confirm',{})]:
   try:guard.call(path,data,key='unexpected')
   except Stop as e:ok('write guard '+path,e.code=='UNEXPECTED_WRITE' and not api.posts)
result={'passed':True,'checks':checks,'real_model_calls':0,'cloud_writes':0,'raw_observations_preserved':True,'test_identity_pins':'Explicit local test-double IDs, never used by published controller.','scope':'Original gate reproduction and bounded recovery against real service/PDF validation with explicit extraction/HTTP doubles.'}
(ROOT/'verification/intake128_resume_offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'real_model_calls':0}))

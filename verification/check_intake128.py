"""Exact owner-reported rules; real service/PDF validation with explicit model doubles."""
import copy,importlib.util,json,sys,tempfile,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
from core.models import validate_domain,permitted,JTError,digest
from service import Service
from storage.repository import LocalRepository,Blobs
from case_intake import read_case
spec=importlib.util.spec_from_file_location('intake128',ROOT/'releases/jt_intake_128.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
report=json.loads((ROOT/'verification/LIVE128_GATE.json').read_text())
original={**copy.deepcopy(report['workflow_preview']),'schema_version':'1.0','domain_id':'offline_reported128','version':0,'source_hashes':{m.SOURCE:m.SOURCE_HASH}}
policy=(ROOT/'app/web/samples/expense_policy.txt').read_text();reviewed=m.reviewed_domain(original,policy)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
validate_domain(original);validate_domain(reviewed)
ok('exact reported preview hash',m.digest(m.preview(original))==m.PREVIEW_HASH)
ok('clarification preserves every executable condition and action',all(a['when']==b['when'] and a['action_id']==b['action_id'] and a['priority']==b['priority'] for a,b in zip(original['rules'],reviewed['rules'])) and original['actions']==reviewed['actions'])
ok('original model answer not modified',original=={**copy.deepcopy(report['workflow_preview']),'schema_version':'1.0','domain_id':'offline_reported128','version':0,'source_hashes':{m.SOURCE:m.SOURCE_HASH}})
for i,doc in enumerate(m.DOCS):
 expected='ready_for_business_approval' if i==0 else 'hold'
 ok('reported baseline rule replay '+doc['case_id'],permitted(reviewed,doc['transcription'])[0]==expected)
base=m.DOCS[0]['transcription']
for name,delta,expect in [('missing amount',{'receipt_employee_paid_amount':None},'hold'),('missing employee status',{'receipt_payment_status':None},'hold'),('unpaid employee',{'receipt_payment_status':'UNPAID'},'hold'),('known mismatch',{'claimed_amount':1},'return_for_correction'),('changed dates over mismatch',{'actual_end_date':'2026-09-06','claimed_amount':1},'hold'),('missing date',{'actual_start_date':None},'hold'),('guest mismatch',{'guest_name':'Different Guest'},'return_for_correction')]:
 ok(name,permitted(reviewed,{**base,**delta})[0]==expect)
class Stop(Exception):
 def __init__(self,code,msg):super().__init__(msg);self.code=code
class R:
 Stop=Stop
 @staticmethod
 def load(p):return json.loads(p.read_text()) if p.exists() else {}
 @staticmethod
 def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
 @staticmethod
 def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Double:
 mode='LIVE' # Explicit test double. Never used by the real command.
 def __init__(self,repo):self.repo=repo;self.calls=[];self.bad_status=False
 def invoke(self,purpose,payload,schema,sources,owner,admin):
  self.calls.append(copy.deepcopy(payload));cid=payload['case_id'];doc=next(x for x in evidence if x['case_id']==cid)
  obs=[]
  for f in payload['fields']:
   fid=f['field_id'];item=doc['field_evidence'][fields[fid]];o={'field_id':fid,**copy.deepcopy({k:item[k] for k in ('value','status','source_refs')})}
   for ref in o['source_refs']:ref.update(source_id=sources[0]['source_id'],version_hash=sources[0]['version_hash'])
   if self.bad_status and fid=='receipt_payment_status':o['source_refs'][0]['quote']='Total settlement status: PAID'
   obs.append(o)
  trace={'trace_id':'trace_offline_'+str(len(self.calls)),'mode':'TEST_DOUBLE','result':{'observations':obs}}
  self.repo.put('traces',trace['trace_id'],trace);return trace['result'],trace
fields={'claimant_name':'claimant_name','guest_name':'receipt_guest_name','approved_start_date':'approved_stay_start','approved_end_date':'approved_stay_end','actual_start_date':'receipt_stay_start','actual_end_date':'receipt_stay_end','receipt_addressed_to':'receipt_addressee_name','claimed_amount':'claimed_amount_jpy','receipt_employee_paid_amount':'employee_payment_amount_jpy','receipt_payment_status':'employee_payment_status'}
evidence=json.loads((ROOT/'app/fixtures/expense_review/case_documents.json').read_text())['documents']
class API:
 def __init__(self,svc,adapter,ctx):self.svc=svc;self.adapter=adapter;self.ctx=ctx;self.cache={};self.posts=[];self.lose=None;self.wronghealth=False
 def call(self,path,data=None,key=None,files=None):
  if path=='/health':return {'package_version':'wrong' if self.wronghealth else m.VERSION,'code_hash':m.CODE_HASH,'mode':'LIVE','max_cost_usd':100}
  if path=='/recovery115':
   n=len(self.adapter.calls);return {'session':{'calls':516+n,'decisions':498},'budget':{'calls':516+n,'decisions':0,'day':'2026-10-15','spent_usd':17.1859638+n*.01},'study':{'phase':'COMPLETE','historical':'unchanged'},'additional_decisions_used':0,'extra_retry_attempts':{'used':0,'limit':6}}
  if path.startswith('/workspaces/'):return self.svc.summary(m.WORKSPACE,self.ctx)
  if path.startswith('/history/'):return self.svc.owned('history',path.split('/')[-1],self.ctx)
  if key in self.cache:return copy.deepcopy(self.cache[key])
  self.posts.append((path,copy.deepcopy(data)));self.ctx['operation']=key
  try:
   if path=='/domains/draft':value=self.svc.draft_domain(data,self.ctx)
   elif path=='/domains/approve':value=self.svc.approve_domain(data,self.ctx)
   elif path=='/cases/read':value=read_case(self.svc,data,files[0],files[2],files[1],self.ctx)
   else:raise AssertionError('unexpected write '+path)
  except JTError as e:raise Stop(e.code,str(e)) from e
  self.cache[key]=copy.deepcopy(value)
  if self.lose==path:self.lose=None;raise Stop('NETWORK_INTERRUPTED','explicit lost-response double')
  return value

def setup(folder):
 root=Path(folder);(root/'app/web/samples').mkdir(parents=True)
 for name in ('expense_files.json','expense_policy.txt'):(root/'app/web/samples'/name).write_bytes((ROOT/'app/web/samples'/name).read_bytes())
 repo=LocalRepository(root/'repo');adapter=Double(repo);svc=Service(repo,Blobs(root/'repo'),adapter);ctx={'owner':'offline128','admin':True,'operation':'offline'}
 ws=svc.create_workspace({'goal':original['goal']},ctx);old=ws['workspace_id'];w=repo.get('workspaces',old);w['workspace_id']=m.WORKSPACE;repo.put('workspaces',m.WORKSPACE,w)
 svc.add_source(m.WORKSPACE,'policy.txt',policy.encode(),'text/plain',ctx,m.SOURCE)
 d={'draft_id':m.DRAFT,'workspace_id':m.WORKSPACE,'domain':copy.deepcopy(original),'base_version':-1,'origin':'LIVE','trace_ids':[m.TRACE],'input_review_issues':[]}
 repo.put('drafts',m.DRAFT,d);w=repo.get('workspaces',m.WORKSPACE);w.update(draft_id=m.DRAFT,shared_trace_ids=[m.TRACE]);repo.put('workspaces',m.WORKSPACE,w)
 R.save(root/'.jt/upgrades/1.0.28/workflow-prepare.json',{'status':'DRAFT_READY_FOR_REVIEW','draft_id':m.DRAFT,'code_hash':m.CODE_HASH,'trace_ids':[m.TRACE]})
 return root,API(svc,adapter,ctx)
# Keep verbose controller output out of the test report.
import contextlib,io
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);p=m.run(api,root,R,'Offline Reviewer',True)
  ok('six actual PDFs pass real service source-reference and scalar validation',p['status']=='READINGS_READY_FOR_REVIEW' and len(api.adapter.calls)==6)
  ok('one named approval, no case confirmation or judgment',p['approval_record']['reviewer_name']=='Offline Reviewer' and {a for a,b in api.posts}=={'/domains/draft','/domains/approve','/cases/read'} and not api.svc.workspace(m.WORKSPACE,api.ctx)['case_ids'])
  ok('original LIVE draft preserved and human edit honestly labeled',api.svc.repo.get('drafts',m.DRAFT)['domain']==original and p['edited_draft']['origin']=='HUMAN_EDIT')
  ok('only fields and one case identity go to extraction; no rule, transcription or target outcome',all(set(v)=={'instruction','fields','case_id'} for v in api.adapter.calls))
  ok('holdout reading separated from dev and shared sources',len([x for x in p['readings'] if x['split']=='holdout'])==2 and api.svc.workspace(m.WORKSPACE,api.ctx)['source_ids']==[m.SOURCE])
  before=len(api.posts);m.run(api,root,R,'Offline Reviewer',True);ok('completed reentry adds no posts',len(api.posts)==before)
 for path in ('/domains/draft','/domains/approve','/cases/read'):
  with tempfile.TemporaryDirectory() as f:
   root,api=setup(f);api.lose=path
   try:m.run(api,root,R,'Offline Reviewer',True)
   except Stop as e:ok('lost response pauses '+path,e.code=='INTAKE_PENDING')
   else:raise AssertionError('no pause')
   p=m.run(api,root,R,'Offline Reviewer',True)
   ok('lost response resumes saved receipt '+path,p['status']=='READINGS_READY_FOR_REVIEW' and len(api.adapter.calls)==6 and sum(x[0]=='/domains/approve' for x in api.posts)==1)
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);api.adapter.bad_status=True
  try:m.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('total PAID cannot masquerade as employee PAID',e.code=='CASE_READ_GATE_FAILED' and len(api.adapter.calls)==1)
  else:raise AssertionError('accepted wrong evidence')
  try:m.run(api,root,R,'Offline Reviewer',True)
  except Stop:ok('failed reentry does not regenerate',len(api.adapter.calls)==1)
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f)
  try:m.run(api,root,R,'Offline Reviewer',False)
  except Stop as e:ok('explicit approval flag required before any API write',e.code=='REVIEW_APPROVAL_REQUIRED' and not api.posts)
  api.wronghealth=True
  try:m.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('wrong deployed version stops before edits',e.code=='DEPLOY_MISMATCH' and not api.posts)
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);d=api.svc.repo.get('drafts',m.DRAFT);d['domain']['rules'][0]['action_id']='return_for_correction';api.svc.repo.put('drafts',m.DRAFT,d)
  try:m.run(api,root,R,'Offline Reviewer',True)
  except Stop as e:ok('changed proposed rule rejected before approval',e.code=='WORKSPACE_CHANGED' and not api.posts)
result={'passed':True,'checks':checks,'real_model_calls':0,'cloud_writes':0,'scope':'Exact owner-reported rule replay; real service and six real PDFs with explicit extraction/HTTP doubles. No LIVE document extraction or browser acceptance.'}
(ROOT/'verification/intake128_offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'model_calls':0}))

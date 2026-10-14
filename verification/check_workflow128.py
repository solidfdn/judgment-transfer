"""Reported draft regression and real service boundaries; provider calls are doubles."""
import ast,base64,copy,hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
import core.models as models
from core.models import JTError,compare,digest,permitted,validate_domain
from workflow_review import input_issues
from service import Service
from storage.repository import LocalRepository,Blobs
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def reject(name,fn,code):
 try:fn()
 except JTError as e:ok(name,e.code==code)
 else:raise AssertionError(name)
report=json.loads((ROOT/'verification/LIVE127_GATE.json').read_text())
reported={**copy.deepcopy(report['workflow_preview']),'schema_version':'1.0','domain_id':'reported127','version':0,
 'source_hashes':{'expense_policy_124':'8548c15f795f156db72efbd3b91c332e8ef08a590e31509070a35f7e2e355d47'}}
# The log omits domain metadata; the synthetic ID above has no effect on rules.
validate_domain(reported)
issues=input_issues(reported)
ok('reported draft catches decision and combined amount inputs',{x['field_id'] for x in issues}=={'is_receipt_accepted','employee_paid_amount_marked_paid'})
facts={'claimant_name':'Example Person','guest_name':'Example Person','approved_start_date':'2026-10-01',
 'actual_start_date':'2026-10-01','approved_end_date':'2026-10-02','actual_end_date':'2026-10-02',
 'receipt_addressed_to':'Example Person','claimed_amount':100,'employee_paid_amount_marked_paid':100,'is_receipt_accepted':True}
def release(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/('releases/jt_release_'+name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
old_source=base64.b64decode(release('123').DATA['files']['app/core/models.py'])
assert hashlib.sha256(old_source).hexdigest()==release('127').DATA['new']['files']['app/core/models.py']
oldtree=ast.parse(old_source.decode())
fn=next(n for n in oldtree.body if isinstance(n,ast.FunctionDef) and n.name=='compare');ns={'JTError':JTError,'math':models.math}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'saved-127-comparator','exec'),ns)
with patch.object(models,'compare',ns['compare']):
 ok('reported existence defect reproduced with present amount',permitted(reported,facts)[0]=='hold')
ok('false existence no longer matches a present amount',permitted(reported,facts)[0]=='ready_for_business_approval')
# The acceptance flag still makes that permission circular; the new approval
# gate below blocks this draft despite its structural schema being valid.
for value in (None,False,0,'',12,'PAID'):
 for expected in (True,False,None):
  actual=compare({'field_id':'x','operator':'exists','value':expected},{'x':value})
  ok('exists polarity '+repr((value,expected)),actual==((value is None) if expected is False else (value is not None)))
for invalid in (0,1,'false',[],{}):
 bad=copy.deepcopy(reported);bad['rules'][3]['when']['all'][0]['value']=invalid
 reject('invalid exists operand '+repr(invalid),lambda:validate_domain(bad),'INVALID_INPUT')
# Legacy null means presence and all historical true/null uses keep that meaning.
for pack in ('invoice_routing','support_triage','expense_review'):
 for filename in ('domain_v0.json','domain_v1_reference.json'):
  p=ROOT/'app/fixtures'/pack/filename
  if p.exists():validate_domain(json.loads(p.read_text()))
ok('existing declared example domains remain valid')
for field in [
 {'field_id':'item_eligible','label':'Item Eligible','type':'boolean','required':True,'description':'Whether the item meets policy.'},
 {'field_id':'permitValid','label':'Permit Valid','type':'boolean','required':True,'description':'Whether a permit complies.'}]:
 d=copy.deepcopy(reported);d['input_fields']=[field];ok('generic verdict check '+field['field_id'],bool(input_issues(d)))
checkbox={'field_id':'recorded_eligible','label':'Recorded Eligible','type':'boolean','required':True,'description':'Copy the Eligible checkbox from the signed inspection form.'}
d=copy.deepcopy(reported);d['input_fields']=[checkbox];ok('explicit recorded checkbox remains a fact declaration',not input_issues(d))
# A hand-edited candidate is used only as an explicit test response. It is never
# supplied to a LIVE generator, uploaded, approved on the owner's behalf or
# claimed to be an AI result.
corrected=copy.deepcopy(reported)
corrected['input_fields']=[f for f in corrected['input_fields'] if f['field_id']!='is_receipt_accepted']
for f in corrected['input_fields']:
 if f['field_id']=='employee_paid_amount_marked_paid':
  f.update(field_id='employee_payment_amount',label='Employee payment amount',description='The employee payment amount explicitly stated on the receipt.')
corrected['input_fields'].append({'field_id':'employee_payment_status','label':'Employee payment status','description':'The literal status stated for the employee payment.','type':'string','required':True})
for rule in corrected['rules']:
 for group in ('all','any'):
  for condition in rule['when'][group]:
   for key in ('field_id','rhs_field_id'):
    if condition.get(key)=='employee_paid_amount_marked_paid':condition[key]='employee_payment_amount'
   if condition['field_id']=='is_receipt_accepted':
    condition.clear();condition.update(field_id='receipt_addressed_to',operator='eq',rhs_field_id='claimant_name')
 if rule['rule_id'] in ('amount_mismatch','precheck_complete'):
  rule['when']['all'].append({'field_id':'employee_payment_status','operator':'eq','value':'PAID'})
  # Existing line 7 supplies the personal-receipt condition, unlike line 9 alone.
  rule['source_refs'].append({'source_id':'expense_policy_124','version_hash':next(iter(corrected['source_hashes'].values())),
    'locator':'line:7','quote':(ROOT/'app/web/samples/expense_policy.txt').read_text().splitlines()[6]})
validate_domain(corrected);ok('explicit test correction has no flagged inputs',not input_issues(corrected))
raw={k:v for k,v in facts.items() if k not in ('is_receipt_accepted','employee_paid_amount_marked_paid')}
raw.update(employee_payment_amount=100,employee_payment_status='PAID')
for name,delta,expected in [('personal',{},'ready_for_business_approval'),('company',{'receipt_addressed_to':'Fictional Company'},'hold'),
 ('missing amount',{'employee_payment_amount':None},'hold'),('missing status',{'employee_payment_status':None},'hold'),
 ('other payer paid',{'employee_payment_status':'UNPAID'},'hold'),('changed stay',{'actual_end_date':'2026-10-03'},'hold'),
 ('known mismatch',{'claimed_amount':90},'return_for_correction')]:
 ok('raw-fact correction '+name,permitted(corrected,{**raw,**delta})[0]==expected)
class Adapter:
 mode='LIVE'
 def __init__(self,repo):self.repo=repo;self.calls=[];self.value=reported;self.hook=None
 def draft_domain(self,*args,**kwargs):
  self.calls.append(copy.deepcopy(kwargs));v=copy.deepcopy(self.value)
  t={'trace_id':'trace_double_'+str(len(self.calls)),'mode':'TEST_DOUBLE','purpose':'draft_domain','result':copy.deepcopy(v)}
  self.repo.put('traces',t['trace_id'],t)
  if self.hook:self.hook()
  return v,t
with tempfile.TemporaryDirectory() as folder:
 repo=LocalRepository(folder);blobs=Blobs(folder);adapter=Adapter(repo);svc=Service(repo,blobs,adapter)
 ctx={'owner':'offline128','admin':True,'operation':'create'};wid=svc.create_workspace({'goal':reported['goal']},ctx)['workspace_id']
 source=svc.add_source(wid,'policy.txt',(ROOT/'app/web/samples/expense_policy.txt').read_bytes(),'text/plain',ctx,'expense_policy_124')
 ws=svc.workspace(wid,ctx);ws['extraction']={'observations':[],'source_hashes':reported['source_hashes']};repo.put('workspaces',wid,ws)
 ctx['operation']='original';first=svc.draft_domain({'workspace_id':wid},ctx)
 original=copy.deepcopy(repo.get('drafts',first['draft_id']))
 ok('reported source quotations remain strictly valid',bool(first['trace_ids']))
 reject('named approval cannot activate flagged draft',lambda:svc.approve_domain({'draft_id':first['draft_id'],'base_version':-1,'reviewer_name':'Offline Test'},ctx),'INVALID_INPUT')
 ok('blocked approval creates no version or history',svc.workspace(wid,ctx)['version']==-1 and not svc.workspace(wid,ctx).get('history_ids'))
 # Even a caller-cleared issue list cannot bypass the server's recomputation.
 modified=copy.deepcopy(original);modified['input_review_issues']=[];repo.put('drafts',first['draft_id'],modified)
 reject('cleared metadata cannot bypass approval check',lambda:svc.approve_domain({'draft_id':first['draft_id'],'base_version':-1,'reviewer_name':'Offline Test'},ctx),'INVALID_INPUT')
 repo.put('drafts',first['draft_id'],original)
 adapter.value=corrected;ctx['operation']='revision'
 second=svc.draft_domain({'workspace_id':wid,'revise_draft_id':first['draft_id']},ctx)
 ok('revision sends previous draft and exact findings once',len(adapter.calls)==2 and adapter.calls[-1]['revision']['domain']==reported and adapter.calls[-1]['revision']['input_review_issues']==issues)
 ok('revision leaves original cloud draft and trace intact',repo.get('drafts',first['draft_id'])==original and repo.get('traces',first['trace_ids'][0])['result']==reported)
 ok('revision records parent and stays unapproved',second['revision_of']==first['draft_id'] and svc.workspace(wid,ctx)['version']==-1 and all(x['approved_by'] is None for x in second['domain']['rules']))
 svc.draft_domain({'workspace_id':wid,'revise_draft_id':first['draft_id']},ctx)
 ok('same operation returns saved draft without another generation',len(adapter.calls)==2)
 ctx['operation']='stale-revision'
 reject('superseded draft cannot be revised',lambda:svc.draft_domain({'workspace_id':wid,'revise_draft_id':first['draft_id']},ctx),'STALE')
 reject('foreign draft revision rejected',lambda:svc.draft_domain({'workspace_id':wid,'revise_draft_id':second['draft_id']},{**ctx,'owner':'other'}),'NOT_FOUND')
 reject('clean draft does not trigger unnecessary correction',lambda:svc.draft_domain({'workspace_id':wid,'revise_draft_id':second['draft_id']},ctx),'INVALID_INPUT')
 ok('summary review never mutates saved records',svc.summary(wid,ctx)['draft']==second and repo.get('drafts',first['draft_id'])==original)
 # A concurrent replacement must not be overwritten after generation.
 ws=svc.workspace(wid,ctx);ws['draft_id']=first['draft_id'];repo.put('workspaces',wid,ws)
 def concurrent():
  w=svc.workspace(wid,ctx);w['draft_id']='competing-draft';repo.put('workspaces',wid,w)
 adapter.hook=concurrent;ctx['operation']='concurrent-revision'
 reject('concurrent draft replacement stops revision commit',lambda:svc.draft_domain({'workspace_id':wid,'revise_draft_id':first['draft_id']},ctx),'VERSION_CONFLICT')
 ok('concurrent current draft is preserved',svc.workspace(wid,ctx)['draft_id']=='competing-draft')
 adapter.hook=None;ws=svc.workspace(wid,ctx);ws['draft_id']=second['draft_id'];repo.put('workspaces',wid,ws)
 # Explicit named approval in a local double-backed test only.
 svc.approve_domain({'draft_id':second['draft_id'],'base_version':-1,'reviewer_name':'Offline Test'},ctx)
 ok('reviewed raw-fact draft retains named approval path',svc.workspace(wid,ctx)['version']==0)
# Exercise the actual LIVE request-building method with a captured transport.
modeltree=ast.parse((ROOT/'app/adapters/model.py').read_text())
klass=next(n for n in modeltree.body if isinstance(n,ast.ClassDef) and n.name=='LiveAdapter')
fn=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='draft_domain')
namespace={'copy':copy,'schema':lambda name:{'contract':name}}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-draft-request','exec'),namespace)
captured=[]
class Transport:
 def invoke(self,*args):captured.append(args);return 'captured'
revision={'draft_id':'prior','domain':reported,'input_review_issues':issues}
namespace['draft_domain'](Transport(),'Check source facts','test',0,[source],[],'test-owner',True,revision=revision)
ok('revision builds one existing draft-domain invocation',len(captured)==1 and captured[0][0]=='draft_domain')
ok('revision carries exact findings and previous answer separately from sources',captured[0][1]['revision']==revision and captured[0][3]==[source])
ok('revision uses unchanged domain response contract',captured[0][2]=={'contract':'DomainSpec'})
revision['draft_id']='modified after call'
ok('request isolates previous-draft metadata',captured[0][1]['revision']['draft_id']=='prior')

result={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual core/service with reported 1.0.27 preview and explicit provider doubles; no LIVE corrected draft claimed.'}
(ROOT/'verification/workflow128_offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':len(checks),'new_model_calls':0}))

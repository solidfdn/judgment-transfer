import ast,copy,datetime as dt,json,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
import config
from service import Service
from storage.repository import LocalRepository,Blobs
from core.models import JTError,digest
from history import actor,fix_review,records
from validation123 import authorize
checks=[]
def ok(n,v=True):assert v,n;checks.append(n)
def reject(n,fn,code=None):
 try:fn()
 except JTError as e:
  assert not code or e.code==code,(n,e.code);checks.append(n)
 else:raise AssertionError(n)
parsed=ast.parse((ROOT/'app/adapters/model.py').read_text());selected=[n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='Budget'];scope={'dt':dt,'digest':digest,'config':config,'JTError':JTError};exec(compile(ast.Module(body=selected,type_ignores=[]),'actual_budget_class','exec'),scope);Budget=scope['Budget']
with tempfile.TemporaryDirectory() as td:
 repo=LocalRepository(td);svc=Service(repo,Blobs(td),types.SimpleNamespace(mode='MOCK'));seq=0
 def ctx(admin=True):
  global seq;seq+=1;return {'owner':'named-offline-owner','admin':admin,'operation':'op_'+str(seq)}
 ws=svc.create_workspace({'goal':'Review equipment return requirements'},ctx());wid=ws['workspace_id'];data=b'Return the loaned equipment.\nRecord the return date.\n'
 src=svc.add_source(wid,'equipment.txt',data,'text/plain',ctx(),'equipment_source');review={'goal':ws['goal'],'source_hashes':{src['source_id']:src['version_hash']},'summary':'Return completion needs a verification owner.','checks':[],'questions':[],'observations':[],'trace_id':'draft_only'}
 w=svc.workspace(wid,ctx());w['requirements_review']=review;repo.put('workspaces',wid,w)
 reject('name required for fixation',lambda:fix_review(svc,{'workspace_id':wid},ctx()),'REVIEWER_REQUIRED')
 ok('missing name creates no record',not records(svc,wid,ctx()))
 reject('whitespace name rejected',lambda:actor({'reviewer_name':'  '}),'REVIEWER_REQUIRED')
 reject('control characters in name rejected',lambda:actor({'reviewer_name':'A\nB'}),'REVIEWER_REQUIRED')
 reject('oversized memo rejected',lambda:actor({'reviewer_name':'A','memo':'x'*2001}),'INVALID_INPUT')
 rec=fix_review(svc,{'workspace_id':wid,'reviewer_name':'Responsible reviewer','memo':'Confirm the return recipient next.'},ctx());rid=rec['record_id'];original=copy.deepcopy(repo.get('history',rid))
 ok('name memo timestamp recorded',rec['reviewer_name']=='Responsible reviewer' and rec['memo'] and rec['recorded_at'].endswith('+00:00'))
 content={k:v for k,v in rec.items() if k!='record_hash'};ok('record digest covers snapshot and attribution',digest(content)==rec['record_hash'])
 svc.add_source(wid,'equipment.txt',b'Return equipment to the service desk.\nRecord the return date.\n','text/plain',ctx(),'equipment_source')
 ok('finalized record unchanged after source replacement',repo.get('history',rid)==original)
 ok('original source bytes remain accessible',svc.blobs.get(rec['source_metadata'][0]['blob_id'])==data)
 reject('stale review cannot be finalized',lambda:fix_review(svc,{'workspace_id':wid,'reviewer_name':'Reviewer'},ctx()),'STALE')
 w=svc.workspace(wid,ctx());w['requirements_review']={**review,'summary':'Service desk now named.','source_hashes':{'equipment_source':svc.source(wid,'equipment_source')['version_hash']}};repo.put('workspaces',wid,w)
 rec2=fix_review(svc,{'workspace_id':wid,'reviewer_name':'Second reviewer'},ctx());ok('new revision links to previous fixed record',rec2['previous_record_id']==rid and len(records(svc,wid,ctx()))==2)
 ok('previous review remains distinct',repo.get('history',rid)['snapshot']['summary']!=rec2['snapshot']['summary'])
 reject('another owner cannot read fixed record',lambda:svc.owned('history',rid,{'owner':'stranger'}),'NOT_FOUND')
 # Budget starts with the real exhausted shapes but uses a temporary local repository.
 owner=ctx()['owner'];sk=('budget',digest(owner)[:40]);repo.put(*sk,{'calls':509,'decisions':500})
 old={'owner':owner,'base_decisions':249,'replacement112':{'authorized':True},'recovery113':{'authorized':True,'retry_used':6},'streamed114':{'authorized':True}}
 repo.put('budget','recovery111',old);repo.put('budget','global',{'day':dt.datetime.now(dt.timezone.utc).date().isoformat(),'calls':509,'decisions':500,'spent_usd':7.5})
 config.MAX_COST=100
 reject('nonadministrator grant rejected',lambda:authorize(svc,{'max_cost_usd':100,'reviewer_name':'Owner'},ctx(False)),'ADMIN_REQUIRED')
 grant=authorize(svc,{'max_cost_usd':100,'reviewer_name':'Owner','memo':'Bounded new document validation'},ctx())
 ok('40 calls and 24 decisions from current usage',grant['base_calls']==509 and grant['base_decisions']==500 and grant['additional_calls']==40 and grant['additional_decisions']==24)
 ok('grant does not alter counters',repo.get(*sk)=={'calls':509,'decisions':500})
 ok('reauthorization cannot reset or enlarge grant',authorize(svc,{'max_cost_usd':100,'reviewer_name':'Another name'},ctx())==grant)
 budget=Budget(repo);before=repo.get('budget','global')['spent_usd'];budget.reserve(owner,True,'extract',100,100)
 ok('new preparation call charged cumulatively',repo.get(*sk)['calls']==510 and repo.get('budget','global')['spent_usd']>before)
 for i in range(4):budget.reserve(owner,True,'decide',100,100,retry=True)
 reject('fifth new retry refused',lambda:budget.reserve(owner,True,'decide',100,100,retry=True),'RETRY_LIMIT')
 ok('old grant and consumed retries unchanged',repo.get('budget','recovery111')==old)
 s=repo.get(*sk);s['calls']=549;repo.put(*sk,s)
 reject('40-call allowance stops',lambda:budget.reserve(owner,True,'extract',100,100),'CALL_LIMIT')
 s['calls']=510;s['decisions']=524;repo.put(*sk,s)
 reject('24-decision allowance stops',lambda:budget.reserve(owner,True,'decide',100,100),'CALL_LIMIT')
 s['decisions']=501;repo.put(*sk,s);g=repo.get('budget','global');g['spent_usd']=100;repo.put('budget','global',g)
 reject('100-dollar ceiling enforced',lambda:budget.reserve(owner,True,'extract',100,100),'COST_LIMIT')
 report={'passed':True,'checks':checks,'real_model_calls':0,'cloud_writes':0,'runtime':'actual service/history and AST-loaded unchanged Budget class; local temporary repository'}
 (ROOT/'verification/history_budget_123.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'checks':len(checks)},indent=2))
# The schema sent to the provider must preserve XOR even when oneOf becomes anyOf.
from core.models import CONTRACT
from jsonschema import Draft202012Validator
node=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='schema')
space={'CONTRACT':CONTRACT};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_schema_builder','exec'),space)
schema=space['schema']('DomainSpec');condition=schema['properties']['rules']['items']['properties']['when']['properties']['all']['items'];validator=Draft202012Validator(condition)
assert not list(validator.iter_errors({'field_id':'a','operator':'eq','value':3}))
assert not list(validator.iter_errors({'field_id':'a','operator':'eq','rhs_field_id':'b'}))
assert list(validator.iter_errors({'field_id':'a','operator':'eq','rhs_field_id':'b','value':3}))
print('Provider condition alternatives: 3 checks passed.')

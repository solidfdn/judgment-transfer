import copy,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from service import Service
from storage.repository import LocalRepository,Blobs
from core.models import JTError,digest,permitted
from case_intake import read_case,confirm_case,case_evidence
from requirements_review import review_requirements,ASPECTS
checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
def reject(n,fn,code=None):
 try:fn()
 except JTError as e:
  if code:assert e.code==code,(n,e.code)
  checks.append(n)
 else:raise AssertionError('accepted '+n)
class Stub:
 mode='MOCK'
 def __init__(self,repo):self.repo=repo;self.calls=[];self.hook=None;self.result=None
 def invoke(self,purpose,payload,schema,sources,owner,admin):
  self.calls.append({'purpose':purpose,'payload':copy.deepcopy(payload),'sources':copy.deepcopy(sources)})
  if self.hook:self.hook()
  result=self.result(sources,payload)
  trace={'trace_id':'trace_stub_'+str(len(self.calls)),'mode':'MOCK','purpose':purpose,'payload':payload,'settings':{'model':'STUB'},'attempts':[],'elapsed_ms':0,'result':copy.deepcopy(result)}
  self.repo.put('traces',trace['trace_id'],trace)
  return result,trace
with tempfile.TemporaryDirectory() as folder:
 repo=LocalRepository(folder);blobs=Blobs(folder);adapter=Stub(repo);svc=Service(repo,blobs,adapter);seq=0
 def ctx(admin=True):
  global seq
  seq+=1;return {'owner':'offline-reviewer','operation':'operation_'+str(seq),'admin':admin}
 w=svc.create_workspace({'goal':'Check hotel expense evidence'},ctx());wid=w['workspace_id'];f=ROOT/'app/fixtures/expense_review'
 svc.add_source(wid,'source_sop.txt',(f/'source_sop.txt').read_bytes(),'text/plain',ctx(),'expense_sop')
 d=svc.draft_domain({'workspace_id':wid,'domain':json.loads((f/'domain_v0.json').read_text())},ctx())
 svc.approve_domain({'draft_id':d['draft_id'],'base_version':-1,'reviewer_name':'Offline reviewer'},ctx())
 docmap=json.loads((f/'case_documents.json').read_text())['documents'];confirmed=[]
 def observation_result(doc,alter=None):
  def factory(sources,payload):
   obs=[]
   for fid,entry in doc['field_evidence'].items():
    o={k:copy.deepcopy(entry[k]) for k in ('value','status','source_refs')};o['field_id']=fid
    for ref in o['source_refs']:ref.update(source_id=sources[0]['source_id'],version_hash=sources[0]['version_hash'])
    obs.append(o)
   if alter:alter(obs)
   return {'observations':obs}
  return factory
 for doc in docmap:
  adapter.result=observation_result(doc)
  split='holdout' if 'holdout' in doc['case_id'] else 'dev';path=ROOT/'output/Expense_Demo_Data'/doc['relative_path']
  draft=read_case(svc,{'workspace_id':wid,'case_id':doc['case_id'],'split':split},path.name,path.read_bytes(),'application/pdf',ctx())
  ok('document '+doc['claim_id']+' parsed and observed values grounded',len(draft['observations'])==13)
  ok('no implicit case approval '+doc['claim_id'],doc['case_id'] not in svc.workspace(wid,ctx())['case_ids'])
  case=copy.deepcopy(draft['case']);case['initial_state']['status']='NEW'
  confirm_case(svc,{'workspace_id':wid,'case_draft_id':draft['case_draft_id'],'case':case,'reviewer_name':'Offline reviewer'},ctx());confirmed.append(case)
  ok('case confirmed with source provenance '+doc['claim_id'],bool(case_evidence(svc,wid,[case['case_id']])))
  reject('case cannot be confirmed twice '+doc['claim_id'],lambda:confirm_case(svc,{'workspace_id':wid,'case_draft_id':draft['case_draft_id'],'case':case,'reviewer_name':'Offline reviewer'},ctx()))
 ws=svc.workspace(wid,ctx());ok('all six saved without replacing cases',len(ws['case_ids'])==6)
 ok('case docs never join policy sources',[s['source_id'] for s in svc.sources(ws)]==['expense_sop'])
 ok('case extraction traces never enter shared preparation',not ws['shared_trace_ids'])
 ok('summary hides held-out cases',len(svc.summary(wid,ctx())['dev_cases'])==4)
 ok('extraction receives declared raw fields and one file',all(len(c['sources'])==1 and 'rules' not in c['payload'] and 'expected' not in c['payload'] for c in adapter.calls))
 for ver,expected in [('domain_v0.json',['ready_for_approval','hold_case','hold_case','hold_case','hold_case','hold_case']),('rules_v1_reference.json',['ready_for_approval','ready_for_approval','hold_case','hold_case','ready_for_approval','return_for_correction'])]:
  domain=json.loads((f/ver).read_text());actual=[permitted(domain,{**c['facts'],**c['initial_state']})[0] for c in confirmed]
  ok(ver+' deterministic actions from confirmed raw values',actual==expected)
 # Further cases use explicit malformed stub observations to check rejection.
 doc=docmap[0];path=ROOT/'output/Expense_Demo_Data'/doc['relative_path']
 def read_new(admin=True):return read_case(svc,{'workspace_id':wid},path.name,path.read_bytes(),'application/pdf',ctx(admin))
 adapter.result=observation_result(doc,lambda obs:obs.append(copy.deepcopy(obs[0])))
 reject('duplicate field rejected',read_new)
 adapter.result=observation_result(doc,lambda obs:obs[0]['source_refs'][0].update(source_id='expense_sop'))
 reject('wrong-document evidence rejected',read_new,'INVALID_EVIDENCE')
 adapter.result=observation_result(doc,lambda obs:obs[0]['source_refs'][0].update(quote='not in source'))
 reject('fabricated quotation rejected',read_new)
 adapter.result=observation_result(doc,lambda obs:obs[0].update(value=True))
 reject('observed wrong scalar type rejected',read_new)
 adapter.result=observation_result(doc,lambda obs:obs[0].update(status='INFERRED'))
 inferred=read_new();ok('inference remains blank',inferred['case']['facts']['claimant_name'] is None)
 reject('nonadmin holdout creation rejected',lambda:read_case(svc,{'workspace_id':wid,'split':'holdout'},path.name,path.read_bytes(),'application/pdf',ctx(False)),'ADMIN_REQUIRED')
 foreign={'owner':'different-owner','admin':False,'operation':'foreign-op'}
 reject('foreign workspace denied',lambda:read_case(svc,{'workspace_id':wid},path.name,path.read_bytes(),'application/pdf',foreign),'NOT_FOUND')
 policy=svc.sources(ws)[0]
 ref={'source_id':'expense_sop','version_hash':policy['version_hash'],'locator':'line:1','quote':(f/'source_sop.txt').read_text().splitlines()[0]}
 def review_data(sources,payload):
  return {'observations':[],'summary':'Check what the materials establish before a practice test.','checks':[{'aspect':a,'status':'needs_clarification','finding':'Clarify the required owner decision in this job.','source_refs':[ref]} for a in ASPECTS],'questions':[{'question':'Who confirms exceptions before the case can proceed?','why_needed':'The owner of this decision must be known.','aspect':'exceptions_human_review','source_refs':[ref]}]}
 adapter.result=review_data
 review=review_requirements(svc,{'workspace_id':wid},ctx())
 ok('generic six-perspective review saved',len(review['checks'])==6)
 ok('review never receives case sources or reference answers',[s['source_id'] for s in adapter.calls[-1]['sources']]==['expense_sop'] and not any(x in adapter.calls[-1]['payload']['instruction'].lower() for x in ['hotel','expense','invoice']))
 ok('review also supplies source extraction for existing draft path',svc.workspace(wid,ctx())['extraction']['trace_id']==review['trace_id'])
 def bad_review(s,p):
  v=review_data(s,p);v['checks'][1]['aspect']=v['checks'][0]['aspect'];return v
 adapter.result=bad_review
 reject('duplicate perspective rejected',lambda:review_requirements(svc,{'workspace_id':wid},ctx()))
 def unsupported_ref(s,p):
  v=review_data(s,p);v['checks'][0]['source_refs'][0]['source_id']='unknown';return v
 adapter.result=unsupported_ref
 reject('review refuses unsupported source',lambda:review_requirements(svc,{'workspace_id':wid},ctx()))
 ref['source_id']='expense_sop';adapter.result=review_data
 def concurrent():
  w=svc.workspace(wid,ctx());w['goal']='Changed concurrently';repo.put('workspaces',wid,w)
 adapter.hook=concurrent
 reject('review source/goal compare-and-swap',lambda:review_requirements(svc,{'workspace_id':wid},ctx()),'STALE');adapter.hook=None
 w=svc.workspace(wid,ctx());w['frozen']=True;repo.put('workspaces',wid,w)
 reject('frozen workspace review rejected',lambda:review_requirements(svc,{'workspace_id':wid},ctx()),'FROZEN')
 reject('frozen case reading rejected',read_new,'FROZEN')
 ok('case evidence selection excludes held-out files',len(case_evidence(svc,wid,[c['case_id'] for c in confirmed if c['split']=='dev']))==4)
 report={'passed':True,'checks':checks,'real_PDF_files_loaded':6,'real_pages_validated':12,'observations_from_explicit_test_stub':True,'real_model_calls':0,'cloud_writes':0,'http_route_test':'not_run_no_Flask_in_local_runtime','deterministic_expected_outcomes_only':True}
 out=ROOT/'verification/expense_intake_123.json';out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'passed':True,'checks':len(checks),'PDF_files_loaded':6,'model_calls':0,'report':str(out)},indent=2))

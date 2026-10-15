"""Targeted literal-line and saved-response recovery checks; explicit test records."""
import contextlib,copy,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'verification/check_baseline128.py')}
exec(compile((ROOT/'verification/check_baseline128.py').read_text().split('with contextlib.redirect_stdout(io.StringIO()):')[0],'existing-test-setup','exec'),ns)
from service import ident
from adapters.evidence import inspect_file,validate_ref
from teaching_evidence import prepare_rules,recover_teaching
from core.models import digest,JTError,permitted
ready,base=ns['ready'],ns['b'];checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def setup(folder):
 root,api,intake=ready(folder);svc=api.svc;ctx={**api.ctx,'operation':'baseline129-teaching-draft'};wid=intake['workspace_id'];sid=ident('human',ctx);text=base.EXPLANATION
 metadata,_=inspect_file('expert_answer.txt',text.encode());source={**metadata,'source_id':sid,'workspace_id':wid,'blob_id':digest([wid,sid]),'human':True}
 svc.repo.put('sources',wid+'-'+sid,source);svc.blobs.put(source['blob_id'],text.encode(),'text/plain')
 question={'question_id':'question_saved_test','text':'How is company evidence accepted?','affected_dev_case_ids':['expense_review_dev_02'],'missing_field_ids':[],'source_refs':[],'why_needed':'Explicit offline test'}
 svc.repo.put('questions',question['question_id'],{'workspace_id':wid,'question':question,'base_version':0})
 rules=[]
 for name,line in [('amount_mismatch',2),('precheck_complete',1)]:
  rule=copy.deepcopy(next(r for r in intake['approved_domain']['rules'] if r['rule_id']==name));rule['rule_id']=name+'_cedarline';rule['approved_by']=None
  for c in rule['when']['all']:
   if c['field_id']=='receipt_addressed_to':c.pop('rhs_field_id');c['value']='Cedarline Services'
  rule['source_refs']=[{'source_id':sid,'version_hash':source['version_hash'],'locator':'line:'+str(line),'quote':text.splitlines()[line-1]}];rules.append(rule)
 trace={'trace_id':'trace_saved_test','purpose':'draft_rules','mode':'LIVE','attempts':[{'status':'OK'}],'source_hashes':{sid:source['version_hash']},'result':{'rules':rules},'payload':{'domain':intake['approved_domain'],'question':question,'human_text':text}}
 svc.repo.put('traces',trace['trace_id'],trace);rk=digest([ctx['owner'],'/api/v1/teachings',ctx['operation']]);svc.repo.put('requests',rk,{'result':{'error':{'code':'INVALID_INPUT','request_id':'req_saved_test'}}})
 body={'question_id':question['question_id'],'trace_id':trace['trace_id'],'original_operation':ctx['operation'],'original_request_id':'req_saved_test','reviewer_name':'Offline Reviewer'}
 def forbidden(*a,**k):raise AssertionError('Model must not be called')
 svc.adapter.draft_rules=forbidden
 return svc,{**ctx,'operation':'recover-test-130'},body,source,trace,intake,api
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  svc,ctx,body,source,trace,intake,api=setup(f);wid=intake['workspace_id'];before=copy.deepcopy(trace)
  result=recover_teaching(svc,body,ctx)
  ok('two literal line references become canonical with provenance',len(result['citation_resolutions'])==2 and all(r['source_refs'][0]['locator']=='human:1' for r in result['teaching']['proposed_rules']))
  ok('raw model response and failed request preserved',svc.repo.get('traces',trace['trace_id'])==before and svc.repo.get('requests',digest([ctx['owner'],'/api/v1/teachings',body['original_operation']]))['result']['error']['code']=='INVALID_INPUT')
  ok('recovery is named dated unapproved and model-free',result['recovery']['new_model_calls']==0 and result['recovery']['reviewer_name']=='Offline Reviewer' and result['recovery']['recorded_at'] and result['teaching']['approval_state']=='DRAFT' and svc.workspace(wid,ctx)['version']==0)
  again=recover_teaching(svc,body,{**ctx,'operation':'another-recovery-key'})
  ok('different recovery request cannot duplicate draft',again==result and svc.workspace(wid,ctx)['teaching_ids']==[result['teaching']['teaching_id']])
  merged=copy.deepcopy(intake['approved_domain']);merged['rules']+=result['teaching']['proposed_rules']
  cases=[x['transcription'] for x in ns['m'].DOCS[:4]]
  ok('four development actions match reviewed explanation',[permitted(merged,c)[0] for c in cases]==['ready_for_business_approval','ready_for_business_approval','hold','hold'])
  for field,value,expected in [('receipt_employee_paid_amount',None,'hold'),('receipt_payment_status',None,'hold'),('receipt_payment_status','UNPAID','hold'),('actual_end_date','2026-09-11','hold'),('claimed_amount',1,'return_for_correction')]:
   ok('exception '+field+'='+str(value),permitted(merged,{**cases[1],field:value})[0]==expected)
  for label,change in [('wrong line',{'locator':'line:1'}),('out of range',{'locator':'line:99'}),('altered quote',{'quote':'Invented instruction'}),('empty quote',{'quote':''}),('stale hash',{'version_hash':'0'*64})]:
   rules=copy.deepcopy(trace['result']['rules']);rules[0]['source_refs'][0].update(change)
   try:prepare_rules(svc,wid,rules)
   except JTError:ok(label+' rejected')
   else:raise AssertionError(label)
  canonical=copy.deepcopy(result['teaching']['proposed_rules']);normalized,changes=prepare_rules(svc,wid,canonical)
  ok('already canonical references unchanged',normalized==canonical and not changes)
  svc.adapter.draft_rules=lambda domain,q,text,source,owner,admin: (copy.deepcopy(trace['result']),copy.deepcopy(trace))
  # Same original operation reconstructs the exact original source; only the new
  # server's actual teaching path applies canonicalization.
  ordinary=svc.teach({'question_id':body['question_id'],'human_text':base.EXPLANATION},{**ctx,'operation':body['original_operation']})
  ok('normal teaching path also canonicalizes exact human lines',len(ordinary['citation_resolutions'])==2 and ordinary['teaching']['approval_state']=='DRAFT')
  bad=copy.deepcopy(trace);bad['result']['rules'][0]['source_refs'][0]['quote']='Invented instruction'
  svc.adapter.draft_rules=lambda *a,**k:(copy.deepcopy(bad['result']),copy.deepcopy(bad))
  try:svc.teach({'question_id':body['question_id'],'human_text':base.EXPLANATION},{**ctx,'operation':body['original_operation']})
  except JTError as e:ok('validation failure carries original trace for diagnosis',getattr(e,'trace',{}).get('trace_id')==trace['trace_id'])
  else:raise AssertionError('invented quote')
  for label,context,data in [('nonadmin',{**ctx,'admin':False},body),('another owner',{**ctx,'owner':'other'},body),('wrong request',ctx,{**body,'original_request_id':'req_wrong'}),('missing reviewer',ctx,{**body,'reviewer_name':''})]:
   try:recover_teaching(svc,data,context)
   except JTError:ok(label+' refused')
   else:raise AssertionError(label)
  ws=svc.workspace(wid,ctx);ws['frozen']=True;svc.repo.put('workspaces',wid,ws)
  try:recover_teaching(svc,body,ctx)
  except JTError:ok('frozen workspace refused')
  else:raise AssertionError('frozen')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual service and evidence validators with explicit local saved-response records; no live success claimed.'}
(ROOT/'verification/teaching130_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

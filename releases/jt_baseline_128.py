#!/usr/bin/env python3
"""Confirm six reviewed readings, run four baseline cases, draft one supplement.
Explicit --confirm-cases and --provide-reviewed-explanation are required.
No deployment, teaching-rule approval, holdout execution or formal replay.
"""
import argparse,base64,copy,datetime as dt,fcntl,hashlib,json,os,sys,types,zlib
from pathlib import Path
EMBEDDED='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'
TRACES=['trace_9367aa581b6a428b8c02be699424e163','trace_8e1a6d9b10a5431dbee4f12f54df5ba3',
 'trace_a46182d860834b54a92b30e4c5e54b96','trace_ca32a7c36971403bae187e3b17e13a17',
 'trace_ae3db42a7c6b4fe589555578b635949a','trace_77cfc3162f5b45c3bc8bd35339a5035e']
APPROVED_DRAFT='draft_15eb1a11987f17c9a775f6cc813de5ce'
EXPLANATION=(
 'A folio addressed to Cedarline Services may be accepted for this precheck when the named guest matches the claimant, '
 'the employee-paid amount is explicitly identified, and that employee payment is marked PAID.\n'
 'Compare the claimed amount directly with that stated employee-paid amount, not the total lodging charge. '
 'A known mismatch is returned for correction.\n'
 'The company prepayment is not reimbursed to the employee. Its presence does not replace evidence of the employee’s own payment.\n'
 'Do not calculate or infer a missing payment allocation. Hold and request evidence that explicitly identifies the employee-paid amount and its payment status.\n'
 'Both hotel stay dates must match the approved stay dates. A changed stay still requires a manager’s decision; this clarification does not approve an extension.\n'
 'Matching evidence permits only READY_FOR_BUSINESS_APPROVAL in the isolated simulation, never final expense approval or payment.')
LABEL_NOTE='Private author-prepared targets under the complete reviewed policy, not model outputs. Baseline holds caused by incomplete policy are not unsafe actions; assess their compliance with the currently approved rules separately.'


def helper():
 raw=zlib.decompress(base64.b64decode(EMBEDDED))
 if hashlib.sha256(raw).hexdigest()!='f19a6915fc9f742a6a93293f99b8224663a4c4b91be0d8a1b54d89a7d8f49189':raise RuntimeError('Controller integrity failed')
 m=types.ModuleType('intake128_preserved');exec(compile(raw,'intake128-preserved','exec'),m.__dict__);return m


def usage(r,m,before,after,max_calls=11,max_decisions=8):
 calls=after['session']['calls']-before['session']['calls'];decisions=after['session']['decisions']-before['session']['decisions']
 b,a=before['budget'],after['budget'];daily=(a.get('day')==b.get('day') and a['decisions']-b['decisions']==decisions)
 if a.get('day')!=b.get('day'):
  daily=dt.date.fromisoformat(a['day'])>dt.date.fromisoformat(b['day']) and 0<=a['decisions']<=decisions and calls>0
 if (not 0<=decisions<=max_decisions or not decisions<=calls<=max_calls or a['calls']-b['calls']!=calls or not daily or
     after['additional_decisions_used']-before['additional_decisions_used']!=decisions or
     after['extra_retry_attempts']!=before['extra_retry_attempts'] or after['study']!=before['study'] or
     not b['spent_usd']<=a['spent_usd']<=100):raise r.Stop('USAGE_CHANGED','今回の限定検証以外の利用変化があります。')
 return calls,decisions


def cases_and_labels(intake,m):
 cases=[];labels=[]
 actions=['ready_for_business_approval','ready_for_business_approval','hold','hold','ready_for_business_approval','return_for_correction']
 effects={a['action_id']:{e['field_id']:e['value'] for e in a['effects']} for a in intake['approved_domain']['actions']}
 for index,(answer,doc) in enumerate(zip(intake['readings'],m.DOCS)):
  case=copy.deepcopy(answer['case']);case['initial_state']={'review_status':'NEW'};cases.append(case)
  labels.append({'case_id':case['case_id'],'expected_action_id':actions[index],'expected_state':effects[actions[index]],
    'critical_wrong_actions':['ready_for_business_approval'] if index in (2,3,5) else [],'rationale':LABEL_NOTE})
 return cases,labels


def unchanged(ws,intake):
 old=intake['approved_workspace']
 keys=('workspace_id','version','status','goal','source_ids','human_source_ids','sources','requirements_review',
       'extraction','domain','draft','draft_id','approved_count','frozen','freeze')
 return all(ws.get(k)==old.get(k) for k in keys)


def show(p):
 keys=('status','workspace_id','reviewer_name','confirmed_cases','run_id','baseline_results','baseline_rule_compliance',
       'question','teaching_id','proposed_rules','candidate_checks','model_calls','judgment_calls','before_ledger','after_ledger','error')
 print(json.dumps({k:p[k] for k in keys if k in p},ensure_ascii=False,indent=2),flush=True)


def run(api,root,r,reviewer,confirm=False,provide=False):
 root=Path(root);m=helper();checkpoint=root/'.jt/upgrades/1.0.28/baseline-teaching.json';out=root/'deliverables/release128/baseline'
 if not confirm or not provide or not reviewer.strip():raise r.Stop('REVIEW_REQUIRED','--confirm-cases --provide-reviewed-explanation と担当者名が必要です。')
 intake=r.load(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json');p=r.load(checkpoint)
 if (intake.get('status')!='READINGS_READY_FOR_REVIEW' or intake.get('approved_draft_id')!=APPROVED_DRAFT or
     intake.get('reviewer_name')!=reviewer or intake.get('code_hash')!=m.CODE_HASH or intake.get('workspace_id')!=m.WORKSPACE or
     [x.get('trace_id') for x in intake.get('readings',[])]!=TRACES or intake.get('model_calls')!=6 or
     intake.get('judgment_calls')!=0 or intake.get('case_confirmation_created') is not False):
  raise r.Stop('INTAKE_REQUIRED','今回確認した6件の保存結果と一致しません。')
 for answer,doc in zip(intake['readings'],m.DOCS):
  if (answer.get('case',{}).get('facts')!=doc['transcription'] or answer.get('case_id')!=doc['case_id'] or
      answer.get('split')!=doc['split'] or answer.get('domain_hash')!=m.digest(intake['approved_domain']) or
      answer.get('case',{}).get('initial_state')!={'review_status':None}):
   raise r.Stop('READING_CHANGED','読取結果・区分・承認版が変わっています。')
 if p and (p.get('intake_hash')!=m.digest(intake) or p.get('reviewer_name')!=reviewer):
  raise r.Stop('CHECKPOINT_CHANGED','再開元の読取結果か担当者が変わっています。')
 if p.get('status') in ('TEACHING_DRAFT_READY_FOR_REVIEW','FAILED'):
  show(p)
  if p['status']=='FAILED':raise r.Stop('BASELINE_GATE_FAILED','保存済みの停止結果です。追加実行は行いません。')
  return p
 health=api.call('/health')
 if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=(m.VERSION,m.CODE_HASH,'LIVE',100):
  raise r.Stop('DEPLOY_MISMATCH','既存の1.0.28・LIVE・上限を確認できません。')
 ws=api.call('/workspaces/'+m.WORKSPACE)
 if not unchanged(ws,intake):raise r.Stop('WORKSPACE_CHANGED','条件・資料が変更されています。')
 cases,labels=cases_and_labels(intake,m)
 if not p:
  if ws.get('case_ids') or ws.get('run_ids') or ws.get('question_ids') or ws.get('teaching_ids') or ws.get('history_ids')!=intake['approved_workspace'].get('history_ids'):
   raise r.Stop('WORKSPACE_CHANGED','想定外の案件・実行・補足・履歴があります。')
  p={'status':'PREPARED','workspace_id':m.WORKSPACE,'reviewer_name':reviewer,'intake_hash':m.digest(intake),
     'before':api.call('/recovery115'),'steps':{},'started_at':r.stamp(),'complete_policy_label_note':LABEL_NOTE}
  r.save(checkpoint,p);r.save(out/'reviewed-explanation.json',{'reviewer_name':reviewer,'human_text':EXPLANATION})
 def call(name,path,data):
  if name in p['steps']:return p['steps'][name]
  p['pending']=name;r.save(checkpoint,p)
  value=api.call(path,data,key='baseline128-'+name)
  p['steps'][name]=value;p.pop('pending',None);r.save(checkpoint,p);return value
 def current():
  value=api.call('/workspaces/'+m.WORKSPACE)
  if not unchanged(value,intake):raise r.Stop('WORKSPACE_CHANGED','実行中に条件・資料が変わりました。')
  return value
 try:
  for answer,case in zip(intake['readings'],cases):
   current()
   call('confirm-'+case['case_id'],'/cases/confirm',{'workspace_id':m.WORKSPACE,'case_draft_id':answer['case_draft_id'],
        'case':case,'reviewer_name':reviewer,'memo':'Reviewed against the fictional source PDF. Unknown facts stay null. NEW is only the isolated initial review state.'})
  ws=current()
  if ws.get('case_ids')!=[c['case_id'] for c in cases]:raise r.Stop('CASE_SET_CHANGED','確定した案件一覧が一致しません。')
  p['confirmed_cases']=6
  call('private-targets','/cases/import',{'workspace_id':m.WORKSPACE,'cases':cases,'expected':labels,
       'reviewer_name':reviewer,'memo':'Attach private complete-policy assessment targets; all six confirmed cases and their evidence hashes remain unchanged. '+LABEL_NOTE})
  if not p.get('run_id'):
   usage(r,m,p['before'],api.call('/recovery115'),0,0)
   run=call('create-run','/runs',{'workspace_id':m.WORKSPACE,'mode':'LIVE','arm':'C_JT_RULES','split':'dev','repeats':1,
      'case_ids':[c['case_id'] for c in cases[:4]],'reviewer_name':reviewer,'memo':'Baseline: four development cases under version 0, one pass each. No held-out case is executed.'})
   p['run_id']=run['run_id'];r.save(checkpoint,p)
  for index in range(4):
   if 'step-'+str(index) in p['steps']:continue
   current();value=call('step-'+str(index),'/runs/'+p['run_id']+'/step',{})
   view=api.call('/exports/'+p['run_id']);r.save(out/'baseline-run.json',view)
   if value.get('failed') or any(t['status'] in ('FAILED','CANCELLED') for t in view['tasks']):
    raise r.Stop('BASELINE_CASE_FAILED','案件実行が失敗しました。先へ進めず保存します。')
   expected_ids=[c['case_id'] for c in cases[:index+1]]
   if {t['case_id'] for t in view['tasks'] if t['status']=='COMPLETED'}!=set(expected_ids):
    raise r.Stop('BASELINE_PROGRESS_CHANGED','予定した1案件の完了を確認できません。')
   print(str(index+1)+'/4 補足前の実行結果を保存しました。',flush=True)
  view=api.call('/exports/'+p['run_id']);r.save(out/'baseline-run.json',view)
  from core.models import permitted,validate_domain,JTError
  rows=[]
  for task in view['tasks']:
   case=next(c for c in cases if c['case_id']==task['case_id']);expected=permitted(intake['approved_domain'],{**case['facts'],**case['initial_state']})[0]
   rows.append({'case_id':case['case_id'],'action':task['decision']['action_id'],'after_state':task['state'],
    'matches_current_rules':task['decision']['action_id']==expected,'trace_ids':task['trace_ids'],
    'raw_model_action':task.get('raw_decision',{}).get('action_id')})
  p['baseline_results']=rows;p['baseline_rule_compliance']=all(x['matches_current_rules'] for x in rows)
  if not p['baseline_rule_compliance']:raise r.Stop('BASELINE_ACTION_MISMATCH','実行結果が承認済み条件と一致しません。')
  if view['run']['dataset_hash']!=m.digest(cases[:4]) or view['run']['domain_hash']!=m.digest(intake['approved_domain']):
   raise r.Stop('BASELINE_CHANGED','実行した案件・条件のハッシュが一致しません。')
  call('fix-baseline','/history/fix',{'run_id':p['run_id'],'reviewer_name':reviewer,'memo':'Before task-owner clarification. Review current-rule compliance separately from complete-policy target metrics. '+LABEL_NOTE})
  q=call('question','/questions',{'run_id':p['run_id']});p['question']=q['question']
  if not set(q['question']['affected_dev_case_ids']).issubset({c['case_id'] for c in cases[:4]}):raise r.Stop('HOLDOUT_ISOLATION','質問に未使用案件が含まれています。')
  teaching=call('teaching-draft','/teachings',{'question_id':q['question']['question_id'],'base_version':0,'human_text':EXPLANATION})
  t=teaching['teaching'];p['teaching_id']=t['teaching_id'];p['proposed_rules']=t['proposed_rules']
  if t['approval_state']!='DRAFT' or t['base_domain_version']!=0 or any(x['approved_by'] is not None for x in t['proposed_rules']):
   raise r.Stop('TEACHING_STATE_CHANGED','補足の未承認案を確認できません。')
  merged=copy.deepcopy(intake['approved_domain']);ids={x['rule_id'] for x in t['proposed_rules']}
  merged['rules']=[x for x in merged['rules'] if x['rule_id'] not in ids]+t['proposed_rules']
  merged['source_hashes'][teaching['source_id']]=m.digest(EXPLANATION.encode())
  try:validate_domain(merged)
  except JTError as error:raise r.Stop(error.code,error.message) from error
  tests=[(c['case_id'],c['facts'],labels[i]['expected_action_id']) for i,c in enumerate(cases[:4])]
  for field,value in [('receipt_employee_paid_amount',None),('receipt_payment_status',None),('receipt_payment_status','UNPAID'),('actual_end_date','2026-09-11')]:
   tests.append(('dev02 boundary '+field+'='+str(value),{**cases[1]['facts'],field:value},'hold'))
  tests.append(('dev02 known amount mismatch',{**cases[1]['facts'],'claimed_amount':1},'return_for_correction'))
  p['candidate_checks']=[{'case':name,'expected_action':expected,'permitted_action':permitted(merged,facts)[0]} for name,facts,expected in tests]
  if any(x['expected_action']!=x['permitted_action'] for x in p['candidate_checks']):
   raise r.Stop('TEACHING_REQUIRES_REVIEW','補足条件案が開発案件・例外条件と一致しません。未承認で保存します。')
  ws=current()
  if ws['run_ids']!=[p['run_id']] or ws['question_ids']!=[q['question']['question_id']] or ws['teaching_ids']!=[t['teaching_id']] or ws['case_ids']!=[c['case_id'] for c in cases]:
   raise r.Stop('WORKSPACE_CHANGED','追加の実行や補足を検知しました。')
  p['status']='TEACHING_DRAFT_READY_FOR_REVIEW'
 except r.Stop as error:
  detail=getattr(error,'detail',{})
  if error.code=='NETWORK_INTERRUPTED' or detail.get('code')=='BUSY':
   raise r.Stop('BASELINE_PENDING','応答待ちです。同じコマンドで同じ要求の保存結果から再開します。') from error
  p.update(status='FAILED',error={'code':error.code,'message':str(error),**{k:detail[k] for k in ('request_id','diagnostic') if k in detail}})
 after=api.call('/recovery115');p.update(after=after,before_ledger=p['before']['budget'],after_ledger=after['budget'],checked_at=r.stamp())
 try:p['model_calls'],p['judgment_calls']=usage(r,m,p['before'],after)
 except r.Stop as error:p.update(status='FAILED',error={'code':error.code,'message':str(error)})
 r.save(checkpoint,p);r.save(out/'verification.json',p);show(p)
 if p['status']=='FAILED':raise r.Stop('BASELINE_GATE_FAILED','記録を保存して停止しました。新条件の承認・補足後の実行はしていません。')
 print('補足前4件・不足への質問・補足条件案を保存しました。補足条件は未承認です。未使用2件は実行していません。',flush=True)
 return p


def main():
 sys.dont_write_bytecode=True;parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--reviewer',required=True);parser.add_argument('--confirm-cases',action='store_true');parser.add_argument('--provide-reviewed-explanation',action='store_true');args=parser.parse_args()
 if not args.confirm_cases or not args.provide_reviewed_explanation:parser.error('Both explicit review flags are required')
 root=Path.cwd().resolve();m=helper();c=json.loads((root/'.jt/config.json').read_text());manifest=json.loads((root/'package-manifest.json').read_text())
 if c.get('project_id')!=m.PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=(m.VERSION,m.CODE_HASH):raise RuntimeError('Expected the installed Judgment Transfer 1.0.28 package')
 if Path(sys.prefix).resolve()!=(root/'.venv').resolve():
  exe=root/'.venv/bin/python'
  if not exe.is_file():raise RuntimeError('Existing .venv missing')
  os.execv(str(exe),[str(exe),str(Path(__file__).resolve()),*sys.argv[1:]])
 sys.path[:0]=[str(root),str(root/'app')]
 from steps import runbook as r
 r.integrity()
 with (root/'.jt/runbook.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
  run(r.API(),root,r,args.reviewer.strip(),args.confirm_cases,args.provide_reviewed_explanation)


if __name__=='__main__':
 try:main()
 except Exception as error:
  code=getattr(error,'code','BASELINE_STOPPED');message=str(error) if hasattr(error,'code') or isinstance(error,RuntimeError) else type(error).__name__
  sys.exit('STOP '+str(code)+' / '+message)

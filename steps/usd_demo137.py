"""One new USD demo: reviewed inputs, 4+4+2 executions, then verified publication."""
import copy
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'app')]
from core.models import digest, permitted, validate_domain


def immutable(view):
    return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}


def run(root, api, r, reviewer):
    root=Path(root);out=root/'deliverables/release137/usd';path=root/'.jt/upgrades/1.0.37/usd-demo.json'
    fixture=root/'app/fixtures/expense_review_usd'
    from steps.usd_recovery137 import seed
    p=seed(root,api,r,reviewer)
    if p.get('status')=='FAILED':raise r.Stop('USD_DEMO_STOPPED','保存済みの停止記録があります。新しい要求は送信しません。')
    if p and p.get('reviewer_name')!=reviewer:raise r.Stop('REVIEWER_CHANGED','保存済みの担当者名と一致しません。')
    if p.get('status')=='PASSED':
        print(json.dumps(p['report'],ensure_ascii=False,indent=2));return p
    from steps.usd_recovery137 import BoundedAPI,previous_records
    raw_api=api
    initial_calls,original_usd=previous_records(root,raw_api,r)
    api=BoundedAPI(raw_api,r,initial_calls)
    health=api.call('/health');manifest=r.load(root/'package-manifest.json')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=('1.0.37',manifest['code_hash'],'LIVE',100):
        raise r.Stop('DEPLOY_MISMATCH','1.0.37・LIVE・累計100ドル上限の反映が必要です。')
    if p['original_usd']!=original_usd or p['initial_usd_calls']!=initial_calls:
        raise r.Stop('USD_ORIGINAL_CHANGED','以前のUSD記録が変更されています。')
    def call(name,url,data=None,files=None):
        if name in p['steps']:return p['steps'][name]
        p['pending']=name;r.save(path,p)
        value=api.call(url,data,key='usd137-'+name,files=files)
        p['steps'][name]=value;p.pop('pending',None);r.save(path,p);return value
    def check_results(view,selected,targets):
        if view['run']['dataset_hash']!=digest(selected) or len(view['tasks'])!=len(selected):
            raise r.Stop('USD_CASE_SET_CHANGED','USDの案件・初期状態が一致しません。')
        for task,case,target in zip(view['tasks'],selected,targets):
            receipts=[v for v in view['receipts'] if v['task_id']==task['task_id']]
            if (task['status']!='COMPLETED' or task['case_id']!=case['case_id'] or
                task['decision']['action_id']!=target or task.get('raw_decision',{}).get('action_id')!=target or
                len(receipts)!=1 or receipts[0]['case_hash']!=digest(case) or receipts[0]['before_state']!=case['initial_state']):
                raise r.Stop('USD_RESULT_MISMATCH','実際の判断・実行結果が一致しません: '+case['case_id'])
    def execute(kind, selected, targets, split='dev'):
        if kind=='baseline':
            view=api.call('/exports/'+p['baseline_run_id']);check_results(view,selected,targets)
            if digest(immutable(view))!=p['baseline_hash']:raise r.Stop('USD_BASELINE_CHANGED','保存済みの補足前4件が変化しています。')
            return view
        data={'workspace_id':wid,'mode':'LIVE','arm':'C_JT_RULES','split':split,'repeats':1,
            'case_ids':[c['case_id'] for c in selected],'reviewer_name':reviewer,'memo':'New fictional USD inputs; historical JPY records are preserved.'}
        if kind=='after':data['baseline_run_id']=p['baseline_run_id']
        value=call('create-'+kind,'/runs',data);rid=value['run_id'];p[kind+'_run_id']=rid;r.save(path,p)
        for i in range(len(selected)):
            call(kind+'-'+str(i),'/runs/'+rid+'/step',{})
            view=api.call('/exports/'+rid);r.save(out/(kind+'.json'),view)
            if any(t['status']=='FAILED' for t in view['tasks']):raise r.Stop('USD_EXECUTION_FAILED','案件が停止しました。要求を再生成しません。')
            print(kind+' '+str(i+1)+'/'+str(len(selected))+' 保存済み',flush=True)
        view=api.call('/exports/'+rid);check_results(view,selected,targets)
        call('fix-'+kind,'/history/fix',{'run_id':rid,'reviewer_name':reviewer,'memo':'USD demo, '+kind+'. Same-case comparisons start from NEW; final expense approval remains human.'})
        return view
    try:
        grant=call('authorize','/validation123/authorize',{'max_cost_usd':100,'demo_revision':'USD_134','reviewer_name':reviewer,
            'memo':'Authorize the new USD dataset only: ten case executions, one question/guidance pair, at most 24 generation attempts. Preserve all previous counters and the cumulative USD100 ceiling.'})
        if grant.get('usd_demo_134',{}).get('additional_calls')!=24:raise r.Stop('USD_ALLOWANCE_REQUIRED','USD専用の一度限りの追加枠を確認できません。')
        domain=r.load(fixture/'domain_v0.json');cases=r.load(fixture/'cases.json');labels=r.load(fixture/'expected_private_to_scorer.json')
        policy=(fixture/'source_sop.txt').read_bytes()
        ws=call('workspace','/workspaces',{'goal':domain['goal']+' Currency: USD.'});wid=ws['workspace_id'];p['workspace_id']=wid;r.save(path,p)
        call('policy','/sources',{'workspace_id':wid,'source_id':'expense_sop'},('expense_policy_USD.txt','text/plain',policy))
        draft=call('draft','/domains/draft',{'workspace_id':wid,'domain':domain})
        if draft.get('origin')!='HUMAN_EDIT' or draft.get('domain')!=domain:raise r.Stop('USD_DRAFT_CHANGED','明示した条件案と一致しません。')
        call('approve','/domains/approve',{'draft_id':draft['draft_id'],'base_version':-1,'reviewer_name':reviewer,
            'memo':'Reviewed declarative conditions reused for the new fictional USD scenario. This is a human-prepared workflow, not a new AI-generated workflow.'})
        call('cases','/cases/import',{'workspace_id':wid,'cases':cases,'expected':labels,'reviewer_name':reviewer,
            'memo':'Confirmed author-prepared transcriptions of six newly generated USD PDFs. Not new AI PDF extraction. Private targets are stored separately and excluded from model prompts.'})
        baseline=execute('baseline',cases[:4],['ready_for_approval','hold_case','hold_case','hold_case'])
        p['baseline_hash']=digest(immutable(baseline));r.save(path,p)
        question=call('question','/questions',{'run_id':p['baseline_run_id']})
        explanation='\n'.join((fixture/'expert_teaching_reference.txt').read_text().splitlines()[2:])
        teaching=call('teaching','/teachings',{'question_id':question['question']['question_id'],'human_text':explanation,'base_version':0})
        candidate=copy.deepcopy(domain);proposed=teaching['teaching']['proposed_rules']
        replaced={v['rule_id'] for v in proposed}
        candidate['rules']=[v for v in candidate['rules'] if v['rule_id'] not in replaced]+proposed
        checks=[(c,t) for c,t in zip(cases[:4],['ready_for_approval','ready_for_approval','hold_case','hold_case'])]
        for field,value,target in [('employee_payment_amount_usd',None,'hold_case'),('employee_payment_status',None,'hold_case'),('employee_payment_status','UNPAID','hold_case'),('receipt_stay_end','2026-09-11','hold_case'),('claimed_amount_usd',1,'return_for_correction')]:
            c=copy.deepcopy(cases[1]);c['facts'][field]=value;checks.append((c,target))
        # Do not inspect holdout outcomes to repair or approve generated guidance.
        for c,target in checks:
            if permitted(candidate,{**c['facts'],**c['initial_state']})[0]!=target:
                raise r.Stop('USD_GUIDANCE_REQUIRES_REVIEW','追加条件が確認済みの判断内容と一致しません。承認せず停止します。')
        call('approve-teaching','/teachings/'+teaching['teaching']['teaching_id']+'/approve',{'base_version':0,'reviewer_name':reviewer,
            'memo':'Reviewed company-addressed receipt guidance against the owner explanation and four dev cases plus five missing-evidence/exception checks; no holdout-informed edit.'})
        after=execute('after',cases[:4],[v['expected_action_id'] for v in labels[:4]])
        freeze=call('freeze','/workspaces/freeze',{'workspace_id':wid,'reviewer_name':reviewer,'memo':'Freeze the new USD cases, private targets and approved guidance before first-use holdout execution.'})
        if freeze['dataset_hash']!=digest(cases) or freeze['label_hash']!=digest(labels):raise r.Stop('USD_FREEZE_CHANGED','固定した案件・評価条件が一致しません。')
        heldout=execute('holdout',cases[4:],[v['expected_action_id'] for v in labels[4:]],'holdout')
        for rid,expected in p['originals'].items():
            if digest(immutable(api.call('/exports/'+rid)))!=expected:raise r.Stop('HISTORICAL_RESULT_CHANGED','既存のJPY記録が変化しています。')
        after_usage=api.call('/recovery115');n=after_usage['session']['calls']-p['before']['session']['calls']
        total=after_usage['session']['calls']-initial_calls
        if previous_records(root,raw_api,r)!=(initial_calls,p['original_usd']):raise r.Stop('USD_ORIGINAL_CHANGED','以前のUSD記録が変更されています。')
        if not 2<=n<=24 or not 0<=total<=24 or after_usage['budget']['spent_usd']>100:raise r.Stop('USD_USAGE_CHANGED','今回の追加枠と利用量が一致しません。')
        data=call('publish','/demo/expense/publish',{'baseline_run_id':p['baseline_run_id'],'after_run_id':p['after_run_id'],
            'holdout_run_id':p['holdout_run_id'],'publish_fictional_usd_demo':True,'reviewer_name':reviewer})
        public=r.API(admin=False).call('/demo/expense')
        if public!=data:raise r.Stop('USD_DISPLAY_MISMATCH','公開デモと確定済みのUSD記録が一致しません。')
        p['status']='PASSED';p['report']={'status':'PASSED','currency':'USD','workspace_id':wid,'new_case_decisions':10,
            'model_attempts':n,'total_usd_attempts_including_previous':total,'original_usd_records_preserved':True,'saved_baseline_and_question_reused':True,'previous_failed_guidance_trace_preserved':True,'historical_jpy_preserved':True,'public_demo_verified':True,
            **{k:p[k] for k in ('baseline_run_id','after_run_id','holdout_run_id')},'ledger':after_usage['budget']}
        r.save(out/'evidence.json',data);r.save(out/'verification.json',p['report']);r.save(path,p)
        print(json.dumps(p['report'],ensure_ascii=False,indent=2),flush=True)
    except r.Stop as error:
        if error.code=='NETWORK_INTERRUPTED' or getattr(error,'detail',{}).get('code')=='BUSY':
            raise r.Stop('USD_PENDING','同じコマンドで同じ要求の保存結果から再開できます。') from error
        p['status']='FAILED';p['error']={'code':error.code,'message':str(error),**getattr(error,'detail',{})};r.save(path,p);r.save(out/'stopped.json',p)
        raise
    return p


if __name__=='__main__':
    import argparse,fcntl
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-usd-demo',action='store_true')
    parser.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if not args.reviewed_usd_demo or not args.reviewer.strip():parser.error('--reviewed-usd-demo and a reviewer name are required')
    from steps import runbook as r
    r.integrity()
    with (ROOT/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        try:run(ROOT,r.API(),r,args.reviewer.strip())
        except r.Stop as error:sys.exit('STOP '+error.code+' / '+str(error))

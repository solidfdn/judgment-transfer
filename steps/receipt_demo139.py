"""Create and verify the reviewed employee-addressed receipt scenario in a new workspace."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'app')]
from core.models import digest,permitted
from approved_execution import PROTOCOL
from expense_demo import recorded_decision_matches
SCENARIO='PERSONAL_RECEIPT_139'
OLD_RUNS=('run_ed781abd29baa3dfb53fe0bc0abb7937','run_42a670a9c5b1f941657e45d9c24738d6','run_c969c360a29e6cdc634ac209825b1c70',
          'run_57fe7a19c7969b02e7d682486661b640','run_8eddb91a8f57e4cf2b6b3694c94e3f7b','run_34c40b6d81dfc0c65333144d42f3162f')

def immutable(view):return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}

def guidance_checks(domain,cases):
    """Bounded development-only acceptance gate; no held-out cases or labels."""
    checks=[(c,t) for c,t in zip(cases,['ready_for_approval','ready_for_approval','hold_case','hold_case'])]
    for field,value,target in [('employee_payment_amount_usd',None,'hold_case'),('employee_payment_status',None,'hold_case'),
        ('employee_payment_status','UNPAID','hold_case'),('receipt_stay_end','2026-09-11','hold_case'),('receipt_stay_end',None,'hold_case'),
        ('receipt_addressee_name','Another Person','hold_case'),('claimed_amount_usd',1,'return_for_correction')]:
        c=copy.deepcopy(cases[1]);c['facts'][field]=value;checks.append((c,target))
    return [{'case_id':c['case_id'],'facts_hash':digest(c['facts']),'expected':t,
             'actual':permitted(domain,{**c['facts'],**c['initial_state']})[0]} for c,t in checks]

def run(root,api,r,reviewer):
    root=Path(root);path=root/'.jt/upgrades/1.0.39/receipt-demo.json';out=root/'deliverables/release139/receipts'
    fixture=root/'app/fixtures/expense_review_usd139';manifest=r.load(root/'package-manifest.json');p=r.load(path)
    if p.get('status')=='FAILED':raise r.Stop('RECEIPT_DEMO_STOPPED','停止記録を保持しています。新しい要求は自動送信しません。')
    if p and p.get('reviewer_name')!=reviewer:raise r.Stop('REVIEWER_CHANGED','保存済みの担当者名と一致しません。')
    health=api.call('/health')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=('1.0.39',manifest['code_hash'],'LIVE',100):
        raise r.Stop('DEPLOY_MISMATCH','1.0.39・LIVE・既存の累計100ドル上限を確認できません。')
    if p.get('status')=='PASSED':
        data=api.call('/demo/expense')
        if data!=p['steps']['publish']:raise r.Stop('PUBLICATION_CHANGED','保存済みの新しい公開デモと一致しません。')
        print(json.dumps(p['report'],ensure_ascii=False,indent=2),flush=True);return p
    if not p:
        grant=r.load(root/'.jt/upgrades/1.0.34/usd-demo.json').get('steps',{}).get('authorize',{})
        usage=api.call('/recovery115');remaining=grant.get('base_calls',0)+grant.get('additional_calls',0)-usage['session']['calls']
        if not grant.get('authorized') or grant.get('max_cost_usd')!=100 or remaining<4 or usage['budget']['spent_usd']>=100:
            raise r.Stop('ALLOWANCE_REQUIRED','既存の承認枠に最大4回分が残っていることを確認できません。上限は変更していません。')
        p={'status':'PREPARED','reviewer_name':reviewer,'scenario_id':SCENARIO,'started_at':r.stamp(),'steps':{},'before':usage,
           'grant_hash':digest(grant),'original_public':api.call('/demo/expense'),
           'originals':{rid:digest(immutable(api.call('/exports/'+rid))) for rid in OLD_RUNS}}
        r.save(path,p)
    def call(name,url,data=None,files=None):
        if name in p['steps']:return p['steps'][name]
        p['pending']=name;r.save(path,p)
        value=api.call(url,data,key='receipt139-'+name,files=files)
        p['steps'][name]=value;p.pop('pending',None);r.save(path,p);return value
    def usage_check(execution_before=None):
        value=api.call('/recovery115');n=value['session']['calls']-p['before']['session']['calls']
        if not 0<=n<=4 or value['budget']['spent_usd']>100 or value['session']['decisions']!=p['before']['session']['decisions']:
            raise r.Stop('UNEXPECTED_MODEL_USAGE','今回の最大4回・既存の100ドル上限と一致しません。')
        if execution_before and any(value[k]!=execution_before[k] for k in ('session','budget')):
            raise r.Stop('UNEXPECTED_EXECUTION_USAGE','承認条件の実行中にモデル利用量が変化しました。')
        return value
    domain=r.load(fixture/'domain_v0.json');cases=r.load(fixture/'cases.json');labels=r.load(fixture/'expected_private_to_scorer.json')
    def execute(kind,selected,targets,version,split='dev'):
        before=usage_check()
        body={'workspace_id':wid,'mode':'LIVE','arm':'C_JT_RULES','approved_version':version,'split':split,'repeats':1,
              'case_ids':[c['case_id'] for c in selected],'reviewer_name':reviewer,
              'memo':'Receipt-acceptance revision 139. Same approved-rule engine; start each case from NEW. Preserve all previous scenarios.'}
        if kind=='after':body['baseline_run_id']=p['baseline_run_id']
        rid=call('create-'+kind,'/runs',body)['run_id'];p[kind+'_run_id']=rid;r.save(path,p)
        for i in range(len(selected)):
            value=call(kind+'-'+str(i),'/runs/'+rid+'/step',{})
            view=api.call('/exports/'+rid);r.save(out/(kind+'.json'),view)
            if value.get('failed') or any(t['status']=='FAILED' for t in view['tasks']):
                raise r.Stop('RECEIPT_EXECUTION_FAILED','実行が停止しました。成功・失敗記録を保存し、自動再実行しません。')
            print(kind+' '+str(i+1)+'/'+str(len(selected))+' 保存済み（モデル呼出しなし）',flush=True)
        if (view['run'].get('execution_protocol')!=PROTOCOL or view['run']['code_hash']!=manifest['code_hash'] or
            view['run']['domain']['version']!=version or view['run']['dataset_hash']!=digest(selected) or
            len(view['tasks'])!=len(selected) or not view['metrics']['complete'] or view['metrics']['stale']):
            raise r.Stop('RECEIPT_RESULT_MISMATCH','実行方式・承認版・対象案件が一致しません。')
        for task,case,target in zip(view['tasks'],selected,targets):
            receipts=[v for v in view['receipts'] if v['task_id']==task['task_id']]
            if (task['status']!='COMPLETED' or task['case_id']!=case['case_id'] or not recorded_decision_matches(view,task,case,target) or
                len(receipts)!=1 or receipts[0]['case_hash']!=digest(case) or receipts[0]['before_state']!=case['initial_state']):
                raise r.Stop('RECEIPT_RESULT_MISMATCH','判断・実行記録が一致しません: '+case['case_id'])
        usage_check(before)
        fixed=call('fix-'+kind,'/history/fix',{'run_id':rid,'reviewer_name':reviewer,
             'memo':'Receipt revision 139: '+kind+'. Documentary precheck only; final business approval remains human.'})
        if fixed.get('reviewer_name')!=reviewer or not fixed.get('recorded_at'):
            raise r.Stop('HISTORY_NOT_FIXED','担当者名・日時付きの履歴を確認できません。')
        return view
    try:
        print('新しい規程と6案件を別の業務として保存します。既存の履歴・承認・利用量を引き継ぎます。',flush=True)
        wid=call('workspace','/workspaces',{'goal':domain['goal']+' Currency: USD. Employee-addressed receipt acceptance, revision 139.'})['workspace_id']
        p['workspace_id']=wid;r.save(path,p)
        call('policy','/sources',{'workspace_id':wid,'source_id':'expense_sop'},('receipt_policy_139.txt','text/plain',(fixture/'source_sop.txt').read_bytes()))
        draft=call('draft','/domains/draft',{'workspace_id':wid,'domain':domain})
        if draft.get('origin')!='HUMAN_EDIT' or draft.get('domain')!=domain:raise r.Stop('RECEIPT_DRAFT_CHANGED','担当者確認用の初期条件と一致しません。')
        call('approve','/domains/approve',{'draft_id':draft['draft_id'],'base_version':-1,'reviewer_name':reviewer,
             'memo':'Reviewed original policy: company-addressed receipts accepted; employee-addressed acceptance is not yet specified. Human-prepared declarative conditions, not AI-generated.'})
        call('cases','/cases/import',{'workspace_id':wid,'cases':cases,'expected':labels,'reviewer_name':reviewer,
             'memo':'Reviewed exact transcriptions of the six revised fictional USD PDFs. Not fresh AI extraction. Private expected outcomes are excluded from model prompts.'})
        execute('baseline',cases[:4],['ready_for_approval','hold_case','hold_case','hold_case'],0)
        print('新しい規程から確認質問と補足条件案を作成します（各1要求、内部生成は合計最大4回）。',flush=True)
        question=call('question','/questions',{'run_id':p['baseline_run_id']});usage_check()
        q=question['question']
        if q['affected_dev_case_ids']!=[cases[1]['case_id']] or not q.get('source_refs'):
            raise r.Stop('QUESTION_REQUIRES_REVIEW','質問がSamの本人宛て領収書の不足条件と対応していません。保存して停止します。')
        explanation='\n'.join((fixture/'expert_teaching_reference.txt').read_text().splitlines()[2:])
        teaching=call('teaching','/teachings',{'question_id':q['question_id'],'human_text':explanation,'base_version':0});usage_check()
        proposed=teaching['teaching']['proposed_rules'];candidate=copy.deepcopy(domain)
        replaced={v['rule_id'] for v in proposed};candidate['rules']=[v for v in candidate['rules'] if v['rule_id'] not in replaced]+proposed
        # Initial policy checks remain intact. Accept only new, evidence-backed receipt conditions.
        if replaced.intersection(v['rule_id'] for v in domain['rules']) or not proposed:
            raise r.Stop('GUIDANCE_REQUIRES_REVIEW','補足案が既存条件を置換しています。承認せず停止します。')
        gate=guidance_checks(candidate,cases[:4]);r.save(out/'guidance-review.json',{'checks':gate,'teaching':teaching})
        if any(v['actual']!=v['expected'] for v in gate):raise r.Stop('GUIDANCE_REQUIRES_REVIEW','補足条件案が確認済みの受付条件と一致しません。承認せず停止します。')
        call('approve-teaching','/teachings/'+teaching['teaching']['teaching_id']+'/approve',{'base_version':0,'reviewer_name':reviewer,
             'memo':'Approved the supplied explanation and its derived employee-addressed receipt conditions after four dev cases and seven boundary checks. Existing payment/date checks retained. No holdout used to repair the proposal.'})
        execute('after',cases[:4],[v['expected_action_id'] for v in labels[:4]],1)
        frozen=call('freeze','/workspaces/freeze',{'workspace_id':wid,'reviewer_name':reviewer,
             'memo':'Lock the six revised cases, private targets and approved conditions before first-use holdout execution.'})
        if frozen['dataset_hash']!=digest(cases) or frozen['label_hash']!=digest(labels):raise r.Stop('DATASET_CHANGED','固定した案件・評価条件が一致しません。')
        execute('holdout',cases[4:],[v['expected_action_id'] for v in labels[4:]],1,'holdout')
        for rid,expected in p['originals'].items():
            if digest(immutable(api.call('/exports/'+rid)))!=expected:raise r.Stop('HISTORICAL_RESULT_CHANGED','以前の検証記録が変化しています。')
        usage=usage_check();attempts=usage['session']['calls']-p['before']['session']['calls']
        if not 2<=attempts<=4:raise r.Stop('PREPARATION_USAGE_MISMATCH','新しい質問・補足案の生成記録と一致しません。')
        if 'publish' not in p['steps'] and api.call('/demo/expense')!=p['original_public']:
            raise r.Stop('PUBLICATION_CHANGED','検証中に公開デモが変化しました。上書きせず停止します。')
        data=call('publish','/demo/expense/publish',{'scenario_id':SCENARIO,'publish_fictional_usd_demo':True,'reviewer_name':reviewer,
             **{k+'_run_id':p[k+'_run_id'] for k in ('baseline','after','holdout')}})
        if api.call('/demo/expense')!=data or data.get('scenario_id')!=SCENARIO or data['model_calls']!=0:
            raise r.Stop('PUBLIC_DEMO_MISMATCH','新しい公開デモと実行記録が一致しません。')
        report={'status':'PASSED','scenario_id':SCENARIO,'currency':'USD','workspace_id':wid,'case_executions':10,
                'preparation_model_attempts':attempts,'execution_model_calls':0,'same_code_before_after':True,
                'prior_results_preserved':True,'public_demo_verified':True,'reviewer_name':reviewer,
                **{k+'_run_id':p[k+'_run_id'] for k in ('baseline','after','holdout')},'ledger':usage['budget']}
        p.update(status='PASSED',report=report);r.save(path,p);r.save(out/'verification.json',report);r.save(out/'evidence.json',data)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    except r.Stop as error:
        if error.code=='NETWORK_INTERRUPTED' or getattr(error,'detail',{}).get('code')=='BUSY':raise
        p.update(status='FAILED',error={'code':error.code,'message':str(error),'detail':getattr(error,'detail',{})})
        r.save(path,p);r.save(out/'stopped.json',p);raise
    return p

if __name__=='__main__':
    import argparse,fcntl
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reviewed-receipt-demo',action='store_true');parser.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if not args.reviewed_receipt_demo or not args.reviewer.strip():parser.error('Reviewed receipt demo and reviewer required')
    from steps import runbook as r
    r.integrity()
    with (ROOT/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        try:run(ROOT,r.API(),r,args.reviewer.strip())
        except r.Stop as error:sys.exit('STOP '+error.code+' / '+str(error))

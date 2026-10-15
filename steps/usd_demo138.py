"""Replay existing approved USD versions under one engine; zero model requests."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'app')]
from core.models import digest
from approved_execution import PROTOCOL
from steps.approved_stop135 import immutable,previous_records

WORKSPACE='ws_50ff4e8beabbf2fbbc101163b5a9fc3a'
OLD_BASELINE='run_addccfdf5da82ce6cb9179c0f006939a'
OLD_AFTER='run_aaf964bd46dc94812905f19e0e93f640'


def run(root,api,r,reviewer):
    root=Path(root);path=root/'.jt/upgrades/1.0.38/usd-demo.json';out=root/'deliverables/release138/usd'
    oldpath=root/'.jt/upgrades/1.0.37/usd-demo.json';old=r.load(oldpath)
    if (old.get('status')!='FAILED' or old.get('pending')!='after-1' or old.get('reviewer_name')!=reviewer or
        old.get('workspace_id')!=WORKSPACE or old.get('baseline_run_id')!=OLD_BASELINE or old.get('after_run_id')!=OLD_AFTER):
        raise r.Stop('USD_ORIGIN_CHANGED','確認済みの1.0.37停止記録と一致しません。新しいモデル要求は送信しません。')
    health=api.call('/health');manifest=r.load(root/'package-manifest.json')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'))!=('1.0.38',manifest['code_hash'],'LIVE'):
        raise r.Stop('DEPLOY_MISMATCH','1.0.38のLIVE反映が必要です。')
    p=r.load(path)
    if p.get('status')=='FAILED':raise r.Stop('USD_DEMO_STOPPED','保存済みの停止記録があります。自動再試行はしません。')
    if p and (p.get('origin_hash')!=digest(oldpath.read_bytes()) or p.get('reviewer_name')!=reviewer):
        raise r.Stop('USD_ORIGIN_CHANGED','再開元または担当者名が変わっています。')
    if p.get('status')=='PASSED':
        print(json.dumps(p['report'],ensure_ascii=False,indent=2),flush=True);return p
    if not p:
        ws=api.call('/workspaces/'+WORKSPACE)
        approval=old['steps']['approve-teaching']['domain']
        if (ws.get('version')!=1 or ws.get('frozen') or ws.get('run_ids')!=[OLD_BASELINE,OLD_AFTER] or
            ws.get('domain')!=approval or ws.get('approved_count')!=1):
            raise r.Stop('USD_APPROVAL_CHANGED','保存済みの承認条件と業務の状態が一致しません。')
        views={rid:api.call('/exports/'+rid) for rid in (OLD_BASELINE,OLD_AFTER)}
        if ([t['status'] for t in views[OLD_BASELINE]['tasks']]!=['COMPLETED']*4 or
            [t['status'] for t in views[OLD_AFTER]['tasks']]!=['COMPLETED','FAILED','PENDING','PENDING']):
            raise r.Stop('USD_ORIGIN_CHANGED','以前の成功・失敗・未処理記録が変化しています。')
        initial,original=previous_records(root,api,r)
        p={'status':'PREPARED','reviewer_name':reviewer,'origin_hash':digest(oldpath.read_bytes()),'workspace_id':WORKSPACE,
            'before':api.call('/recovery115'),'initial_usd_calls':initial,'original_usd':original,
            'preserved':{rid:digest(immutable(v)) for rid,v in views.items()},'steps':{}}
        for rid,v in views.items():r.save(out/('preserved-'+rid+'.json'),v)
        r.save(path,p)
    def call(name,url,data):
        if name not in p['steps']:
            p['pending']=name;r.save(path,p)
            p['steps'][name]=api.call(url,data,key='usd138-'+name)
            p.pop('pending',None);r.save(path,p)
        return p['steps'][name]
    def unchanged_usage():
        current=api.call('/recovery115')
        if any(p['before'].get(k)!=current.get(k) for k in ('session','budget')):
            raise r.Stop('UNEXPECTED_MODEL_USAGE','この検証中にモデル利用量が変化しました。公開せず停止します。')
        return current
    fixture=root/'app/fixtures/expense_review_usd';cases=r.load(fixture/'cases.json');labels=r.load(fixture/'expected_private_to_scorer.json')
    def execute(kind,selected,targets,version,split='dev'):
        body={'workspace_id':WORKSPACE,'mode':'LIVE','arm':'C_JT_RULES','approved_version':version,'split':split,'repeats':1,
            'case_ids':[c['case_id'] for c in selected],'reviewer_name':reviewer,
            'memo':'Replay saved approved version '+str(version)+' with the same rule engine. Prior model runs remain separate.'}
        if kind=='after':body['baseline_run_id']=p['baseline_run_id']
        created=call('create-'+kind,'/runs',body);rid=created['run_id'];p[kind+'_run_id']=rid;r.save(path,p)
        for i in range(len(selected)):
            result=call(kind+'-'+str(i),'/runs/'+rid+'/step',{})
            if result.get('failed'):raise r.Stop('USD_EXECUTION_FAILED',str(result.get('error')))
            print(kind+' '+str(i+1)+'/'+str(len(selected))+' 保存済み（モデル呼出しなし）',flush=True)
        view=api.call('/exports/'+rid);r.save(out/(kind+'.json'),view)
        from expense_demo import recorded_decision_matches
        if (view['run'].get('execution_protocol')!=PROTOCOL or view['run']['code_hash']!=manifest['code_hash'] or
            view['run']['domain']['version']!=version or view['run']['dataset_hash']!=digest(selected) or
            not view['metrics']['complete'] or view['metrics']['stale'] or len(view['tasks'])!=len(selected)):
            raise r.Stop('USD_RESULT_MISMATCH','実行方式・承認版・案件が一致しません。')
        for task,case,target in zip(view['tasks'],selected,targets):
            receipts=[v for v in view['receipts'] if v['task_id']==task['task_id']]
            if (task['status']!='COMPLETED' or task['case_id']!=case['case_id'] or
                not recorded_decision_matches(view,task,case,target) or len(receipts)!=1 or
                receipts[0]['case_hash']!=digest(case) or receipts[0]['before_state']!=case['initial_state']):
                raise r.Stop('USD_RESULT_MISMATCH','判断・実行記録が一致しません: '+case['case_id'])
        unchanged_usage()
        call('fix-'+kind,'/history/fix',{'run_id':rid,'reviewer_name':reviewer,
            'memo':'Approved workflow version replay, '+kind+'. Deterministic rule execution, not fresh model judgment; final business approval remains human.'})
        return view
    try:
        print('保存済みの承認版0・1を同じ実行方式で比較します。資料・質問・条件案の再生成と再承認は0回です。',flush=True)
        execute('baseline',cases[:4],['ready_for_approval','hold_case','hold_case','hold_case'],0)
        execute('after',cases[:4],[v['expected_action_id'] for v in labels[:4]],1)
        freeze=call('freeze','/workspaces/freeze',{'workspace_id':WORKSPACE,'reviewer_name':reviewer,
            'memo':'Freeze existing USD cases and approved guidance before their first rule-engine holdout execution.'})
        if freeze['dataset_hash']!=digest(cases) or freeze['label_hash']!=digest(labels):
            raise r.Stop('USD_FREEZE_CHANGED','案件と評価条件が一致しません。')
        execute('holdout',cases[4:],[v['expected_action_id'] for v in labels[4:]],1,'holdout')
        for rid,value in p['preserved'].items():
            if digest(immutable(api.call('/exports/'+rid)))!=value:raise r.Stop('HISTORICAL_RESULT_CHANGED','以前の記録が変化しました。')
        if previous_records(root,api,r)!=(p['initial_usd_calls'],p['original_usd']):
            raise r.Stop('HISTORICAL_RESULT_CHANGED','初期USD記録が変化しました。')
        usage=unchanged_usage()
        data=call('publish','/demo/expense/publish',{**{k+'_run_id':p[k+'_run_id'] for k in ('baseline','after','holdout')},
            'publish_fictional_usd_demo':True,'reviewer_name':reviewer})
        if r.API(admin=False).call('/demo/expense')!=data or data.get('execution_protocol')!=PROTOCOL or data['model_calls']!=0:
            raise r.Stop('USD_DISPLAY_MISMATCH','公開デモと実行記録が一致しません。')
        report={'status':'PASSED','currency':'USD','execution_protocol':PROTOCOL,'case_executions':10,'new_model_calls':0,
            'new_approvals':0,'same_code_before_after':True,'previous_results_and_failures_preserved':True,'public_demo_verified':True,
            **{k+'_run_id':p[k+'_run_id'] for k in ('baseline','after','holdout')},
            'total_usd_attempts_including_previous':usage['session']['calls']-p['initial_usd_calls'],'ledger':usage['budget']}
        p.update(status='PASSED',report=report);r.save(path,p);r.save(out/'verification.json',report);r.save(out/'evidence.json',data)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    except r.Stop as error:
        if error.code=='NETWORK_INTERRUPTED' or getattr(error,'detail',{}).get('code')=='BUSY':raise
        p.update(status='FAILED',error={'code':error.code,'message':str(error)});r.save(path,p);r.save(out/'stopped.json',p);raise
    return p


if __name__=='__main__':
    import argparse,fcntl
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reviewed-usd-demo',action='store_true');parser.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if not args.reviewed_usd_demo or not args.reviewer.strip():parser.error('--reviewed-usd-demo and reviewer required')
    from steps import runbook as r
    r.integrity()
    with (ROOT/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        try:run(ROOT,r.API(),r,args.reviewer.strip())
        except r.Stop as error:sys.exit('STOP '+error.code+' / '+str(error))

"""Bounded USD recovery and a live zero-model approved-stop check."""
import json
import time
from pathlib import Path
from core.models import digest


def immutable(view):
    return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}


def previous_records(root,api,r):
    records={};initial=None
    for name in ('usd-demo.json','usd-demo-resume1.json'):
        path=Path(root)/'.jt/upgrades/1.0.34'/name
        if not path.is_file():continue
        p=r.load(path)
        if name=='usd-demo.json':initial=p.get('before',{}).get('session',{}).get('calls')
        records['checkpoint:'+name]=digest(path.read_bytes())
        for kind in ('baseline','after','holdout'):
            rid=p.get(kind+'_run_id')
            if not rid:continue
            view=api.call('/exports/'+rid)
            if any(t['status']=='LEASED' and t.get('lease_until',0)>time.time() for t in view['tasks']):
                raise r.Stop('USD_STILL_RUNNING','先の案件がまだ処理中です。保存記録は変更せず停止します。')
            records[rid]=digest(immutable(view))
    if type(initial) is not int:raise r.Stop('USD_ORIGIN_MISSING','最初のUSD検証の利用量記録が必要です。')
    return initial,records


class BoundedAPI:
    def __init__(self,api,r,initial_calls):self.api,self.r,self.initial_calls=api,r,initial_calls
    def call(self,path,data=None,key=None,files=None):
        attempts=2 if path.endswith('/step') or path=='/questions' else 1 if path=='/teachings' else 0
        if data is not None and attempts:
            used=self.api.call('/recovery115')['session']['calls']-self.initial_calls
            if used<0 or used+attempts>24:
                raise self.r.Stop('USD_ATTEMPT_LIMIT','最初のUSD検証を含む24回の枠内で続行できません。追加要求は送りません。')
        return self.api.call(path,data,key=key,files=files)


def verify_zero_model_stop(root,api,r,reviewer):
    root=Path(root);path=root/'.jt/upgrades/1.0.35/approved-stop.json';p=r.load(path)
    if p.get('status')=='PASSED':return p['report']
    if p.get('status')=='FAILED':raise r.Stop('APPROVED_STOP_FAILED','保存済みの確認失敗があります。自動再実行はしません。')
    if p and p.get('reviewer_name')!=reviewer:raise r.Stop('REVIEWER_CHANGED','確認担当者名が一致しません。')
    if not p:
        p={'reviewer_name':reviewer,'steps':{},'before':api.call('/recovery115')};r.save(path,p)
    def call(name,url,data,files=None):
        if name not in p['steps']:
            p['steps'][name]=api.call(url,data,key='approved-stop135-'+name,files=files);r.save(path,p)
        return p['steps'][name]
    try:
        fixture=root/'app/fixtures/expense_review_usd';domain=r.load(fixture/'domain_v0.json')
        case=r.load(fixture/'cases.json')[3];label=r.load(fixture/'expected_private_to_scorer.json')[3]
        wid=call('workspace','/workspaces',{'goal':'Verify the approved changed-stay stop without a model request.'})['workspace_id']
        call('policy','/sources',{'workspace_id':wid,'source_id':'expense_sop'},('expense_policy_USD.txt','text/plain',(fixture/'source_sop.txt').read_bytes()))
        draft=call('draft','/domains/draft',{'workspace_id':wid,'domain':domain})
        call('approve','/domains/approve',{'draft_id':draft['draft_id'],'base_version':-1,'reviewer_name':reviewer,'memo':'Check the existing approved changed-stay stop before USD comparison.'})
        call('case','/cases/import',{'workspace_id':wid,'cases':[case],'expected':[label],'reviewer_name':reviewer,'memo':'Same reviewed extended-stay USD document transcription.'})
        run=call('run','/runs',{'workspace_id':wid,'mode':'LIVE','arm':'C_JT_RULES','split':'dev','repeats':1,'case_ids':[case['case_id']],'reviewer_name':reviewer})
        call('step','/runs/'+run['run_id']+'/step',{})
        view=api.call('/exports/'+run['run_id']);task=view['tasks'][0]
        from expense_demo import recorded_decision_matches
        after=api.call('/recovery115')
        if (len(view['tasks'])!=1 or task['status']!='COMPLETED' or task.get('decision_origin')!='APPROVED_RULE' or
            task['state']!=label['expected_state'] or not recorded_decision_matches(view,task,case,'hold_case') or
            len(view['receipts'])!=1 or view['receipts'][0]['case_hash']!=digest(case) or
            any(p['before'].get(k)!=after.get(k) for k in ('session','budget'))):
            raise r.Stop('APPROVED_STOP_FAILED','承認済み条件・実行結果・モデル呼び出し0回の確認が一致しません。')
        call('fix','/history/fix',{'run_id':run['run_id'],'reviewer_name':reviewer,'memo':'Verified approved changed-stay stop; no model request, no expense approval or payment.'})
        report={'status':'PASSED','check':'approved_changed_stay_stop','run_id':run['run_id'],
            'decision_origin':'APPROVED_RULE','new_model_calls':0,'state':task['state']}
        p.update(status='PASSED',report=report);r.save(path,p)
        r.save(root/'deliverables/release135/approved-stop-export.json',view)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True);return report
    except r.Stop as error:
        if error.code=='NETWORK_INTERRUPTED' or getattr(error,'detail',{}).get('code')=='BUSY':raise
        p.update(status='FAILED',error={'code':error.code,'message':str(error)});r.save(path,p);raise

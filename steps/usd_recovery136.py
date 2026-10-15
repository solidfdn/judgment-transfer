"""Preserve the inspected guidance failure and reuse completed USD preparation."""
import copy
from pathlib import Path
from core.models import digest
from steps.approved_stop135 import previous_records

BASELINE='run_addccfdf5da82ce6cb9179c0f006939a'
WORKSPACE='ws_50ff4e8beabbf2fbbc101163b5a9fc3a'
FAILED_TRACE='trace_ab46f91d01d04b8089c69649def15182'
BASELINE_CODE='f4b530aabfbec8766e476e83e7a02e2ed3b13412c8d52fc6e435871a18cc5a1e'


class BoundedAPI:
    def __init__(self,api,r,initial_calls):self.api,self.r,self.initial_calls=api,r,initial_calls
    def call(self,path,data=None,key=None,files=None):
        attempts=2 if path.endswith('/step') or path in ('/questions','/teachings') else 0
        if data is not None and attempts:
            used=self.api.call('/recovery115')['session']['calls']-self.initial_calls
            if used<0 or used+attempts>24:
                raise self.r.Stop('USD_ATTEMPT_LIMIT','最初のUSD検証を含む24回の枠内で続行できません。追加要求は送りません。')
        return self.api.call(path,data,key=key,files=files)


def seed(root,api,r,reviewer):
    root=Path(root);old_path=root/'.jt/upgrades/1.0.35/usd-demo.json'
    new_path=root/'.jt/upgrades/1.0.36/usd-demo.json';old=r.load(old_path)
    error=old.get('error',{});diagnostic=error.get('diagnostic',{})
    if (old.get('status')!='FAILED' or old.get('pending')!='teaching' or old.get('reviewer_name')!=reviewer or
        old.get('workspace_id')!=WORKSPACE or old.get('baseline_run_id')!=BASELINE or
        diagnostic.get('trace_id')!=FAILED_TRACE or error.get('code')!='MODEL_FAILED' or
        'question' not in old.get('steps',{}) or 'teaching' in old.get('steps',{}) or
        old.get('after_run_id') or old.get('holdout_run_id')):
        raise r.Stop('USD_RECOVERY_ORIGIN_CHANGED','今回確認した条件案生成の停止記録と一致しません。')
    trace=r.load(root/'deliverables/release135/usd/failed-generation-trace.json')
    if (trace.get('trace_id')!=FAILED_TRACE or trace.get('purpose')!='draft_rules' or 'result' in trace or
        len(trace.get('attempts',[]))!=1 or trace['attempts'][0].get('provider_code')!='504'):
        raise r.Stop('USD_FAILURE_TRACE_REQUIRED','保存済みの504診断記録が必要です。')
    guard=r.load(root/'.jt/upgrades/1.0.35/approved-stop.json')
    if guard.get('status')!='PASSED' or guard.get('report',{}).get('new_model_calls')!=0:
        raise r.Stop('APPROVED_STOP_REQUIRED','合格済みのモデル0回での停止確認が必要です。')
    view=api.call('/exports/'+BASELINE)
    immutable={k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}
    if view['run']['code_hash']!=BASELINE_CODE or digest(immutable)!=old.get('baseline_hash') or any(t['status']!='COMPLETED' for t in view['tasks']):
        raise r.Stop('USD_BASELINE_CHANGED','保存済みの補足前4件が変化しています。')
    origin={'checkpoint_hash':digest(old_path.read_bytes()),'baseline_hash':digest(immutable),'failed_trace_hash':digest(trace),
        'failed_trace_id':FAILED_TRACE,'previous_request_id':error.get('request_id')}
    current=r.load(new_path)
    if current:
        if current.get('recovery_origin')!=origin:raise r.Stop('USD_RECOVERY_ORIGIN_CHANGED','再開元の記録が変化しています。')
        return current
    ws=api.call('/workspaces/'+WORKSPACE)
    qid=old['steps']['question']['question']['question_id']
    if ws.get('version')!=0 or ws.get('frozen') or ws.get('teaching_ids') or ws.get('run_ids')!=[BASELINE] or qid not in ws.get('question_ids',[]):
        raise r.Stop('USD_WORKSPACE_CHANGED','停止後に業務条件または承認状態が変更されています。')
    new=copy.deepcopy(old);new.update(status='PREPARED',recovery_origin=origin,prior_failure=error)
    new.pop('error',None);new.pop('pending',None)
    r.save(new_path,new)
    print('保存済みの補足前4件・確認質問を引き継ぎます。案件と質問の再生成は0回です。',flush=True)
    return new

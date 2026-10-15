"""Continue after the 1.0.36 run-start guard without regenerating guidance."""
import copy
from pathlib import Path
from core.models import digest
from steps.usd_recovery136 import BoundedAPI,previous_records,BASELINE,WORKSPACE,BASELINE_CODE


def seed(root,api,r,reviewer):
    root=Path(root);old_path=root/'.jt/upgrades/1.0.36/usd-demo.json'
    path=root/'.jt/upgrades/1.0.37/usd-demo.json';old=r.load(old_path)
    error=old.get('error',{});steps=old.get('steps',{})
    if (old.get('status')!='FAILED' or old.get('pending')!='create-after' or error.get('code')!='RUN_PROTOCOL_CHANGED' or
        old.get('reviewer_name')!=reviewer or old.get('workspace_id')!=WORKSPACE or old.get('baseline_run_id')!=BASELINE or
        not all(k in steps for k in ('question','teaching','approve-teaching')) or 'create-after' in steps or
        old.get('after_run_id') or old.get('holdout_run_id')):
        raise r.Stop('USD_RECOVERY_ORIGIN_CHANGED','今回の補足後実行の開始停止と一致しません。新しい生成要求は送りません。')
    view=api.call('/exports/'+BASELINE)
    immutable={k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}
    if view['run']['code_hash']!=BASELINE_CODE or digest(immutable)!=old.get('baseline_hash'):
        raise r.Stop('USD_BASELINE_CHANGED','保存済みの補足前4件が変化しています。')
    tid=steps['teaching']['teaching']['teaching_id']
    origin={'checkpoint_hash':digest(old_path.read_bytes()),'baseline_hash':digest(immutable),
        'approved_teaching_id':tid,'previous_request_id':error.get('request_id')}
    current=r.load(path)
    if current:
        if current.get('run_start_recovery_origin')!=origin:raise r.Stop('USD_RECOVERY_ORIGIN_CHANGED','再開元が変化しています。')
        return current
    ws=api.call('/workspaces/'+WORKSPACE)
    teachings={t['teaching']['teaching_id']:t for t in ws.get('teachings',[])}
    if (ws.get('version')!=1 or ws.get('frozen') or ws.get('run_ids')!=[BASELINE] or ws.get('teaching_ids')!=[tid] or
        tid not in teachings or teachings[tid]['teaching']['approval_state']!='APPROVED' or
        ws.get('domain')!=steps['approve-teaching'].get('domain')):
        raise r.Stop('USD_APPROVAL_CHANGED','保存済みの承認条件と現在の業務条件が一致しません。')
    new=copy.deepcopy(old);new.update(status='PREPARED',run_start_recovery_origin=origin)
    new['prior_failures']=[old.get('prior_failure'),error];new.pop('error',None);new.pop('pending',None)
    r.save(path,new)
    print('保存済みの補足前4件・確認質問・承認済み条件案を引き継ぎます。再生成・再承認は0回です。',flush=True)
    return new

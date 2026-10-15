#!/usr/bin/env python3
"""Recover only the saved, source-verified teaching proposal; zero generation."""
import argparse,copy,fcntl,json,os,sys
from pathlib import Path
WORKSPACE='ws_1fc7f906adcf832815c6347e20fde077'
RUN='run_ed781abd29baa3dfb53fe0bc0abb7937'
TRACE='trace_eea43b5632994a7b8f67e85645c4c4e0'
QUESTION='question_92bd35172b4562b9ad52aa6d45d3f66d'
REQUEST='req_9d19e537361ab25719022c0d'

def run(api,root,r,reviewer):
    from adapters.evidence import inspect_file
    from core.models import digest,permitted,validate_domain
    from teaching_evidence import prepare_rules
    root=Path(root);out=root/'deliverables/release130';checkpoint=root/'.jt/upgrades/1.0.30/teaching-recovery.json'
    manifest=r.load(root/'package-manifest.json');health=api.call('/health')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=('1.0.30',manifest['code_hash'],'LIVE',100):
        raise r.Stop('DEPLOY_MISMATCH','1.0.30・LIVE・既存上限を確認できません。')
    oldpath=root/'.jt/upgrades/1.0.29/baseline-teaching.json';old=r.load(oldpath);oldbytes=oldpath.read_bytes()
    inspection=root/'deliverables/release129/teaching-inspection';diagnostic=r.load(inspection/'diagnostic.json');trace=r.load(inspection/'saved-trace.json')
    intake=r.load(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json');domain=intake['approved_domain']
    if (old.get('status')!='FAILED' or old.get('run_id')!=RUN or old.get('baseline_rule_compliance') is not True or
        old.get('model_calls')!=6 or old.get('judgment_calls')!=4 or old.get('reviewer_name')!=reviewer or
        old.get('question',{}).get('question_id')!=QUESTION or old.get('error',{}).get('request_id')!=REQUEST or
        diagnostic.get('trace_id')!=TRACE or trace.get('trace_id')!=TRACE or trace.get('payload',{}).get('domain')!=domain):
        raise r.Stop('SAVED_ANSWER_MISMATCH','確認済みの停止結果・担当者・条件版と一致しません。')
    text=trace['payload']['human_text'];sid=next(iter(trace['source_hashes']))
    if len(trace['source_hashes'])!=1 or trace['source_hashes'][sid]!=digest(text.encode()):raise r.Stop('SOURCE_CHANGED','説明の版が一致しません。')
    metadata,_=inspect_file('expert_answer.txt',text.encode());source={**metadata,'source_id':sid,'human':True,'blob_id':'saved-human'}
    policy=(root/'app/web/samples/expense_policy.txt').read_bytes();pm,_=inspect_file('policy.txt',policy)
    policy_id='expense_policy_124';sources={sid:source,policy_id:{**pm,'source_id':policy_id,'blob_id':'saved-policy'}}
    if domain['source_hashes']!={policy_id:digest(policy)}:raise r.Stop('SOURCE_CHANGED','資料の版が一致しません。')
    class Evidence:
        def get(self,key):return {'saved-human':text.encode(),'saved-policy':policy}[key]
    class ReadOnly:
        blobs=Evidence()
        def source(self,wid,key):return sources[key]
    local=ReadOnly();rules,resolutions=prepare_rules(local,WORKSPACE,copy.deepcopy(trace['result']['rules']))
    from adapters.evidence import validate_ref
    merged=copy.deepcopy(domain);ids={rule['rule_id'] for rule in rules}
    merged['rules']=[rule for rule in merged['rules'] if rule['rule_id'] not in ids]+rules;merged['source_hashes'][sid]=digest(text.encode())
    validate_domain(merged,lambda ref:validate_ref(ref,sources[ref['source_id']],local.blobs))
    dev=[x['case'] for x in intake['readings'][:4]];expected=['ready_for_business_approval','ready_for_business_approval','hold','hold']
    tests=[(c['case_id'],c['facts'],action) for c,action in zip(dev,expected)]
    for field,value,action in [('receipt_employee_paid_amount',None,'hold'),('receipt_payment_status',None,'hold'),('receipt_payment_status','UNPAID','hold'),('actual_end_date','2026-09-11','hold'),('claimed_amount',1,'return_for_correction')]:
        tests.append(('dev02 '+field+'='+str(value),{**dev[1]['facts'],field:value},action))
    checks=[{'case':name,'expected_action':action,'permitted_action':permitted(merged,facts)[0]} for name,facts,action in tests]
    if any(x['expected_action']!=x['permitted_action'] for x in checks):raise r.Stop('TEACHING_REQUIRES_REVIEW','補足条件案の開発案件・例外確認が不合格です。保存・承認しません。')
    saved=r.load(checkpoint)
    if saved.get('status')=='TEACHING_DRAFT_READY_FOR_REVIEW':print(json.dumps(saved,ensure_ascii=False,indent=2));return saved
    def export():
        value=api.call('/exports/'+RUN);value.pop('exported_at',None);return value
    before=api.call('/recovery115');view=export();ws=api.call('/workspaces/'+WORKSPACE)
    if len(view['tasks'])!=4 or any(t['status']!='COMPLETED' for t in view['tasks']) or view['run']['domain_hash']!=digest(domain):
        raise r.Stop('BASELINE_CHANGED','完了した補足前4件を確認できません。')
    r.save(out/'preserved-baseline.json',view)
    value=api.call('/teachings/recover',{'question_id':QUESTION,'trace_id':TRACE,'original_operation':'baseline129-teaching-draft',
        'original_request_id':REQUEST,'reviewer_name':reviewer,'memo':'Reuse the saved model answer after exact line, hash and quotation validation; no business condition edits or rule approval.'},key='recover-teaching130-saved-answer')
    r.save(out/'recovered-teaching.json',value)
    if value['teaching']['approval_state']!='DRAFT' or value['teaching']['proposed_rules']!=rules or value['trace_id']!=TRACE or value.get('citation_resolutions')!=resolutions:
        raise r.Stop('RECOVERY_CHANGED','保存された未承認案が検証した内容と一致しません。')
    after=api.call('/recovery115');latest=api.call('/workspaces/'+WORKSPACE)
    protected=('version','approved_count','frozen','freeze','case_ids','run_ids','question_ids','source_ids','human_source_ids','domain','history_ids')
    if before!=after or export()!=view or oldpath.read_bytes()!=oldbytes or any(latest.get(k)!=ws.get(k) for k in protected):
        raise r.Stop('PRESERVATION_FAILED','利用量または過去記録の変更を検知しました。')
    result={'status':'TEACHING_DRAFT_READY_FOR_REVIEW','workspace_id':WORKSPACE,'run_id':RUN,'trace_id':TRACE,
        'teaching_id':value['teaching']['teaching_id'],'reviewer_name':reviewer,'new_model_calls':0,'judgment_calls':0,'approval_created':False,
        'baseline_preserved':True,'citation_resolutions':resolutions,'proposed_rules':rules,'candidate_checks':checks,'ledger':after['budget']}
    r.save(checkpoint,result);r.save(out/'verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
    print('保存済み回答を未承認の補足条件案として復元しました。モデル呼び出し0回。補足後・未使用案件の実行はまだ行っていません。',flush=True)
    return result

def main():
    sys.dont_write_bytecode=True;p=argparse.ArgumentParser();p.add_argument('--reviewer',required=True);args=p.parse_args();root=Path.cwd().resolve()
    if not args.reviewer.strip():raise RuntimeError('Reviewer required')
    if json.loads((root/'.jt/config.json').read_text()).get('project_id')!='jt-261013-a79fce':raise RuntimeError('Unexpected project')
    if Path(sys.prefix).resolve()!=(root/'.venv').resolve():os.execv(str(root/'.venv/bin/python'),[str(root/'.venv/bin/python'),str(Path(__file__).resolve()),*sys.argv[1:]])
    sys.path[:0]=[str(root),str(root/'app')];from steps import runbook as r
    r.integrity();(root/'.jt/upgrades/1.0.30').mkdir(parents=True,exist_ok=True)
    with (root/'.jt/upgrades/1.0.30/teaching.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        run(r.API(),root,r,args.reviewer.strip())
if __name__=='__main__':
    try:main()
    except Exception as e:sys.exit('STOP '+str(getattr(e,'code','RECOVERY_STOPPED'))+' / '+(str(e) if hasattr(e,'code') or isinstance(e,RuntimeError) else type(e).__name__))

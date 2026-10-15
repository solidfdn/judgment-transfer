#!/usr/bin/env python3
"""Approve the inspected supplement and execute four dev plus two held-out cases once."""
import argparse,copy,datetime as dt,fcntl,json,os,sys
from pathlib import Path
VERSION='1.0.30'
CODE_HASH='afe8d8d1812219f3e12e764b004a799327eb9db495f7284c73e749141e3be97a'
BASE_CODE='63800f5130d75799709f977a396baef4bd84790a37f4735102fe7c5eb465049d'
WORKSPACE='ws_1fc7f906adcf832815c6347e20fde077'
BASELINE='run_ed781abd29baa3dfb53fe0bc0abb7937'
TEACHING='teaching_55bf7012a9c6c070c59b3809ef946a2d'
RULES_HASH='5366622faf61d8057375d0f4246938f7b14f6b1399ad02ae5aafbfbb2588496d'
NOTE='The preserved baseline is package 1.0.29; the after and held-out runs are 1.0.30. The reviewed update changes teaching citation handling/recovery only. Decision adapter, model settings, strict evidence validator, execution and scoring are unchanged. Package hashes remain distinct. No latency improvement or broad reliability claim follows from this six-case sample.'
LABEL_NOTE='Private author-prepared targets under the complete reviewed policy, not model outputs. Baseline holds caused by incomplete policy are not unsafe actions; assess their compliance with the currently approved rules separately.'

def immutable(view):
    return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}

def usage(r,before,after):
    calls=after['session']['calls']-before['session']['calls'];decisions=after['session']['decisions']-before['session']['decisions']
    b,a=before['budget'],after['budget'];daily=a.get('day')==b.get('day') and a['decisions']-b['decisions']==decisions
    if a.get('day')!=b.get('day'):daily=dt.date.fromisoformat(a['day'])>dt.date.fromisoformat(b['day']) and 0<=a['decisions']<=decisions
    if (not 0<=calls==decisions<=6 or a['calls']-b['calls']!=calls or not daily or
        after['additional_decisions_used']-before['additional_decisions_used']!=decisions or after['extra_retry_attempts']!=before['extra_retry_attempts'] or
        after['study']!=before['study'] or not b['spent_usd']<=a['spent_usd']<=100):raise r.Stop('USAGE_CHANGED','今回の6件以外の利用変化を検知しました。')
    return calls,decisions

def run(api,root,r,reviewer,approve=False):
    from core.models import digest
    import config
    root=Path(root);out=root/'deliverables/release130/comparison';path=root/'.jt/upgrades/1.0.30/expense-comparison.json'
    recovery_path=root/'.jt/upgrades/1.0.30/teaching-recovery.json';recovery=r.load(recovery_path);p=r.load(path)
    if not approve or not reviewer.strip():raise r.Stop('REVIEW_REQUIRED','確認済み2条件の承認指定と担当者名が必要です。')
    if (recovery.get('status')!='TEACHING_DRAFT_READY_FOR_REVIEW' or recovery.get('teaching_id')!=TEACHING or recovery.get('run_id')!=BASELINE or
        recovery.get('reviewer_name')!=reviewer or digest(recovery.get('proposed_rules'))!=RULES_HASH or recovery.get('approval_created') is not False or
        len(recovery.get('candidate_checks',[]))!=9 or any(x['expected_action']!=x['permitted_action'] for x in recovery['candidate_checks'])):
        raise r.Stop('RECOVERY_CHANGED','確認済みの補足条件案と一致しません。')
    if p and (p.get('recovery_hash')!=digest(recovery) or p.get('reviewer_name')!=reviewer):raise r.Stop('CHECKPOINT_CHANGED','再開元か担当者が変わりました。')
    if p.get('status') in ('PASSED','FAILED'):
        print(json.dumps(p.get('report',p),ensure_ascii=False,indent=2))
        if p['status']=='FAILED':raise r.Stop('COMPARISON_GATE_FAILED','保存済みの停止結果です。追加実行は行いません。')
        return p
    health=api.call('/health')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=(VERSION,CODE_HASH,'LIVE',100):
        raise r.Stop('DEPLOY_MISMATCH','確認済み1.0.30・LIVE・既存上限と一致しません。')
    intake=r.load(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json');base_domain=intake['approved_domain'];cases=[]
    for answer in intake['readings']:
        case=copy.deepcopy(answer['case']);case['initial_state']={'review_status':'NEW'};cases.append(case)
    if [x['split'] for x in cases]!=['dev']*4+['holdout']*2:raise r.Stop('CASE_SET_CHANGED','開発4件・未使用2件が必要です。')
    before_view=api.call('/exports/'+BASELINE);ws=api.call('/workspaces/'+WORKSPACE)
    if (before_view['run']['code_hash']!=BASE_CODE or before_view['run']['domain_hash']!=digest(base_domain) or
        before_view['run']['dataset_hash']!=digest(cases[:4]) or before_view['run']['model_settings']!=config.SETTINGS or
        len(before_view['tasks'])!=4 or any(t['status']!='COMPLETED' for t in before_view['tasks'])):
        raise r.Stop('BASELINE_CHANGED','保存済み補足前4件・判断設定が一致しません。')
    if not p:
        doc=next((t for t in ws.get('teachings',[]) if t['teaching']['teaching_id']==TEACHING),{})
        if (ws.get('version')!=0 or ws.get('frozen') or ws.get('approved_count')!=0 or ws.get('domain')!=base_domain or
            ws.get('teaching_ids')!=[TEACHING] or doc.get('teaching',{}).get('approval_state')!='DRAFT' or
            doc['teaching']['proposed_rules']!=recovery['proposed_rules'] or ws.get('dev_cases')!=cases[:4] or
            ws.get('case_ids')!=[c['case_id'] for c in cases]):raise r.Stop('WORKSPACE_CHANGED','承認前の保存状態と一致しません。')
        before=api.call('/recovery115')
        if before['budget']!=recovery['ledger']:raise r.Stop('USAGE_CHANGED','復元後に別のモデル利用が記録されています。')
        p={'status':'PREPARED','reviewer_name':reviewer,'recovery_hash':digest(recovery),'before':before,'steps':{},
           'baseline_hash':digest(immutable(before_view)),'original_run_ids':ws['run_ids'],'started_at':r.stamp()}
        r.save(out/'baseline.json',before_view);r.save(path,p)
    if digest(immutable(before_view))!=p['baseline_hash']:raise r.Stop('BASELINE_CHANGED','過去の実行記録が変わっています。')
    def call(name,url,data):
        if name in p['steps']:return p['steps'][name]
        p['pending']=name;r.save(path,p)
        value=api.call(url,data,key='compare130-'+name)
        p['steps'][name]=value;p.pop('pending',None);r.save(path,p);return value
    def save_run(kind):
        view=api.call('/exports/'+p[kind+'_run_id']);r.save(out/(kind+'.json'),view);return view
    def rows(view,selected,targets):
        result=[]
        if [t['case_id'] for t in view['tasks']]!=[c['case_id'] for c in selected]:raise r.Stop('CASE_SET_CHANGED','実行案件が一致しません。')
        effects={a['action_id']:{e['field_id']:e['value'] for e in a['effects']} for a in view['run']['domain']['actions']}
        for task,case,target in zip(view['tasks'],selected,targets):
            receipts=[x for x in view.get('receipts',[]) if x['task_id']==task['task_id']]
            if (task['status']!='COMPLETED' or task.get('decision',{}).get('action_id')!=target or task.get('raw_decision',{}).get('action_id')!=target or
                task['state']!=effects[target] or task.get('score',{}).get('correct') is not True or task['score'].get('critical_error') is not False or
                len(receipts)!=1 or receipts[0]['before_state']!=case['initial_state'] or receipts[0]['case_hash']!=digest(case)):
                raise r.Stop('CASE_RESULT_MISMATCH','実際の判断・確定結果・開始状態が合格条件と一致しません: '+case['case_id'])
            result.append({'case_id':case['case_id'],'action':target,'state':task['state'],'trace_ids':task['trace_ids'],'explanation':task['decision']['explanation']})
        return result
    try:
        approved=call('approve','/teachings/'+TEACHING+'/approve',{'base_version':0,'reviewer_name':reviewer,'memo':'Reviewed the two company-folio rules against the owner explanation; missing employee payment evidence and changed stays remain held. This approves precheck guidance only, never expenditure or payment.'})
        domain=approved['domain'];normalized=copy.deepcopy(domain)
        for rule in normalized['rules']:rule['approved_by']=None
        expected=copy.deepcopy(base_domain);ids={x['rule_id'] for x in recovery['proposed_rules']}
        expected['rules']=[x for x in expected['rules'] if x['rule_id'] not in ids]+recovery['proposed_rules'];expected['version']=1
        for rule in expected['rules']:rule['approved_by']=None
        for rule in recovery['proposed_rules']:
            for ref in rule['source_refs']:expected['source_hashes'][ref['source_id']]=ref['version_hash']
        if approved['version']!=1 or normalized!=expected or any(not str(x.get('approved_by','')).startswith('human:') for x in domain['rules'] if x['rule_id'] in ids):raise r.Stop('APPROVAL_CHANGED','承認版が確認済み条件と一致しません。')
        for kind,split,selected,targets in [('after','dev',cases[:4],['ready_for_business_approval','ready_for_business_approval','hold','hold']),('holdout','holdout',cases[4:],['ready_for_business_approval','return_for_correction'])]:
            if kind=='holdout':
                freeze=call('freeze','/workspaces/freeze',{'workspace_id':WORKSPACE,'reviewer_name':reviewer,'memo':'Lock all six confirmed cases, original private targets and approved guidance before first held-out execution. No holdout-informed revision.'})
                effects={a['action_id']:{e['field_id']:e['value'] for e in a['effects']} for a in domain['actions']}
                targets6=['ready_for_business_approval','ready_for_business_approval','hold','hold','ready_for_business_approval','return_for_correction']
                labels=[{'case_id':case['case_id'],'expected_action_id':targets6[i],'expected_state':effects[targets6[i]],'critical_wrong_actions':['ready_for_business_approval'] if i in (2,3,5) else [],'rationale':LABEL_NOTE} for i,case in enumerate(cases)]
                if freeze['label_hash']!=digest(labels) or freeze['dataset_hash']!=digest(cases) or freeze['domain_hash']!=digest(domain) or freeze['code_hash']!=CODE_HASH or freeze['model_settings']!=config.SETTINGS:
                    raise r.Stop('FREEZE_CHANGED','固定された案件・条件・設定が一致しません。')
            result=call('create-'+kind,'/runs',{'workspace_id':WORKSPACE,'mode':'LIVE','arm':'C_JT_RULES','split':split,'repeats':1,'case_ids':[c['case_id'] for c in selected],
                'reviewer_name':reviewer,'memo':'One measured pass after approved clarification. '+NOTE})
            p[kind+'_run_id']=result['run_id'];r.save(path,p)
            for index in range(len(selected)):
                name=kind+'-'+str(index)
                if name in p['steps']:continue
                call(name,'/runs/'+result['run_id']+'/step',{});view=save_run(kind)
                if any(t['status'] in ('FAILED','CANCELLED') for t in view['tasks']):raise r.Stop('CASE_EXECUTION_FAILED','案件実行が停止しました。')
                if sum(t['status']=='COMPLETED' for t in view['tasks'])!=index+1:raise r.Stop('CASE_PROGRESS_CHANGED','予定した1案件の完了を確認できません。')
                print(('補足後' if kind=='after' else '未使用案件')+' '+str(index+1)+'/'+str(len(selected))+' の実行結果を保存しました。',flush=True)
            view=save_run(kind)
            if view['run']['dataset_hash']!=digest(selected) or view['run']['domain_hash']!=digest(domain) or view['run']['code_hash']!=CODE_HASH:raise r.Stop('RUN_CHANGED','実行条件が一致しません。')
            p[kind+'_results']=rows(view,selected,targets)
            call('fix-'+kind,'/history/fix',{'run_id':result['run_id'],'reviewer_name':reviewer,'memo':('Four development cases after clarification. ' if kind=='after' else 'First pass on two cases excluded from teaching. ')+NOTE})
        current=api.call('/workspaces/'+WORKSPACE)
        if (current['run_ids']!=p['original_run_ids']+[p['after_run_id'],p['holdout_run_id']] or current['version']!=1 or current['approved_count']!=1 or
            not current['frozen'] or current['teaching_ids']!=[TEACHING] or current['case_ids']!=[c['case_id'] for c in cases]):raise r.Stop('WORKSPACE_CHANGED','予定外の実行・条件変更を検知しました。')
        if digest(immutable(api.call('/exports/'+BASELINE)))!=p['baseline_hash']:raise r.Stop('BASELINE_CHANGED','過去の補足前実行が変わっています。')
        p['baseline_preserved']=True;p['status']='PASSED'
    except r.Stop as error:
        if error.code=='NETWORK_INTERRUPTED' or getattr(error,'detail',{}).get('code')=='BUSY':
            raise r.Stop('COMPARISON_PENDING','応答待ちです。同じコマンドで同じ要求の保存結果から再開できます。') from error
        p.update(status='FAILED',error={'code':error.code,'message':str(error),**getattr(error,'detail',{})})
        for kind in ('after','holdout'):
            if p.get(kind+'_run_id'):
                try:
                    view=save_run(kind);ids={x for t in view['tasks'] if t['status']=='FAILED' for x in t['trace_ids']}
                    p.setdefault('failed_traces',[]).extend({k:t.get(k) for k in ('trace_id','purpose','elapsed_ms','settings','attempts','error')} for t in view['traces'] if t['trace_id'] in ids)
                except r.Stop:p['export_diagnostic']='Saved run could not be fetched; original failure retained.'
    after=api.call('/recovery115');p['after']=after
    try:
        calls,decisions=usage(r,p['before'],after)
        if p['status']=='PASSED' and (calls,decisions)!=(6,6):raise r.Stop('USAGE_CHANGED','6件各1回の実行を確認できません。')
        p.update(model_calls=calls,judgment_calls=decisions)
    except r.Stop as e:p.update(status='FAILED',error={'code':e.code,'message':str(e)})
    report={k:p[k] for k in ('status','reviewer_name','after_run_id','holdout_run_id','after_results','holdout_results','model_calls','judgment_calls','error','failed_traces') if k in p}
    report.update(baseline_run_id=BASELINE,baseline_preserved=p.get('baseline_preserved'),baseline_code_hash=BASE_CODE,after_code_hash=CODE_HASH,protocol_note=NOTE,
        before_ledger=p['before']['budget'],after_ledger=after['budget'],approval_version=1 if 'approve' in p['steps'] else None)
    if p['status']=='PASSED':
        report['dev_changes']=[{'case_id':a['case_id'],'before_action':b['decision']['action_id'],'after_action':a['action']} for b,a in zip(before_view['tasks'],p['after_results'])]
        report['scope']='Four same-case before/after results and two first-use holdout results. Not a general reliability or performance benchmark.'
    p['report']=report;r.save(path,p);r.save(out/'verification.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
    if p['status']!='PASSED':raise r.Stop('COMPARISON_GATE_FAILED','記録を保存して停止しました。自動再実行・条件の自動修正はしません。')
    print('補足後4件・未使用2件が合格しました。承認・実行結果を担当者名と日時付きで保存しました。',flush=True);return p

def main():
    sys.dont_write_bytecode=True;parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--approve-reviewed-teaching',action='store_true');parser.add_argument('--reviewer',required=True);args=parser.parse_args()
    root=Path.cwd().resolve();c=json.loads((root/'.jt/config.json').read_text());m=json.loads((root/'package-manifest.json').read_text())
    if c.get('project_id')!='jt-261013-a79fce' or (m.get('version'),m.get('code_hash'))!=(VERSION,CODE_HASH):raise RuntimeError('Expected the installed Judgment Transfer 1.0.30 package')
    if Path(sys.prefix).resolve()!=(root/'.venv').resolve():os.execv(str(root/'.venv/bin/python'),[str(root/'.venv/bin/python'),str(Path(__file__).resolve()),*sys.argv[1:]])
    sys.path[:0]=[str(root),str(root/'app')];from steps import runbook as r
    r.integrity()
    with (root/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        run(r.API(),root,r,args.reviewer.strip(),args.approve_reviewed_teaching)
if __name__=='__main__':
    try:main()
    except Exception as e:sys.exit('STOP '+str(getattr(e,'code','COMPARISON_STOPPED'))+' / '+(str(e) if hasattr(e,'code') or isinstance(e,RuntimeError) else type(e).__name__))

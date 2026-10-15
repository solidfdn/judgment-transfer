#!/usr/bin/env python3
"""Approve the explicitly reviewed v128 clarification, then read six fictional PDFs.

Requires --approve-reviewed-workflow --reviewer NAME. No deployment, new rule
inference, case confirmation, decisions, teaching, or historical replay.
Author-prepared transcriptions are checked locally after extraction only.
"""
import argparse
import base64
import copy
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import zipfile

PROJECT = 'jt-261013-a79fce'
VERSION = '1.0.28'
CODE_HASH = '59032aa699d4e439e10b9f01e14d247b8744bc9b8d1069fb7b73126ce0a595b7'
WORKSPACE = 'ws_1fc7f906adcf832815c6347e20fde077'
DRAFT = 'draft_583b01423999b7f9efc79bbc33d9aa00'
TRACE = 'trace_1583bb08df16426aa5cebc5551f78ce5'
PREVIEW_HASH = 'ebbf9f444a4e24a6e5ed60227293fe51b6208a4128ea7c6a1ad548a7e637b6f9'
SOURCE = 'expense_policy_124'
SOURCE_HASH = '8548c15f795f156db72efbd3b91c332e8ef08a590e31509070a35f7e2e355d47'
PAYMENT_DESCRIPTION = ('The payment status explicitly stated for the employee payment on the hotel receipt. '
    'Do not use the total settlement status or a company payment status. '
    'If no employee-payment status is stated, leave this value unknown.')
MEMO = ('Reviewed clarification of LIVE draft '+DRAFT+'. Employee payment status is distinct from '
    'total settlement and company payment status. Added source line 7 to the two personal-receipt '
    'rules. Conditions and actions unchanged. Company-addressed folio acceptance remains unresolved. '
    'Isolated documentary precheck only; no expenditure or payment approval.')
DOCS = [{'case_id': 'expense_review_dev_01', 'path': 'case_inputs/dev/EXP-261001.pdf', 'sha256': '0100c793fde64e80cb8cab9ee5b8fbf6413d53eba90ea52d1b604278100e57d2', 'split': 'dev', 'stratum': 'normal', 'transcription': {'claimant_name': 'Mika Sato', 'guest_name': 'Mika Sato', 'approved_start_date': '2026-09-03', 'approved_end_date': '2026-09-05', 'actual_start_date': '2026-09-03', 'actual_end_date': '2026-09-05', 'receipt_addressed_to': 'Mika Sato', 'claimed_amount': 26800, 'receipt_employee_paid_amount': 26800, 'receipt_payment_status': 'PAID'}}, {'case_id': 'expense_review_dev_02', 'path': 'case_inputs/dev/EXP-261002.pdf', 'sha256': '915a7d923c50198005e2e04a4a77844a77914df96c2cab32656dbb59b99abe4c', 'split': 'dev', 'stratum': 'transfer', 'transcription': {'claimant_name': 'Aya Mori', 'guest_name': 'Aya Mori', 'approved_start_date': '2026-09-08', 'approved_end_date': '2026-09-10', 'actual_start_date': '2026-09-08', 'actual_end_date': '2026-09-10', 'receipt_addressed_to': 'Cedarline Services', 'claimed_amount': 34800, 'receipt_employee_paid_amount': 34800, 'receipt_payment_status': 'PAID'}}, {'case_id': 'expense_review_dev_03', 'path': 'case_inputs/dev/EXP-261003.pdf', 'sha256': '11f42e292c9a3110cb8a9b7f257ba0d74f74c2c20b63c0d78e435ed7edc17c48', 'split': 'dev', 'stratum': 'must_hold', 'transcription': {'claimant_name': 'Jun Aoki', 'guest_name': 'Jun Aoki', 'approved_start_date': '2026-09-12', 'approved_end_date': '2026-09-14', 'actual_start_date': '2026-09-12', 'actual_end_date': '2026-09-14', 'receipt_addressed_to': 'Cedarline Services', 'claimed_amount': 31200, 'receipt_employee_paid_amount': None, 'receipt_payment_status': None}}, {'case_id': 'expense_review_dev_04', 'path': 'case_inputs/dev/EXP-261004.pdf', 'sha256': '745cf4910380d827d2f95dbf7a8c2265936d55f8fa72c7cd227700a8de495edf', 'split': 'dev', 'stratum': 'must_hold', 'transcription': {'claimant_name': 'Ren Kato', 'guest_name': 'Ren Kato', 'approved_start_date': '2026-09-18', 'approved_end_date': '2026-09-19', 'actual_start_date': '2026-09-18', 'actual_end_date': '2026-09-20', 'receipt_addressed_to': 'Ren Kato', 'claimed_amount': 39600, 'receipt_employee_paid_amount': 39600, 'receipt_payment_status': 'PAID'}}, {'case_id': 'expense_review_holdout_01', 'path': 'case_inputs/holdout/EXP-261005.pdf', 'sha256': 'd3a1f4680e322670d993ea2da26138bd96fe4ab4a11bac91dd29d705484c92fa', 'split': 'holdout', 'stratum': 'transfer', 'transcription': {'claimant_name': 'Nao Ito', 'guest_name': 'Nao Ito', 'approved_start_date': '2026-09-23', 'approved_end_date': '2026-09-25', 'actual_start_date': '2026-09-23', 'actual_end_date': '2026-09-25', 'receipt_addressed_to': 'Cedarline Services', 'claimed_amount': 27600, 'receipt_employee_paid_amount': 27600, 'receipt_payment_status': 'PAID'}}, {'case_id': 'expense_review_holdout_02', 'path': 'case_inputs/holdout/EXP-261006.pdf', 'sha256': '57084d8b6b31c00dd7e46391f5295e30e5890a71382407f1d5284fad5c55d746', 'split': 'holdout', 'stratum': 'transfer', 'transcription': {'claimant_name': 'Yui Ono', 'guest_name': 'Yui Ono', 'approved_start_date': '2026-09-27', 'approved_end_date': '2026-09-29', 'actual_start_date': '2026-09-27', 'actual_end_date': '2026-09-29', 'receipt_addressed_to': 'Cedarline Services', 'claimed_amount': 42400, 'receipt_employee_paid_amount': 26400, 'receipt_payment_status': 'PAID'}}]


def digest(value):
    return hashlib.sha256(value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,
        ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def preview(domain):
    return {k:domain[k] for k in ('title','goal','input_fields','state_fields','actions','default_action_id','rules')}


def reviewed_domain(original, policy):
    """Explicit human-review edit, not an untouched model output."""
    value=copy.deepcopy(original)
    field=next(f for f in value['input_fields'] if f['field_id']=='receipt_payment_status')
    field.update(label='Employee Payment Status',description=PAYMENT_DESCRIPTION)
    ref={'source_id':SOURCE,'version_hash':SOURCE_HASH,'locator':'line:7','quote':policy.splitlines()[6]}
    for rule in value['rules']:
        if rule['rule_id'] in ('amount_mismatch','precheck_complete'):rule['source_refs'].append(copy.deepcopy(ref))
    return value


def stable(ws):
    return {k:copy.deepcopy(ws.get(k)) for k in ('workspace_id','version','status','goal','source_ids',
        'human_source_ids','sources','requirements_review','extraction','domain','draft','draft_id',
        'case_ids','run_ids','teaching_ids','question_ids','history_ids','approved_count','frozen','freeze','shared_trace_ids')}


def usage(r,before,after,maximum):
    calls=after['session']['calls']-before['session']['calls']
    b,a=before['budget'],after['budget']
    same_day=b.get('day')==a.get('day')
    rolled=(not same_day and calls>0 and dt.date.fromisoformat(a['day'])>dt.date.fromisoformat(b['day']) and a['decisions']==0)
    if (not 0<=calls<=maximum or a['calls']-b['calls']!=calls or
        after['session']['decisions']!=before['session']['decisions'] or
        not ((same_day and a['decisions']==b['decisions']) or rolled) or
        after['additional_decisions_used']!=before['additional_decisions_used'] or
        after['extra_retry_attempts']!=before['extra_retry_attempts'] or after['study']!=before['study'] or
        not b['spent_usd']<=a['spent_usd']<=100):
        raise r.Stop('VALIDATION_USAGE_CHANGED','今回のPDF読取以外の使用変化があります。保存して停止します。')
    return calls


def files(root,r):
    pack=json.loads((root/'app/web/samples/expense_files.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(pack['base64'],validate=True))) as archive:
        result={d['case_id']:archive.read(d['path']) for d in DOCS}
    if any(digest(result[d['case_id']])!=d['sha256'] for d in DOCS):
        raise r.Stop('CASE_FILE_CHANGED','確認対象PDFのハッシュが一致しません。')
    return result


def read_issues(answer,doc,domain):
    issues=[];case=answer.get('case',{});observations=answer.get('observations',[])
    defs={f['field_id'] for f in domain['input_fields']}
    if (answer.get('status')!='DRAFT' or answer.get('workspace_id')!=WORKSPACE or
        answer.get('case_id')!=doc['case_id'] or answer.get('split')!=doc['split'] or
        answer.get('domain_hash')!=digest(domain) or answer.get('domain_version')!=0 or not answer.get('trace_id') or
        case.get('case_id')!=doc['case_id'] or case.get('split')!=doc['split'] or case.get('domain_id')!=domain['domain_id']):
        issues.append('Case draft identity, domain or trace mismatch.')
    if len(observations)!=len(defs) or {o.get('field_id') for o in observations}!=defs:
        issues.append('Exactly one observation per approved input is required.')
    if set(case.get('facts',{}))!=defs:issues.append('Case facts do not match approved inputs.')
    if case.get('initial_state')!={f['field_id']:None for f in domain['state_fields']}:
        issues.append('Initial state must remain unconfirmed.')
    sources=answer.get('sources',[])
    if len(sources)!=1 or sources[0].get('version_hash')!=doc['sha256']:
        issues.append('Case source hash mismatch.')
    # These transcriptions are private verifier data, never request/model inputs.
    for o in observations:
        fid=o.get('field_id');expected=doc['transcription'].get(fid)
        if (o.get('value')!=expected or case.get('facts',{}).get(fid)!=expected or
            o.get('status')!=('UNRESOLVED' if expected is None else 'OBSERVED')):
            issues.append(fid+': reading differs from the author-checked document transcription.')
        if fid=='receipt_payment_status' and expected is not None:
            if not any('Employee card payment status: PAID' in ref.get('quote','') for ref in o.get('source_refs',[])):
                issues.append(fid+': the cited text must identify the employee payment, not total settlement.')
    return issues


def show(p):
    keys=('status','workspace_id','reviewer_name','original_draft_id','approved_draft_id','model_calls',
        'judgment_calls','case_confirmation_created','before_ledger','after_ledger','case_previews','error')
    print(json.dumps({k:p[k] for k in keys if k in p},ensure_ascii=False,indent=2),flush=True)


def run(api,root,r,reviewer,approve=False):
    root=Path(root);checkpoint=root/'.jt/upgrades/1.0.28/pdf-intake.json';out=root/'deliverables/release128/intake'
    if not approve or not isinstance(reviewer,str) or not reviewer.strip():
        raise r.Stop('REVIEW_APPROVAL_REQUIRED','説明した修正内容の承認には --approve-reviewed-workflow と --reviewer が必要です。')
    reviewer=reviewer.strip();p=r.load(checkpoint)
    if p and (p.get('reviewer_name')!=reviewer or p.get('code_hash')!=CODE_HASH):
        raise r.Stop('CHECKPOINT_CHANGED','保存済みの担当者・アプリ版と一致しません。')
    if p.get('status') in ('READINGS_READY_FOR_REVIEW','FAILED'):
        show(p)
        if p['status']=='FAILED':raise r.Stop('CASE_READ_GATE_FAILED','保存済みの停止結果です。追加読取は行いません。')
        print('保存済み読取結果です。追加モデル呼び出し0回。',flush=True);return p
    health=api.call('/health')
    if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=(VERSION,CODE_HASH,'LIVE',100):
        raise r.Stop('DEPLOY_MISMATCH','1.0.28・LIVE・既存の100ドル上限を確認できません。')
    data=files(root,r);policy=(root/'app/web/samples/expense_policy.txt').read_text()
    if digest(policy.encode())!=SOURCE_HASH:raise r.Stop('SOURCE_CHANGED','資料が変更されています。')
    ws=api.call('/workspaces/'+WORKSPACE)
    if not p:
        gate=r.load(root/'.jt/upgrades/1.0.28/workflow-prepare.json');d=ws.get('draft') or {}
        if (gate.get('status')!='DRAFT_READY_FOR_REVIEW' or gate.get('draft_id')!=DRAFT or
            gate.get('code_hash')!=CODE_HASH or gate.get('trace_ids')!=[TRACE] or
            d.get('draft_id')!=DRAFT or d.get('origin')!='LIVE' or d.get('trace_ids')!=[TRACE] or
            digest(preview(d['domain']))!=PREVIEW_HASH or d.get('input_review_issues') or
            d['domain']['source_hashes']!={SOURCE:SOURCE_HASH} or ws.get('version')!=-1 or ws.get('domain') is not None or
            ws.get('case_ids') or ws.get('case_draft_ids') or ws.get('case_source_ids') or ws.get('run_ids') or ws.get('teaching_ids') or
            ws.get('history_ids') or ws.get('frozen') or ws.get('source_ids')!=[SOURCE]):
            raise r.Stop('WORKSPACE_CHANGED','今回確認した未承認案・資料・案件未投入状態と一致しません。')
        p={'status':'PREPARED','workspace_id':WORKSPACE,'code_hash':CODE_HASH,'reviewer_name':reviewer,
            'original_draft_id':DRAFT,'original_draft':d,'original_workspace':stable(ws),
            'reviewed_domain':reviewed_domain(d['domain'],policy),'before':api.call('/recovery115'),
            'started_at':r.stamp(),'readings':[],'case_previews':[],'judgment_calls':0,'case_confirmation_created':False}
        r.save(out/'original-live-draft.json',d);r.save(out/'reviewed-domain.json',p['reviewed_domain']);r.save(checkpoint,p)
    try:
        if not p.get('approved_domain'):
            original=p['original_workspace']
            changing={'version','status','domain','draft','draft_id','history_ids'}
            if any(stable(ws)[k]!=v for k,v in original.items() if k not in changing):
                raise r.Stop('WORKSPACE_CHANGED','修正・承認以外の資料や記録が変わりました。')
            if not p.get('edited_draft'):
                current_draft=ws.get('draft') or {}
                unchanged=current_draft==p['original_draft']
                saved_edit=(p.get('status')=='EDIT_PENDING' and current_draft.get('origin')=='HUMAN_EDIT'
                    and current_draft.get('domain')==p['reviewed_domain'] and not current_draft.get('trace_ids'))
                if ws.get('version')!=-1 or not (unchanged or saved_edit):
                    raise r.Stop('DRAFT_CHANGED','編集対象の案が変わりました。')
            if ws.get('version') not in (-1,0) or ws.get('case_ids') or ws.get('run_ids') or ws.get('frozen'):
                raise r.Stop('WORKSPACE_CHANGED','承認中に作業状態が変わりました。')
            if not p.get('edited_draft'):
                p['status']='EDIT_PENDING';r.save(checkpoint,p)
                d=api.call('/domains/draft',{'workspace_id':WORKSPACE,'domain':p['reviewed_domain']},key='intake128-reviewed-clarification')
                if d.get('origin')!='HUMAN_EDIT' or d.get('domain')!=p['reviewed_domain'] or d.get('trace_ids') or d.get('input_review_issues'):
                    raise r.Stop('EDIT_MISMATCH','明示した修正と保存された案が一致しません。')
                p['edited_draft']=d;p['approved_draft_id']=d['draft_id'];r.save(out/'reviewed-draft.json',d);r.save(checkpoint,p)
            current=api.call('/workspaces/'+WORKSPACE)
            if current.get('draft')!=p['edited_draft']:raise r.Stop('DRAFT_CHANGED','承認対象の案が変わりました。')
            p['status']='APPROVAL_PENDING';r.save(checkpoint,p)
            a=api.call('/domains/approve',{'draft_id':p['approved_draft_id'],'base_version':-1,
                'reviewer_name':reviewer,'memo':MEMO},key='intake128-approve-reviewed')
            ws=api.call('/workspaces/'+WORKSPACE);stripped=copy.deepcopy(a['domain'])
            if not all(isinstance(x.get('approved_by'),str) and x['approved_by'].startswith('human:') for x in stripped['rules']):
                raise r.Stop('APPROVAL_MISMATCH','承認の記録を確認できません。')
            for rule in stripped['rules']:rule['approved_by']=None
            if stripped!=p['reviewed_domain'] or a.get('version')!=0 or ws.get('domain')!=a['domain'] or ws.get('version')!=0:
                raise r.Stop('APPROVAL_MISMATCH','承認した版と修正案が一致しません。')
            original=p['original_workspace']
            allowed={'version','status','domain','draft','draft_id','history_ids'}
            if any(stable(ws)[k]!=v for k,v in original.items() if k not in allowed) or len(ws.get('history_ids',[]))!=1:
                raise r.Stop('WORKSPACE_CHANGED','条件の承認以外の変更があります。')
            record=api.call('/history/'+ws['history_ids'][0])
            if record.get('reviewer_name')!=reviewer or record.get('memo')!=MEMO or record.get('snapshot',{}).get('domain')!=a['domain'] or not record.get('recorded_at'):
                raise r.Stop('APPROVAL_MISMATCH','担当者・日時・修正内容の履歴が一致しません。')
            usage(r,p['before'],api.call('/recovery115'),0)
            p.update(approved_domain=a['domain'],approved_workspace=stable(ws),approval_record=record,status='APPROVED')
            r.save(checkpoint,p);r.save(out/'approval-record.json',record)
            print('修正内容を担当者名・日時付きで承認しました。モデル呼び出し0回。PDF6件を順番に読み取ります。',flush=True)
        for index,doc in enumerate(DOCS):
            if index<len(p['readings']):continue
            current=api.call('/workspaces/'+WORKSPACE)
            if stable(current)!=p['approved_workspace']:raise r.Stop('WORKSPACE_CHANGED','PDF読取以外の作業状態が変わりました。')
            if not p.get('pending'):
                if current.get('case_draft_ids',[])!=[x['case_draft_id'] for x in p['readings']]:
                    raise r.Stop('CASE_SET_CHANGED','別のPDF読取が追加されています。')
                p['pending']={'index':index,'before':api.call('/recovery115')};p['status']='READ_PENDING';r.save(checkpoint,p)
            if p['pending']['index']!=index:raise r.Stop('CHECKPOINT_CHANGED','読取位置が一致しません。')
            answer=api.call('/cases/read',{'workspace_id':WORKSPACE,'case_id':doc['case_id'],
                'split':doc['split'],'stratum':doc['stratum']},key='intake128-read-'+doc['case_id'],
                files=(Path(doc['path']).name,'application/pdf',data[doc['case_id']]))
            r.save(out/(doc['case_id']+'.json'),answer)
            after=api.call('/recovery115');calls=usage(r,p['pending']['before'],after,2)
            issues=read_issues(answer,doc,p['approved_domain'])
            p['case_previews'].append({'case_id':doc['case_id'],'split':doc['split'],'trace_id':answer.get('trace_id'),
                'model_calls':calls,'facts':answer.get('case',{}).get('facts'),
                'payment_status_evidence':[o for o in answer.get('observations',[]) if o.get('field_id')=='receipt_payment_status'],
                'review_issues':issues})
            p['readings'].append(answer);r.save(checkpoint,p)
            latest=api.call('/workspaces/'+WORKSPACE)
            if stable(latest)!=p['approved_workspace'] or latest.get('case_draft_ids',[])!=[x['case_draft_id'] for x in p['readings']]:
                raise r.Stop('WORKSPACE_CHANGED','PDF読取以外の変更があります。')
            if issues:raise r.Stop('DOCUMENT_READING_REQUIRES_REVIEW','読取結果に原本転記との差分があります。修正せず保存して停止します。')
            if calls<1:raise r.Stop('READ_TRACE_REQUIRED','新規読取の使用記録を確認できません。')
            p.pop('pending');p['status']='READING';r.save(checkpoint,p)
            print(str(index+1)+'/6 PDF読取を保存: '+Path(doc['path']).name,flush=True)
        p['status']='READINGS_READY_FOR_REVIEW'
    except r.Stop as error:
        detail=getattr(error,'detail',{})
        if error.code=='NETWORK_INTERRUPTED' or detail.get('code')=='BUSY':
            r.save(checkpoint,p)
            raise r.Stop('INTAKE_PENDING','応答待ちです。同じコマンドで同じ要求の保存結果を確認します。別の要求は作りません。') from error
        p.update(status='FAILED',error={'code':error.code,'message':str(error),
            **{k:detail[k] for k in ('request_id','diagnostic') if k in detail}})
    after=api.call('/recovery115')
    p.update(after=after,before_ledger=p['before']['budget'],after_ledger=after['budget'],checked_at=r.stamp())
    try:p['model_calls']=usage(r,p['before'],after,12)
    except r.Stop as error:p.update(status='FAILED',error={'code':error.code,'message':str(error)})
    r.save(checkpoint,p);r.save(out/'verification.json',p);show(p)
    if p['status']=='FAILED':raise r.Stop('CASE_READ_GATE_FAILED','保存結果を確認して停止しました。自動再試行・案件確定・案件判断は行いません。')
    print('6件のPDF読取を保存しました。案件の確定と補足前後の比較は未実施です。',flush=True)
    return p


def main():
    sys.dont_write_bytecode=True
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approve-reviewed-workflow',action='store_true')
    parser.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if not args.approve_reviewed_workflow:parser.error('--approve-reviewed-workflow is required; no changes made')
    root=Path.cwd().resolve();conf=json.loads((root/'.jt/config.json').read_text());manifest=json.loads((root/'package-manifest.json').read_text())
    if conf.get('project_id')!=PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=(VERSION,CODE_HASH):
        raise RuntimeError('Expected the installed Judgment Transfer 1.0.28 project/package')
    if Path(sys.prefix).resolve()!=(root/'.venv').resolve():
        executable=root/'.venv/bin/python'
        if not executable.is_file():raise RuntimeError('Existing .venv missing; no dependency installed')
        os.execv(str(executable),[str(executable),str(Path(__file__).resolve()),*sys.argv[1:]])
    sys.path[:0]=[str(root),str(root/'app')]
    from steps import runbook as r
    r.integrity()
    with (root/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        run(r.API(),root,r,args.reviewer,True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        code=getattr(error,'code','INTAKE_STOPPED')
        message=str(error) if hasattr(error,'code') or isinstance(error,RuntimeError) else type(error).__name__
        sys.exit('STOP '+str(code)+' / '+message)

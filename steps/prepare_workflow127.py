#!/usr/bin/env python3
"""One streamed workflow proposal, reusing the passed 1.0.25 source review.

No installation, deployment, approval, case execution, budget reset or replay.
Only /domains/draft can write cloud state. Re-entry uses the same request key.
"""
import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'jt-261013-a79fce'
SOURCE_CODE_HASH = 'ec550774dd59e6211d349e9671cfe793cfe73d75518f678c3066277aea33a471'
WORKSPACE = 'ws_1fc7f906adcf832815c6347e20fde077'
SOURCE = 'expense_policy_124'
SOURCE_TRACE = 'trace_62e5bd652ea8480b8a8c4372b7b9cdb8'
VERSION = '1.0.27'
PREVIOUS_VERSION = '1.0.26'
PREVIOUS_CODE_HASH = '51e77a85c036b182039fbe2f495f78e451821c3eec5e124dd8478ff8710231fd'
PREVIOUS_DRAFT_ID = 'draft_63bab9807f91bd34bad6e8a05ef99486'
PREVIOUS_TRACE_IDS = ['trace_0d6f14a4b9f14aaa81e450f7ba74f446']
PREVIOUS_PREVIEW_HASH = '424c3348e0897aa8e7e1691adb9aa6d0c2132154dab5e71f8d90c49d164fe330'
REQUEST_KEY = 'workflow-prepare127-draft'
FINAL = ('DRAFT_READY_FOR_REVIEW', 'FAILED')


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def frozen_parts(ws):
    # The proposal may add a draft and its trace, but cannot activate any rules.
    return {k: copy.deepcopy(ws.get(k)) for k in ('workspace_id', 'version', 'status',
        'goal', 'source_ids', 'human_source_ids', 'sources', 'requirements_review',
        'extraction', 'domain', 'case_ids', 'run_ids', 'teaching_ids', 'question_ids',
        'history_ids', 'approved_count', 'frozen', 'freeze')}


def preview(draft):
    domain = draft['domain']
    return {k: domain[k] for k in ('title', 'goal', 'input_fields', 'state_fields',
        'actions', 'default_action_id', 'rules')}


def show(report):
    keys = ('status', 'workspace_id', 'source_review_trace_id', 'draft_id', 'trace_ids',
        'previous_draft_id', 'previous_trace_ids', 'model_calls', 'judgment_calls', 'approval_created', 'before_ledger',
        'after_ledger', 'question_preview', 'workflow_preview', 'error_code',
        'error_message', 'request_id', 'diagnostic', 'saved_answer_diagnostic')
    print(json.dumps({k: report[k] for k in keys if k in report}, ensure_ascii=False, indent=2), flush=True)


def daily_counter_unchanged(before, after, count):
    # The application resets only its DAILY judgment count on the first call
    # of a new UTC day. Cumulative session decisions are checked separately.
    if before.get('day') == after.get('day'):
        return before.get('decisions') == after.get('decisions')
    try:
        previous = dt.date.fromisoformat(before['day'])
        current = dt.date.fromisoformat(after['day'])
    except (KeyError, TypeError, ValueError):
        return False
    return count == 1 and current > previous and after.get('decisions') == 0


def check_usage(r, before, after):
    count = after['session']['calls'] - before['session']['calls']
    if (not 0 <= count <= 1 or after['budget']['calls']-before['budget']['calls'] != count or
            after['session']['decisions'] != before['session']['decisions'] or
            not daily_counter_unchanged(before['budget'], after['budget'], count) or
            after['additional_decisions_used'] != before['additional_decisions_used'] or
            after['extra_retry_attempts'] != before['extra_retry_attempts'] or
            after['study'] != before['study'] or
            not before['budget']['spent_usd'] <= after['budget']['spent_usd'] <= 100):
        raise r.Stop('VALIDATION_USAGE_CHANGED', 'この条件作成以外の利用変化があります。記録を保持して停止します。')
    return count


def run(api, root, r, code_hash):
    root = Path(root)
    checkpoint = root/'.jt/upgrades/1.0.27/workflow-prepare.json'
    output = root/'deliverables/release127'
    progress = r.load(checkpoint)
    if progress and progress.get('code_hash') != code_hash:
        raise r.Stop('GATE_VERSION_CHANGED', '保存済みの確認とアプリの版が異なります。')
    if progress.get('status') in FINAL:
        show(progress)
        if progress['status'] == 'FAILED':
            raise r.Stop('WORKFLOW_PREPARE_FAILED', '保存済みの失敗で停止しました。追加モデル呼び出し0回。')
        print('保存済みの条件案を表示しました。追加モデル呼び出し0回。条件の承認・案件実行は未実施です。', flush=True)
        return progress
    gate = r.load(root/'.jt/upgrades/1.0.25/source-review-gate.json')
    if (gate.get('status'), gate.get('code_hash'), gate.get('workspace_id'), gate.get('trace_id')) != (
            'PASSED', SOURCE_CODE_HASH, WORKSPACE, SOURCE_TRACE):
        raise r.Stop('SOURCE_GATE_REQUIRED', '今回の1.0.25資料レビュー合格記録を確認できません。')
    health = api.call('/health')
    if (health.get('package_version'), health.get('code_hash'), health.get('mode'), health.get('max_cost_usd')) != (
            VERSION, code_hash, 'LIVE', 100):
        raise r.Stop('DEPLOY_MISMATCH', '1.0.27・LIVE・既存の100ドル上限を確認できません。')
    ws = api.call('/workspaces/'+WORKSPACE)
    policy_hash = digest((root/'app/web/samples/expense_policy.txt').read_bytes())
    review = ws.get('requirements_review') or {}
    if (review.get('trace_id') != SOURCE_TRACE or review.get('source_hashes') != {SOURCE:policy_hash} or
            ws.get('version') != -1 or ws.get('domain') is not None or ws.get('run_ids') or
            ws.get('case_ids') or ws.get('teaching_ids') or ws.get('frozen') or
            ws.get('source_ids') != [SOURCE] or review.get('goal') != ws.get('goal') or
            {s['source_id']:s['version_hash'] for s in ws.get('sources', [])} != {SOURCE:policy_hash}):
        raise r.Stop('WORKSPACE_CHANGED', '保存済みレビュー・資料・未承認の作業状態を確認できません。')
    if not progress:
        previous = r.load(root/'.jt/upgrades/1.0.26/workflow-prepare.json')
        old_draft = ws.get('draft') or {}
        if (previous.get('status') != 'DRAFT_READY_FOR_REVIEW' or previous.get('code_hash') != PREVIOUS_CODE_HASH or
                previous.get('draft_id') != PREVIOUS_DRAFT_ID or previous.get('trace_ids') != PREVIOUS_TRACE_IDS or
                previous.get('workspace_id') != WORKSPACE or previous.get('source_review_trace_id') != SOURCE_TRACE or
                old_draft.get('draft_id') != PREVIOUS_DRAFT_ID or old_draft.get('trace_ids') != PREVIOUS_TRACE_IDS or
                old_draft.get('base_version') != -1 or old_draft.get('origin') != 'LIVE'):
            raise r.Stop('PREVIOUS_DRAFT_CHANGED', '今回確認した1.0.26の未承認案と一致しません。生成せず停止します。')
        if (digest(preview(old_draft)) != PREVIOUS_PREVIEW_HASH or
                any(rule.get('approved_by') is not None for rule in old_draft['domain']['rules'])):
            raise r.Stop('PREVIOUS_DRAFT_CHANGED', '確認した条件案が変更されています。生成せず停止します。')
        r.save(output/'workflow-previous-draft.json', old_draft)
        progress = {'status':'PREPARED', 'code_hash':code_hash, 'workspace_id':WORKSPACE,
            'source_review_trace_id':SOURCE_TRACE, 'source_hash':policy_hash,
            'previous_draft_id':PREVIOUS_DRAFT_ID, 'previous_trace_ids':PREVIOUS_TRACE_IDS,
            'request_key':REQUEST_KEY, 'started_at':r.stamp(),
            'workspace_before':frozen_parts(ws),
            'shared_trace_ids_before':copy.deepcopy(ws.get('shared_trace_ids', [])),
            'before':api.call('/recovery115')}
        r.save(checkpoint, progress)
    if progress.get('request_key') != REQUEST_KEY or frozen_parts(ws) != progress['workspace_before']:
        raise r.Stop('WORKSPACE_CHANGED', '確認開始時と入力・承認状態が異なります。')
    # Even after a lost response use the same application request. Its persistent
    # receipt returns the saved result or refuses an uncertain/expired request.
    progress['status'] = 'STARTED'; r.save(checkpoint, progress)
    print('前の未承認案を保持し、同じ資料レビューから条件案を作り直します（1要求・生成は1回）。承認・案件実行は行いません。', flush=True)
    failure = None
    draft = None
    try:
        draft = api.call('/domains/draft', {'workspace_id':WORKSPACE, 'goal':ws['goal']}, key=REQUEST_KEY)
    except r.Stop as error:
        detail = getattr(error, 'detail', {})
        if error.code == 'NETWORK_INTERRUPTED' or detail.get('code') == 'BUSY':
            raise r.Stop('WORKFLOW_PREPARE_PENDING', '応答を確認できません。同じコマンドで保存結果を確認できます。新しい要求は作りません。') from error
        failure = {k:detail[k] for k in ('code','message','request_id','diagnostic') if k in detail}
        failure.setdefault('code', error.code)
        failure.setdefault('message', str(error))
    after = api.call('/recovery115')
    latest = api.call('/workspaces/'+WORKSPACE)
    # Save observations before checking them, so a stopped verification is reviewable.
    progress.update(after=after, workspace_after=frozen_parts(latest), checked_at=r.stamp(),
        before_ledger=progress['before']['budget'], after_ledger=after['budget'],
        approval_created=latest.get('version', -1) >= 0,
        judgment_calls=after['session']['decisions']-progress['before']['session']['decisions'],
        question_preview=[q['question'] for q in review.get('questions', [])])
    if draft is not None:
        r.save(output/'workflow-draft.json', draft)
        progress['draft_id'] = draft.get('draft_id')
        progress['trace_ids'] = draft.get('trace_ids', [])
    try:
        progress['model_calls'] = check_usage(r, progress['before'], after)
        if frozen_parts(latest) != progress['workspace_before']:
            raise r.Stop('WORKSPACE_CHANGED', '条件作成以外の入力・承認状態の変化があります。')
        if failure is None:
            domain = draft.get('domain', {})
            if (draft.get('workspace_id') != WORKSPACE or draft.get('origin') != 'LIVE' or
                    draft.get('base_version') != -1 or domain.get('version') != 0 or
                    domain.get('source_hashes') != {SOURCE:policy_hash} or
                    any(x.get('approved_by') is not None for x in domain.get('rules', [])) or
                    len(draft.get('trace_ids', [])) != 1 or latest.get('draft') != draft or
                    latest.get('shared_trace_ids') != progress['shared_trace_ids_before'] + draft['trace_ids'] or
                    progress['model_calls'] != 1):
                raise r.Stop('DRAFT_GATE_INCOMPLETE', '実生成した未承認の条件案と保存結果を確認できません。')
            progress['workflow_preview'] = preview(draft)
    except r.Stop as error:
        failure = {'code':error.code, 'message':str(error)}
    if failure is None:
        progress['status'] = 'DRAFT_READY_FOR_REVIEW'
    else:
        progress.update(status='FAILED', error_code=failure['code'], error_message=failure.get('message',''))
        progress.update({k:failure[k] for k in ('request_id','diagnostic') if k in failure})
    r.save(checkpoint, progress)
    r.save(output/'workflow-prepare-verification.json', progress)
    show(progress)
    if failure:
        raise r.Stop('WORKFLOW_PREPARE_FAILED', '条件案の作成は未合格です。保存結果を診断し、自動再試行はしません。')
    print('条件案を保存しました。担当者による内容確認・承認前です。PDF読取・補足前後の案件比較は未実行です。', flush=True)
    return progress


def diagnose(root, r):
    """On failure only, read the exact draft trace; never call a model again."""
    checkpoint = root/'.jt/upgrades/1.0.27/workflow-prepare.json'
    report = r.load(checkpoint)
    if report.get('status') != 'FAILED' or report.get('saved_answer_diagnostic'):
        return
    process = subprocess.run(['gcloud','auth','print-access-token'], capture_output=True, text=True)
    if process.returncode or not process.stdout.strip():
        raise RuntimeError('Existing login unavailable for saved-answer reading')
    base = 'https://firestore.googleapis.com/v1/projects/'+PROJECT+'/databases/(default)/documents/'
    def read(path):
        request = urllib.request.Request(base+path, headers={'Authorization':'Bearer '+process.stdout.strip()}, method='GET')
        with urllib.request.urlopen(request, timeout=30) as response: return json.load(response)
    def unpack(doc): return json.loads(doc.get('fields',{}).get('payload',{}).get('stringValue','{}'))
    ws = unpack(read('jt_workspaces/'+WORKSPACE))
    wanted = 'workflow_'+digest([ws['owner'], REQUEST_KEY, ''])[:32]
    trace_id = (report.get('diagnostic') or {}).get('trace_id')
    matches = []; scanned = 0
    if trace_id:
        matches = [unpack(read('jt_traces/'+trace_id))]
    else:
        cursor = None
        for _ in range(10):
            query = {'pageSize':200, 'mask.fieldPaths':'payload'}
            if cursor: query['pageToken'] = cursor
            page = read('jt_traces?'+urllib.parse.urlencode(query))
            for doc in page.get('documents', []):
                scanned += 1; trace = unpack(doc)
                if trace.get('purpose') == 'draft_domain' and trace.get('payload',{}).get('domain_id') == wanted:
                    matches.append(trace)
            cursor = page.get('nextPageToken')
            if not cursor: break
        if cursor: raise RuntimeError('Trace scan limit reached; no candidate assumed')
    matches = [t for t in matches if t.get('purpose') == 'draft_domain' and
        t.get('payload',{}).get('domain_id') == wanted and t.get('source_hashes') == {SOURCE:report['source_hash']}]
    if len(matches) != 1: raise RuntimeError('One exact saved draft trace could not be identified')
    trace = matches[0]
    summary = {'read_only':True, 'new_model_calls':0, 'cloud_writes':0,
        'trace_id':trace['trace_id'], 'trace_documents_scanned':scanned,
        'attempts':[{k:a[k] for k in ('attempt','stage','status','provider_code','error_type','validation_errors','provider_error',
                        'elapsed_ms','failed_stage_elapsed_ms','generation_timeout_ms','chunk_count','first_text_ms',
                        'last_chunk_ms','last_text_ms','received_text_chars','complete_stream','finish_reason') if k in a}
                    for a in trace.get('attempts', [])]}
    if isinstance(trace.get('result'), dict):
        from core.models import JTError, validate_domain
        from adapters.evidence import validate_ref
        source = unpack(read('jt_sources/'+WORKSPACE+'-'+SOURCE))
        data = (root/'app/web/samples/expense_policy.txt').read_bytes()
        if digest(data) != source.get('version_hash') or source['version_hash'] != report['source_hash']:
            raise RuntimeError('Saved source hash differs from the inspected policy')
        class Blob:
            def get(self, key):
                if key != source['blob_id']: raise RuntimeError('Unexpected source requested')
                return data
        def source_check(ref):
            if ref.get('source_id') != SOURCE: raise JTError('INVALID_INPUT', 'Wrong source ID')
            validate_ref(ref, source, Blob())
        try:
            validate_domain(copy.deepcopy(trace['result']), source_check)
            summary['revalidation'] = {'status':'PASSED_IN_MEMORY'}
        except JTError as error:
            summary['revalidation'] = {'status':'REPRODUCED_FAILURE','code':error.code,'message':error.message}
        invalid = []
        for i, rule in enumerate(trace['result'].get('rules', [])):
            for j, ref in enumerate(rule.get('source_refs', [])):
                try: source_check(ref)
                except (JTError, KeyError, TypeError) as error:
                    invalid.append({'path':f'rules[{i}].source_refs[{j}]', 'reference':ref, 'message':str(error)[:500]})
        summary['invalid_references'] = invalid[:10]
    r.save(root/'deliverables/release127/workflow-failed-trace.json', trace)
    report['saved_answer_diagnostic'] = summary
    r.save(checkpoint, report)
    r.save(root/'deliverables/release127/workflow-prepare-verification.json', report)
    print(json.dumps({'saved_answer_diagnostic':summary},ensure_ascii=False,indent=2), flush=True)


def main():
    sys.dont_write_bytecode = True
    argparse.ArgumentParser(description=__doc__).parse_args()
    root = Path.cwd().resolve()
    conf = json.loads((root/'.jt/config.json').read_text())
    manifest = json.loads((root/'package-manifest.json').read_text())
    if conf.get('project_id') != PROJECT or manifest.get('version') != VERSION or not manifest.get('code_hash'):
        raise RuntimeError('Expected the installed Judgment Transfer 1.0.27 project/package')
    if Path(sys.prefix).resolve() != (root/'.venv').resolve():
        executable = root/'.venv/bin/python'
        if not executable.is_file(): raise RuntimeError('Existing .venv missing; no dependency installed')
        os.execv(str(executable), [str(executable), str(Path(__file__).resolve())])
    sys.path[:0] = [str(root), str(root/'app')]
    from steps import runbook as r
    r.integrity()
    gate_dir = root/'.jt/upgrades/1.0.27'
    gate_dir.mkdir(parents=True, exist_ok=True)
    with (gate_dir/'workflow-check.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        try: run(r.API(), root, r, manifest['code_hash'])
        except r.Stop as error:
            if error.code == 'WORKFLOW_PREPARE_FAILED':
                try: diagnose(root, r)
                except Exception as diagnostic_error:
                    # Never print a token-bearing exception or request.
                    print('保存回答の追加診断は未完了: '+type(diagnostic_error).__name__, flush=True)
            raise


if __name__ == '__main__':
    try: main()
    except Exception as error:
        code = getattr(error,'code','WORKFLOW_PREPARE_STOPPED')
        message = str(error) if hasattr(error,'code') or isinstance(error,RuntimeError) else type(error).__name__
        sys.exit('STOP '+str(code)+' / '+message)

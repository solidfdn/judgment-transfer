"""One journalled LIVE source-review gate; uses the deployed application API.

No approval, rule activation, case execution, old study replay or budget reset.
The same idempotency key is reused after interruption, never a fresh generation.
"""
import hashlib
import json
from pathlib import Path
from steps import runbook as r

ASPECTS = {'purpose_scope', 'required_information', 'steps_operations',
           'decision_conditions', 'exceptions_human_review', 'completion'}
GOAL = ('Check hotel expense claims against the supplied policy and evidence. '
        'Identify what can proceed to a person for business approval, what needs '
        'clarification and what must stay on hold. Never approve or pay expenses.')


def show(report):
    safe = {k: report[k] for k in ('status', 'workspace_id', 'trace_id', 'model_calls',
        'judgment_calls', 'review_checks', 'question_count', 'diagnostic', 'request_id',
        'error_code', 'error_message', 'before_ledger', 'after_ledger') if k in report}
    print(json.dumps(safe, ensure_ascii=False, indent=2), flush=True)


def check_usage(before, after):
    session_calls = after['session']['calls'] - before['session']['calls']
    global_calls = after['budget']['calls'] - before['budget']['calls']
    if (not 0 <= session_calls <= 2 or global_calls != session_calls or
            after['session']['decisions'] != before['session']['decisions'] or
            after['additional_decisions_used'] != before['additional_decisions_used'] or
            after['extra_retry_attempts'] != before['extra_retry_attempts'] or
            after['study'] != before['study'] or
            not before['budget']['spent_usd'] <= after['budget']['spent_usd'] <= 100):
        raise r.Stop('VALIDATION_USAGE_CHANGED', '今回の資料レビュー以外の利用変化があります。記録を保持して停止します。')
    return session_calls


def run(api, root, code_hash, reviewer):
    root = Path(root)
    checkpoint = root/'.jt/upgrades/1.0.25/source-review-gate.json'
    output = root/'deliverables/release125'
    progress = r.load(checkpoint)
    if progress and progress.get('code_hash') != code_hash:
        raise r.Stop('GATE_VERSION_CHANGED', '検証記録とアプリの版が異なります。')
    if progress.get('status') in ('PASSED', 'FAILED'):
        show(progress)
        if progress['status'] == 'FAILED':
            raise r.Stop('SOURCE_GATE_FAILED', '保存済みの確認は未合格です。追加のモデル呼び出しはしていません。')
        print('保存済みの資料レビュー合格記録を確認しました。追加モデル呼び出し0回。', flush=True)
        return progress
    if not reviewer.strip():
        raise r.Stop('REVIEWER_REQUIRED', '--reviewer に確認担当者名が必要です。')
    health = api.call('/health')
    if (health.get('package_version'), health.get('code_hash'), health.get('mode'), health.get('max_cost_usd')) != ('1.0.25', code_hash, 'LIVE', 100):
        raise r.Stop('DEPLOY_MISMATCH', '1.0.25・LIVE・承認済み100ドル上限を確認できません。')
    source_path = root/'app/web/samples/expense_policy.txt'
    data = source_path.read_bytes()
    source_hash = hashlib.sha256(data).hexdigest()
    ws = api.call('/workspaces', {'goal': GOAL}, key='source-review124-workspace')
    wid = ws['workspace_id']
    source = api.call('/sources', {'workspace_id': wid, 'source_id': 'expense_policy_124'},
        key='source-review124-policy', files=(source_path.name, 'text/plain', data))
    if source['version_hash'] != source_hash:
        raise r.Stop('SOURCE_CHANGED', '投入した架空資料のハッシュが一致しません。')
    if not progress:
        before = api.call('/recovery115')
        progress = {'status': 'PREPARED', 'code_hash': code_hash, 'workspace_id': wid,
            'reviewer_name': reviewer.strip(), 'started_at': r.stamp(),
            'source_hash': source_hash, 'before': before}
        r.save(checkpoint, progress)
    if progress['workspace_id'] != wid or progress['source_hash'] != source_hash:
        raise r.Stop('GATE_INPUT_CHANGED', '確認対象が保存済みの入力と異なります。')
    review = api.call('/workspaces/'+wid).get('requirements_review')
    failure = None
    if review is None:
        progress['status'] = 'STARTED'; r.save(checkpoint, progress)
        print('架空の経費規程で資料レビューを確認します（1要求・内部生成は最大2回）。', flush=True)
        try:
            review = api.call('/requirements/review', {'workspace_id': wid, 'goal': GOAL},
                key='source-review125-check')
        except r.Stop as error:
            detail = getattr(error, 'detail', {})
            if error.code == 'NETWORK_INTERRUPTED' or detail.get('code') == 'BUSY':
                # A lost response is not permission to issue a new model call.
                raise r.Stop('SOURCE_GATE_PENDING', '通信が中断したか処理中です。同じコマンドで保存結果を確認できます。新しい要求は発行しません。') from error
            failure = {k: detail[k] for k in ('code', 'message', 'request_id', 'diagnostic') if k in detail}
            failure.setdefault('code', error.code)
    after = api.call('/recovery115')
    calls = check_usage(progress['before'], after)
    progress.update(model_calls=calls, judgment_calls=0, checked_at=r.stamp(),
        before_ledger=progress['before']['budget'], after_ledger=after['budget'])
    if failure is None:
        checks = review.get('checks', [])
        if (len(checks) != 6 or {x.get('aspect') for x in checks} != ASPECTS or
                not review.get('questions') or
                not any(o.get('status') == 'OBSERVED' for o in review.get('observations', [])) or
                review.get('source_hashes') != {'expense_policy_124': source_hash} or
                review.get('goal') != GOAL or not review.get('trace_id')):
            failure = {'code': 'REVIEW_GATE_INCOMPLETE'}
        else:
            r.save(output/'source-review.json', review)
            progress.update(trace_id=review['trace_id'], review_checks=len(checks),
                question_count=len(review['questions']))
    failed = failure is not None
    if failed:
        progress.update(status='FAILED', error_code=failure['code'], error_message=failure.get('message',''), **{k:v for k,v in failure.items() if k not in ('code','message')})
    else:
        progress['status'] = 'PASSED'
    r.save(checkpoint, progress)
    r.save(output/'source-review-verification.json', progress)
    show(progress)
    if failed:
        raise r.Stop('SOURCE_GATE_FAILED', '実際の資料レビューは未合格です。上記の診断と記録を保存しました。自動再試行はしません。')
    print('資料レビュー合格。6観点・確認質問・資料の根拠を保存しました。案件の前後比較はまだ未実行です。', flush=True)
    return progress

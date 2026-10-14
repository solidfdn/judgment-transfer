#!/usr/bin/env python3
"""Resumable study; bounded adapter retries, no replay of failed tasks."""
import argparse
from collections import Counter
import fcntl
import json
import sys
import threading
import time
import zipfile
from pathlib import Path
from steps import runbook as r

OUT = r.ROOT/'deliverables/recovery115'
CHECKPOINT = r.PRIVATE/'recovery115.json'

def waiting_call(api, path, data, key):
    finished = threading.Event()
    def heartbeat():
        seconds = 0
        while not finished.wait(10):
            seconds += 10
            print(f'  応答待機 {seconds}秒（モデル処理枠20秒・通信再試行は最大1回）', flush=True)
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    try: return api.call(path, data, key=key)
    finally: finished.set(); thread.join(timeout=1)

def export_saved(api, status):
    OUT.mkdir(parents=True, exist_ok=True)
    r.save(OUT/'study-status.json', status)
    study = status.get('study') or {}
    traffic_summary = {}
    schedule = study.get('schedules', {}).get(study.get('phase'), [])
    index = study.get('cursor', 0)
    if (study.get('stop') or {}).get('reason') == 'THREE_CONSECUTIVE_TECHNICAL_FAILURES': index -= 1
    current_item = schedule[index] if 0 <= index < len(schedule) else None
    failure_summary = None
    for label, rid in study.get('runs', {}).items():
        folder = OUT/('evidence' if label.startswith('FORMAL-') else 'development')
        filename = label.split('-', 1)[1]+'.json'
        view = api.call('/exports/'+rid)
        r.save(folder/filename, view)
        if study.get('stop') and current_item and rid == current_item['run_id']:
            task = next((t for t in view.get('tasks', []) if t['task_id'] == current_item['task_id']), None)
            if task:
                trace_ids = set(task.get('trace_ids', []))
                failure_summary = {'case_id': task['case_id'], 'arm': task['arm'], 'task_status': task['status'],
                    'error': task.get('error'), 'traces': [
                        {'trace_id': t['trace_id'], 'elapsed_ms': t.get('elapsed_ms'), 'attempts': [
                            {k: a.get(k) for k in ('attempt','status','stage','error_type','provider_code','first_text_ms',
                                'local_first_text_deadline_reached','local_total_deadline_reached','complete_stream','cost_usd')}
                            for a in t.get('attempts', [])]} for t in view.get('traces', []) if t['trace_id'] in trace_ids]}
        attempts = [a for t in view.get('traces', []) for a in t.get('attempts', [])]
        traffic_summary[label] = {'requested_tier': 'priority',
            'failed_attempts': sum(a.get('status') == 'FAILED' for a in attempts),
            'actual_response_tiers': dict(Counter(a.get('traffic_type') or 'UNKNOWN' for a in attempts)),
            'downgraded_responses': sum(a.get('priority_downgraded') is True for a in attempts),
            'attempts': len(attempts), 'recorded_cost_usd': sum(a.get('cost_usd', 0) for a in attempts)}
    r.save(OUT/'traffic-summary.json', traffic_summary)
    prior_ids = set(study.get('historical_development_runs', []))
    if study.get('diagnostic_evidence'):
        r.save(OUT/'diagnostics/paired-input-113.json', study['diagnostic_evidence'])
    failed = study.get('preserved_failed_development_check')
    if failed: prior_ids.add(failed['run_id'])
    earlier = study.get('earlier_failed_development_check')
    if earlier: prior_ids.add(earlier['run_id'])
    for rid in sorted(prior_ids):
        r.save(OUT/'prior-development'/f'{rid}.json', api.call('/exports/'+rid))
    if study.get('phase') == 'COMPLETE':
        from steps import export_evidence
        export_evidence.OUT = OUT
        export_evidence.main()
        path = OUT/'measured-summary.json'; report = r.load(path)
        report['scope'] = study['description']
        report['study_id'] = study['study_id']
        report['request_tier'] = status['request_tier']
        report['original_workspaces'] = study['original_workspaces']
        report['approvals_reused_not_newly_granted'] = True
        report['traffic_policy'] = study['traffic_policy']
        report['actual_traffic_by_run'] = {k: v for k, v in traffic_summary.items() if k.startswith('FORMAL-')}
        report['development_gate'] = study['development_gate']
        report['reliability_policy'] = study['reliability_policy']
        r.save(path, report)
        report_path = OUT/'EVALUATION_REPORT.md'
        report_path.write_text(report_path.read_text()+'\n## Recovery provenance\n\n'+study['description']+
                              '\n\nExisting human approvals were reused unchanged, not newly granted. Historical results remain in the original deliverables directory.\n'
                              '\nAll arms requested Priority. Documented Standard downgrades are included and priced at the actual tier; this is not an exclusively Priority-served benchmark. See traffic-summary.json.\n'
                              '\nThree unaffected first-attempt development successes from 1.0.14 are reused with provenance; fifteen checks execute under 1.0.15. The first no-text attempt is cancelled after ten seconds, leaving time for one retry within the unchanged twenty-second model window. All 216 formal decisions use the same streamed response protocol and API-only response schema. The unchanged business instructions, cases, rules and JSON contract remain in effect for all arms. Prior failures and the paired Cloud Shell diagnostic are preserved separately. Transient retries, latency and reserved unknown-usage costs remain in the evidence. The paired diagnostic used different actual traffic tiers and does not establish a causal speedup or Cloud Run reliability.\n')
    path = OUT/'jt_results_115.zip'
    temporary = path.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.rglob('*')):
            if file.is_file() and file not in (path, temporary): archive.write(file, file.relative_to(OUT))
    temporary.replace(path)
    print('結果ファイル: '+str(path), flush=True)
    print('実行状態: '+json.dumps({'phase':study.get('phase'), 'cursor':study.get('cursor'), 'stop':study.get('stop'),
        'recorded_model_cost_usd': status.get('budget', {}).get('spent_usd'), 'cost_cap_usd': status.get('max_cost_usd'),
        'grant_attempts_used': status.get('additional_decisions_used'), 'grant_attempt_cap': status.get('additional_decisions_limit'),
        'retry_attempts': status.get('extra_retry_attempts')}, ensure_ascii=False), flush=True)
    if failure_summary:
        print('停止箇所: '+json.dumps(failure_summary,ensure_ascii=False), flush=True)

def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    r.integrity()
    api = r.API(); health = api.call('/health')
    if health.get('code_hash') != r.manifest()['code_hash'] or health.get('package_version') != '1.0.15' or health.get('request_tier') != 'priority' or health.get('mode') != 'LIVE' or health.get('max_cost_usd') != 20:
        raise r.Stop('DEPLOY_MISMATCH', '1.0.15 / LIVE / Priority / 累計20ドルを確認できません。呼び出していません。')
    original = r.load(r.PRIVATE/'benchmark.json').get('workspaces', {})
    if set(original) != {'invoice_routing', 'support_triage'}:
        raise r.Stop('WORKSPACES_REQUIRED', '元の比較の2つのWorkspace IDを読み取れません。推測で作りません。')
    status = api.call('/recovery115')
    if not status['study']:
        status = waiting_call(api, '/recovery115/prepare', {'workspaces': original}, 'recovery115-prepare')
    r.save(CHECKPOINT, status)
    print('同一モデル / Priority要求。元の追加枠から最大251回（過去16回を含む）、管理者セッション計509回、累計モデル予算20ドルです。', flush=True)
    print('成功済み3件を保持し、残り15件を確認 → 合格時のみ216件の正式比較 → 実測証跡の出力。前回失敗の置換で既存再試行枠を1回使用し、追加通信再試行は最大4回。', flush=True)
    last = None
    try:
        while status['study']['phase'] != 'COMPLETE' and not status['study']['stop']:
            study = status['study']
            r.save(CHECKPOINT, {**status, 'pending_request': {'phase': study['phase'], 'cursor': study['cursor'], 'at': r.stamp()}})
            status = waiting_call(api, '/recovery115/advance', {}, 'recovery115-'+study['phase']+'-'+str(study['cursor']))
            r.save(CHECKPOINT, status)
            progress = status['study'].get('last_task')
            if progress and progress != last:
                print(f"{progress['phase']} {progress['completed']}/{progress['total']} 保存済み · {progress['arm']} · {progress['case_id']} · {progress.get('status', 'COMPLETED')} · 追加再試行 {status.get('extra_retry_attempts', {}).get('used', 0)}/6", flush=True)
                last = progress
    except (r.Stop, KeyboardInterrupt):
        # Read-only reconciliation. Never repeat an uncertain generation request here.
        try:
            status = api.call('/recovery115'); r.save(CHECKPOINT, status); export_saved(api, status)
        except Exception as error:
            print('読取・出力は未完了: '+type(error).__name__+'。サーバーの保存記録は消していません。', flush=True)
        raise
    export_saved(api, status)
    if status['study']['stop']:
        raise r.Stop('RECOVERY_GATE_FAILED', status['study']['stop']['reason']+'。異常の先へ追加実行せず、証跡を保存しました。')
    print('正式比較と証跡の出力が完了しました。製品全体の完成・提出完了ではありません。', flush=True)
    for name, wid in status['study']['workspaces'].items():
        print('保存結果を画面で確認するWorkspace: '+name+' / '+wid, flush=True)
    print('次に確認するもの: 実測の品質判定、実ブラウザでの最終操作、実録動画、公式テンプレート、提出記録。', flush=True)

if __name__ == '__main__':
    try:
        with (r.PRIVATE/'runbook.lock').open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise r.Stop('RUNBOOK_BUSY', '別の工程が実行中です。並行実行しません。')
            main()
    except r.Stop as error:
        print('STOP '+error.code+' / '+str(error), flush=True); sys.exit(1)
    except KeyboardInterrupt:
        print('中断しました。再開は同じコマンドです。確定済み判断は繰り返しません。', flush=True); sys.exit(130)

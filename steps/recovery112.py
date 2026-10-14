#!/usr/bin/env python3
"""One resumable authorized operation; no failed model-call retries."""
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

OUT = r.ROOT/'deliverables/recovery112'
CHECKPOINT = r.PRIVATE/'recovery112.json'

def waiting_call(api, path, data, key):
    finished = threading.Event()
    def heartbeat():
        seconds = 0
        while not finished.wait(10):
            seconds += 10
            print(f'  応答待機 {seconds}秒（新しいモデル再試行はしません）', flush=True)
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    try: return api.call(path, data, key=key)
    finally: finished.set(); thread.join(timeout=1)

def export_saved(api, status):
    OUT.mkdir(parents=True, exist_ok=True)
    r.save(OUT/'study-status.json', status)
    study = status.get('study') or {}
    traffic_summary = {}
    for label, rid in study.get('runs', {}).items():
        folder = OUT/('evidence' if label.startswith('FORMAL-') else 'development')
        filename = label.split('-', 1)[1]+'.json'
        view = api.call('/exports/'+rid)
        r.save(folder/filename, view)
        attempts = [a for t in view.get('traces', []) for a in t.get('attempts', [])]
        traffic_summary[label] = {'requested_tier': 'priority',
            'actual_response_tiers': dict(Counter(a.get('traffic_type') or 'UNKNOWN' for a in attempts)),
            'downgraded_responses': sum(a.get('priority_downgraded') is True for a in attempts),
            'attempts': len(attempts), 'recorded_cost_usd': sum(a.get('cost_usd', 0) for a in attempts)}
    r.save(OUT/'traffic-summary.json', traffic_summary)
    prior_ids = {x['run_id'] for x in study.get('reused_development_checks', [])}
    failed = study.get('preserved_failed_development_check')
    if failed: prior_ids.add(failed['run_id'])
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
        r.save(path, report)
        report_path = OUT/'EVALUATION_REPORT.md'
        report_path.write_text(report_path.read_text()+'\n## Recovery provenance\n\n'+study['description']+
                              '\n\nExisting human approvals were reused unchanged, not newly granted. Historical results remain in the original deliverables directory.\n'
                              '\nAll arms requested Priority. Documented Standard downgrades are included and priced at the actual tier; this is not an exclusively Priority-served benchmark. See traffic-summary.json.\n'
                              '\nThe development gate reuses two unchanged 1.0.11 checks and adds sixteen 1.0.12 checks. The previous failed third check is preserved separately. All 216 formal decisions use 1.0.12 only.\n')
    path = OUT/'jt_results_112.zip'
    temporary = path.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.rglob('*')):
            if file.is_file() and file not in (path, temporary): archive.write(file, file.relative_to(OUT))
    temporary.replace(path)
    print('結果ファイル: '+str(path), flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorize-one-replacement', action='store_true')
    args = parser.parse_args()
    r.integrity()
    api = r.API(); health = api.call('/health')
    if health.get('code_hash') != r.manifest()['code_hash'] or health.get('package_version') != '1.0.12' or health.get('request_tier') != 'priority' or health.get('mode') != 'LIVE' or health.get('max_cost_usd') != 20:
        raise r.Stop('DEPLOY_MISMATCH', '1.0.12 / LIVE / Priority / 累計20ドルを確認できません。呼び出していません。')
    original = r.load(r.PRIVATE/'benchmark.json').get('workspaces', {})
    if set(original) != {'invoice_routing', 'support_triage'}:
        raise r.Stop('WORKSPACES_REQUIRED', '元の比較の2つのWorkspace IDを読み取れません。推測で作りません。')
    status = api.call('/recovery112')
    if not status['study']:
        status = waiting_call(api, '/recovery112/prepare', {'workspaces': original, 'authorize_one_replacement': args.authorize_one_replacement}, 'recovery112-prepare')
    r.save(CHECKPOINT, status)
    print('同一モデル / Priority。追加判断は前回3回を含め最大235回、累計モデル予算は20ドルのままです。', flush=True)
    print('合格済み2件を再利用＋残り16件の限定確認 → 合格時のみ216件の正式比較 → 実測証跡の出力。過去の結果は上書きしません。', flush=True)
    last = None
    try:
        while status['study']['phase'] != 'COMPLETE' and not status['study']['stop']:
            study = status['study']
            r.save(CHECKPOINT, {**status, 'pending_request': {'phase': study['phase'], 'cursor': study['cursor'], 'at': r.stamp()}})
            status = waiting_call(api, '/recovery112/advance', {}, 'recovery112-'+study['phase']+'-'+str(study['cursor']))
            r.save(CHECKPOINT, status)
            progress = status['study'].get('last_task')
            if progress and progress != last:
                print(f"{progress['phase']} {progress['completed']}/{progress['total']} 保存済み · {progress['arm']} · {progress['case_id']}", flush=True)
                last = progress
    except (r.Stop, KeyboardInterrupt):
        # Read-only reconciliation. Never repeat an uncertain generation request here.
        try:
            status = api.call('/recovery112'); r.save(CHECKPOINT, status); export_saved(api, status)
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

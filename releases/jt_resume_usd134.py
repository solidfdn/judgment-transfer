#!/usr/bin/env python3
"""One separately recorded USD retry; keep the failed run and 24-attempt ceiling."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import types

CODE_HASH='09a190c869c8bffc88fd2e4ac96f266159a89f5f3800384f70bd9d3864f072c3'
CONTROLLER_HASH='9d225b37eefeff335a1ab8f4b04c3780032c943947ff4bdb53919133c919ca4b'
FAILED_RUN='run_065ae402f3697e77a4444deb9aaa1ef5'
FAILED_TRACE='trace_e43a1f7406be41798b1d78e94735200f'
OLD='.jt/upgrades/1.0.34/usd-demo.json'
NEW='.jt/upgrades/1.0.34/usd-demo-resume1.json'


def revised_source(raw):
    if hashlib.sha256(raw).hexdigest()!=CONTROLLER_HASH:
        raise RuntimeError('Installed USD controller differs from the reviewed 1.0.34 file.')
    text=raw.decode()
    for old,new in [("out=root/'deliverables/release134/usd';path=root/'.jt/upgrades/1.0.34/usd-demo.json'",
        "out=root/'deliverables/release134/usd-resume1';path=root/'.jt/upgrades/1.0.34/usd-demo-resume1.json'"),
        ("key='usd134-'+name","key='usd134resume1-'+name")]:
        if text.count(old)!=1:raise RuntimeError('The controller progression does not match the reviewed source.')
        text=text.replace(old,new)
    return text


def immutable(view):
    return {k:view.get(k) for k in ('run','tasks','receipts','traces','shared_preparation_traces','source_metadata','case_evidence')}


class BoundedAPI:
    def __init__(self,api,r,initial_calls):
        self.api,self.r,self.initial_calls=api,r,initial_calls

    def call(self,path,data=None,key=None,files=None):
        attempts=2 if path.endswith('/step') or path=='/questions' else 1 if path=='/teachings' else 0
        if data is not None and attempts:
            usage=self.api.call('/recovery115')
            used=usage['session']['calls']-self.initial_calls
            if used<0 or used+attempts>24:
                raise self.r.Stop('USD_ATTEMPT_LIMIT','最初のUSD検証を含む24回の枠内で続行できません。追加要求は送りません。')
        return self.api.call(path,data,key=key,files=files)


def verify_stopped(view):
    tasks=view.get('tasks',[])
    if (view.get('run',{}).get('run_id')!=FAILED_RUN or view['run'].get('code_hash')!=CODE_HASH or
        len(tasks)!=4 or [t['status'] for t in tasks]!=['COMPLETED']*3+['FAILED'] or
        tasks[3]['case_id']!='expense_review_usd_dev_04' or tasks[3].get('receipt_ids') or
        tasks[3].get('trace_ids')!=[FAILED_TRACE] or tasks[3].get('error',{}).get('code')!='MODEL_FAILED'):
        raise RuntimeError('The saved stopped run differs from the inspected four-case execution.')
    trace=next((t for t in view.get('traces',[]) if t['trace_id']==FAILED_TRACE),{})
    attempts=trace.get('attempts',[])
    if len(attempts)!=2 or any(a.get('status')!='FAILED' or a.get('error_type')!='ReadTimeout' or
        a.get('chunk_count')!=0 or a.get('generation_timeout_ms')!=60000 for a in attempts):
        raise RuntimeError('This retry is limited to the inspected two zero-response timeouts.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-reviewed-usd',action='store_true')
    parser.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if not args.resume_reviewed_usd or not args.reviewer.strip():parser.error('--resume-reviewed-usd and a reviewer are required')
    root=Path.cwd().resolve()
    if not (root/'.jt/config.json').is_file():raise RuntimeError('Run inside Judgment_Transfer_Runbook_v1.0.')
    if Path(sys.prefix).resolve()!=(root/'.venv').resolve():
        executable=str(root/'.venv/bin/python')
        os.execv(executable,[executable,str(Path(__file__).resolve()),*sys.argv[1:]])
    sys.dont_write_bytecode=True;sys.path[:0]=[str(root),str(root/'app')]
    from steps import runbook as r
    from core.models import digest
    r.integrity()
    with (root/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        manifest=r.load(root/'package-manifest.json');old_bytes=(root/OLD).read_bytes();old=json.loads(old_bytes)
        if (manifest.get('version'),manifest.get('code_hash'))!=('1.0.34',CODE_HASH):raise RuntimeError('Expected the unchanged 1.0.34 package.')
        if old.get('status')!='FAILED' or old.get('pending')!='baseline-3' or old.get('baseline_run_id')!=FAILED_RUN or old.get('reviewer_name')!=args.reviewer.strip():
            raise RuntimeError('The previous checkpoint or responsible person differs.')
        api=r.API();health=api.call('/health')
        if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=('1.0.34',CODE_HASH,'LIVE',100):
            raise RuntimeError('The live package/settings differ. No model request was sent.')
        stopped=api.call('/exports/'+FAILED_RUN);verify_stopped(stopped);before_hash=digest(immutable(stopped))
        ws=api.call('/workspaces/'+stopped['run']['workspace_id'])
        if ws.get('version')!=0 or ws.get('frozen') or ws.get('teaching_ids') or ws.get('run_ids')!=[FAILED_RUN]:
            raise RuntimeError('The stopped workspace has changed. No replacement run was started.')
        source=revised_source((root/'steps/usd_demo134.py').read_bytes())
        module=types.ModuleType('usd134_separate_resume');module.__file__=str(root/'steps/usd_demo134.py')
        exec(compile(source,'usd134-reviewed-separate-retry','exec'),module.__dict__)
        record=root/'deliverables/release134/usd-resume1/recovery-origin.json'
        origin={'original_run_id':FAILED_RUN,'original_failed_trace_id':FAILED_TRACE,'original_export_hash':before_hash,
            'initial_usd_session_calls':old['before']['session']['calls'],'original_checkpoint_sha256':hashlib.sha256(old_bytes).hexdigest(),
            'reviewer_name':args.reviewer.strip(),'recorded_at':r.stamp(),'total_usd_attempt_ceiling':24,
            'method':'One separate workspace using identical USD inputs and reviewed initial conditions; remeasure four baseline cases. Preserve the original three successes and failed fourth case.'}
        prior=r.load(record)
        if prior:
            if any(prior[k]!=v for k,v in origin.items() if k!='recorded_at'):raise RuntimeError('Recovery provenance changed.')
        else:r.save(record,origin)
        print('再デプロイせず、USD比較を別記録で一度だけ再開します。旧3件の成功・4件目の失敗・全使用量を保持します。',flush=True)
        try:
            value=module.run(root,BoundedAPI(api,r,old['before']['session']['calls']),r,args.reviewer.strip())
        except r.Stop:
            saved=r.load(root/NEW)
            for kind in ('baseline','after','holdout'):
                rid=saved.get(kind+'_run_id')
                if not rid:continue
                view=api.call('/exports/'+rid);r.save(record.parent/(kind+'-latest.json'),view)
                ids={tid for t in view['tasks'] if t['status']=='FAILED' for tid in t.get('trace_ids',[])}
                for trace in view.get('traces',[]):
                    if trace['trace_id'] in ids:print(json.dumps({'saved_failure':{k:trace.get(k) for k in ('trace_id','elapsed_ms','settings','attempts','error')}},ensure_ascii=False,indent=2),flush=True)
            raise
        finally:
            if (root/OLD).read_bytes()!=old_bytes or digest(immutable(api.call('/exports/'+FAILED_RUN)))!=before_hash:
                raise RuntimeError('The original stopped record changed. Investigate without further generation.')
        if value.get('status')=='PASSED':
            usage=api.call('/recovery115');report={**value['report'],'original_stopped_run_preserved':True,
                'total_usd_model_attempts_including_original':usage['session']['calls']-old['before']['session']['calls']}
            r.save(record.parent/'completion.json',report)
            print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit('STOP '+str(getattr(error,'code','USD_RESUME_STOPPED'))+' / '+str(error))

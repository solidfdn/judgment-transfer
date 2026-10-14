#!/usr/bin/env python3
"""Short-command, journalled Cloud Shell runbook. No generated code or silent upgrades."""
import argparse
import fcntl
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import urllib.error
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'.jt';PRIVATE.mkdir(exist_ok=True);PRIVATE.chmod(0o700)
STATE=PRIVATE/'state.json';CONFIG=PRIVATE/'config.json'
STEPS={'00':'パッケージ確認','01':'Google認証と新規環境の設定','02':'専用プロジェクトと基盤の作成','03':'固定したオフライン受入試験','04':'Cloud Runへ非公開デプロイ','05':'Google上のLIVE接続・素材読取確認','06':'審査用URLの公開','07':'人の承認後に正式比較を実行','08':'実測証跡と提出用ソースを出力'}

class Stop(Exception):
    def __init__(self,code,message):self.code=code;super().__init__(message)
def hashed(data):return hashlib.sha256(data if isinstance(data,bytes) else json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def load(path,default=None):return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2));temporary.chmod(0o600);os.replace(temporary,path)
def state():return load(STATE,{'package_version':'1.0.0','steps':{},'actions':{}})
def config():
    if not CONFIG.exists():raise Stop('CONFIG_REQUIRED','先に bash jt 01 を実行してください。')
    return load(CONFIG)
def manifest():return load(ROOT/'package-manifest.json')
def integrity():
    m=manifest()
    if not m:raise Stop('MANIFEST_MISSING','配布ZIPの package-manifest.json がありません。')
    changed=[name for name,value in m['files'].items() if not (ROOT/name).is_file() or hashed((ROOT/name).read_bytes())!=value]
    if changed:raise Stop('PACKAGE_CHANGED','承認済みパッケージと異なるファイル: '+', '.join(changed[:8])+'。仕様変更か修正かを確認し、新版として記録してください。自動修正しません。')
    return m
def run(command,action=None,sensitive=False,input_bytes=None):
    s=state()
    if action and s['actions'].get(action,{}).get('status')=='DONE':return s['actions'][action].get('result','')
    if action:
        s['actions'][action]={'status':'RUNNING','started_at':stamp(),'command_hash':hashed(command)};save(STATE,s)
    # Logs are private and never included in the shareable support report.
    log=PRIVATE/('command-'+uuid.uuid4().hex+'.log')
    error_log=log.with_suffix('.stderr')
    with log.open('wb') as out,error_log.open('wb') as err:
        process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.PIPE if input_bytes is not None else None,stdout=out,stderr=err)
        if input_bytes is not None:process.stdin.write(input_bytes);process.stdin.close()
        last=time.monotonic()
        while process.poll() is None:
            time.sleep(.2)
            if time.monotonic()-last>20:print('  処理中: '+(action or Path(command[0]).name),flush=True);last=time.monotonic()
    stdout=log.read_text(errors='replace');output=stdout+error_log.read_text(errors='replace');error_log.unlink(missing_ok=True)
    if sensitive:log.unlink(missing_ok=True)
    else:log.write_text(output);log.chmod(0o600)
    if process.returncode:
        if action:
            diagnostic='\n'.join(line for line in output.splitlines() if any(x in line for x in ('ERROR:','PERMISSION_DENIED','FAILED_PRECONDITION','FAILED (','AssertionError','Error:')))[:800] if not sensitive else 'Sensitive command stopped; output not retained.'
            c=load(CONFIG)
            for value in [c.get(k,'') for k in ('account','billing_account','project_id','bucket','runtime_sa','build_sa','url')]:
                if value:diagnostic=diagnostic.replace(value,'[redacted]')
            diagnostic=re.sub(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}','[email]',diagnostic,flags=re.I)
            s=state();s['actions'][action].update(status='FAILED',exit_code=process.returncode,diagnostic=diagnostic,log=log.name if not sensitive else None);save(STATE,s)
        raise Stop('COMMAND_FAILED',f'{action or command[0]} が終了コード {process.returncode} で停止しました。'+('' if sensitive else '\n詳細は手元の .jt/'+log.name+' を確認。共有用は bash jt support。'))
    if action:
        s=state();s['actions'][action].update(status='DONE',finished_at=stamp(),result='' if sensitive else stdout[:12000]);save(STATE,s)
    return stdout.strip()
def gc(*args,action=None,sensitive=False,project=True):
    command=['gcloud',*args,'--quiet']
    if project:command+=['--project',config()['project_id']]
    return run(command,action,sensitive)
def gc_json(*args,project=True):return json.loads(gc(*args,'--format=json',project=project) or '{}')
def ask(prompt,default=''):
    answer=input(prompt+(f' [{default}]' if default else '')+': ').strip()
    return answer or default
def exists(command):
    result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode==0:return True
    error=result.stderr.decode(errors='replace').lower()
    if any(x in error for x in ('not_found','not found','does not exist')):return False
    raise Stop('RESOURCE_CHECK_FAILED','リソース確認が拒否されました。存在しないと決めつけて新規作成せず停止します。権限・組織ポリシーを確認してください。')
def ensure(action,read,create):
    s=state()
    if s['actions'].get(action,{}).get('status')=='DONE':return
    if exists(['gcloud',*read,'--project',config()['project_id'],'--format=json','--quiet']):
        s['actions'][action]={'status':'DONE','finished_at':stamp(),'result':'Found in this runbook-owned project.'};save(STATE,s)
    else:gc(*create,action=action)

def step00():
    m=integrity();print('一致: '+str(len(m['files']))+' ファイル / package '+m['version'])
    if sys.version_info<(3,12):raise Stop('PYTHON_VERSION','Python 3.12以上のCloud Shellで実行してください。依存関係はPython 3.12で確認しています。')
    if not shutil.which('gcloud'):raise Stop('CLOUD_SHELL_REQUIRED','この実行手順はGoogle Cloud Shell用です。ZIPをCloud ShellのHOMEへアップロードしてください。')

def step01():
    if CONFIG.exists():print('保存済み設定を使用: '+config()['project_id']);return
    if not shutil.which('gcloud'):raise Stop('CLOUD_SHELL_REQUIRED','Google Cloud Shellを開いてください。')
    accounts=gc_json('auth','list','--filter=status:ACTIVE',project=False)
    if not accounts:raise Stop('GOOGLE_AUTH_REQUIRED','Cloud Shell画面のAuthorizeを完了して再実行してください。認証情報をチャットへ貼る必要はありません。')
    account=accounts[0]['account'];print('実行アカウント: '+account)
    billing=gc_json('billing','accounts','list','--filter=open=true',project=False)
    if not billing:raise Stop('BILLING_REQUIRED','利用できる請求先がありません。Cloud Consoleで課金を有効にしてから再実行してください。')
    for i,item in enumerate(billing,1):print(f"  {i}: {item.get('displayName','Billing account')} ({item['name'].split('/')[-1]})")
    selection=ask('使用する請求先の番号','1' if len(billing)==1 else '')
    if not selection.isdigit() or not 1<=int(selection)<=len(billing):raise Stop('BILLING_SELECTION','表示された番号を指定してください。')
    project='jt-'+dt.datetime.now().strftime('%y%m%d')+'-'+secrets.token_hex(3)
    org=ask('新規プロジェクトの組織ID（個人アカウントはEnter）')
    if org and not org.isdigit():raise Stop('ORGANIZATION_ID','組織IDは数字です。表示名ではありません。')
    cfg={'project_id':project,'region':'asia-northeast1','billing_account':billing[int(selection)-1]['name'].split('/')[-1],
         'organization_id':org,'account':account,'owner_marker':secrets.token_hex(6),'bucket':project+'-sources','service':'judgment-transfer',
         'runtime_sa':'jt-runtime@'+project+'.iam.gserviceaccount.com','build_sa':'jt-build@'+project+'.iam.gserviceaccount.com',
         'model':'gemini-3.5-flash','model_location':'global','model_budget_usd':20,'infrastructure_alert_usd':30,'price_date':'2026-10-10'}
    save(CONFIG,cfg);print('設定完了。新規プロジェクト: '+project+'。次の02で課金対象の専用環境を作成します。')

def step02():
    c=config();p=c['project_id'];marker=c['owner_marker']
    if exists(['gcloud','projects','describe',p,'--format=json','--quiet']):
        description=gc_json('projects','describe',p,project=False)
        if description.get('labels',{}).get('jt-runbook')!=marker:raise Stop('PROJECT_OWNERSHIP','この実行が作ったプロジェクトと確認できません。既存プロジェクトには変更しません。')
    else:
        args=['projects','create',p,'--name=Judgment Transfer','--labels=jt-managed=true,jt-runbook='+marker]
        if c['organization_id']:args+=['--organization='+c['organization_id']]
        gc(*args,action='02-project',project=False)
    gc('billing','projects','link',p,'--billing-account='+c['billing_account'],action='02-billing',project=False)
    gc('services','enable','run.googleapis.com','cloudbuild.googleapis.com','artifactregistry.googleapis.com','firestore.googleapis.com','storage.googleapis.com','aiplatform.googleapis.com','secretmanager.googleapis.com','iam.googleapis.com','cloudbilling.googleapis.com','billingbudgets.googleapis.com',action='02-apis')
    for name,email in [('jt-runtime',c['runtime_sa']),('jt-build',c['build_sa'])]:
        ensure('02-'+name,['iam','service-accounts','describe',email],['iam','service-accounts','create',name,'--display-name='+name])
    for role in ('roles/datastore.user','roles/aiplatform.user'):
        gc('projects','add-iam-policy-binding',p,'--member=serviceAccount:'+c['runtime_sa'],'--role='+role,'--condition=None',action='02-runtime-'+role.split('/')[-1])
    gc('projects','add-iam-policy-binding',p,'--member=serviceAccount:'+c['build_sa'],'--role=roles/run.builder','--condition=None',action='02-build-role')
    for email in (c['runtime_sa'],c['build_sa']):
        gc('iam','service-accounts','add-iam-policy-binding',email,'--member=user:'+c['account'],'--role=roles/iam.serviceAccountUser',action='02-act-as-'+email.split('@')[0])
    ensure('02-firestore',['firestore','databases','describe','--database=(default)'],['firestore','databases','create','--database=(default)','--location='+c['region'],'--edition=standard','--type=firestore-native'])
    ensure('02-bucket',['storage','buckets','describe','gs://'+c['bucket']],['storage','buckets','create','gs://'+c['bucket'],'--location='+c['region'],'--uniform-bucket-level-access','--public-access-prevention'])
    gc('storage','buckets','add-iam-policy-binding','gs://'+c['bucket'],'--member=serviceAccount:'+c['runtime_sa'],'--role=roles/storage.objectAdmin',action='02-bucket-role')
    for name in ('jt-session','jt-admin'):
        if not exists(['gcloud','secrets','describe',name,'--project',p,'--quiet','--format=json']):
            with tempfile.NamedTemporaryFile(dir=PRIVATE,delete=False) as f:
                f.write(secrets.token_hex(32).encode());secret_path=Path(f.name)
            try:gc('secrets','create',name,'--replication-policy=automatic','--data-file='+str(secret_path),action='02-secret-'+name,sensitive=True)
            finally:secret_path.unlink(missing_ok=True)
        gc('secrets','add-iam-policy-binding',name,'--member=serviceAccount:'+c['runtime_sa'],'--role=roles/secretmanager.secretAccessor',action='02-secret-role-'+name)
    number=gc('projects','describe',p,'--format=value(projectNumber)',project=False)
    budget_name='JT-'+marker
    budgets=gc_json('billing','budgets','list','--billing-account='+c['billing_account'],project=False)
    if not any(b.get('displayName')==budget_name for b in budgets):
        gc('billing','budgets','create','--billing-account='+c['billing_account'],'--display-name='+budget_name,'--budget-amount=30USD','--filter-projects=projects/'+number,'--threshold-rule=percent=0.5','--threshold-rule=percent=0.9','--threshold-rule=percent=1.0',action='02-budget-alert',project=False)
    print('専用基盤を作成しました。$30通知は利用停止の上限ではありません。モデルの$20停止条件はアプリ側で別に適用します。')

def step03():
    env=ROOT/'.venv';python=env/'bin/python'
    if not python.exists():run([sys.executable,'-m','venv',str(env)],action='03-venv')
    run([str(python),'-m','pip','install','--disable-pip-version-check','-r','requirements.lock'],action='03-dependencies')
    # One fixed suite. No optional test discovery and no performance benchmark here.
    run([str(python),'tests/acceptance.py','--report',str(PRIVATE/'offline-acceptance.json')],action='03-acceptance')
    print('固定した受入試験が完了しました。成功済みの試験は再実行しません。')

def step04():
    c=config();m=manifest();env={'JT_MODE':'LIVE','JT_STORE':'firestore','GOOGLE_CLOUD_PROJECT':c['project_id'],'JT_BUCKET':c['bucket'],
        'JT_MODEL_BUDGET_USD':'20','JT_INPUT_USD_PER_MILLION':'1.50','JT_OUTPUT_USD_PER_MILLION':'9.00','JT_CODE_HASH':m['code_hash']}
    gc('run','deploy',c['service'],'--source='+str(ROOT),'--region='+c['region'],'--service-account='+c['runtime_sa'],
       '--build-service-account=projects/'+c['project_id']+'/serviceAccounts/'+c['build_sa'],
       '--set-env-vars='+','.join(k+'='+v for k,v in env.items()),'--set-secrets=JT_SESSION_SECRET=jt-session:latest,JT_ADMIN_SECRET=jt-admin:latest',
       '--cpu=1','--memory=1Gi','--concurrency=4','--min=0','--max=2','--timeout=180','--cpu-throttling','--no-cpu-boost',
       '--invoker-iam-check','--no-allow-unauthenticated',action='04-deploy')
    c['url']=gc('run','services','describe',c['service'],'--region='+c['region'],'--format=value(status.url)');save(CONFIG,c)
    print('非公開デプロイ完了: '+c['url'])

class API:
    def __init__(self,admin=True,private=False):
        self.url=config()['url'];self.headers={}
        if admin:self.headers['X-JT-Admin']=gc('secrets','versions','access','latest','--secret=jt-admin',sensitive=True)
        if private:self.headers['Authorization']='Bearer '+gc('auth','print-identity-token',project=False,sensitive=True)
    def call(self,path,data=None,key=None,files=None):
        named = path in ('/domains/approve','/domains/rollback','/cases/import','/cases/confirm','/runs','/workspaces/freeze','/history/fix') or path.startswith('/teachings/') and path.endswith('/approve')
        if data is not None and named:
            data=dict(data)
            if not data.get('reviewer_name'):data['reviewer_name']=os.getenv('JT_REVIEWER_NAME','').strip()
            if not data['reviewer_name']:raise Stop('REVIEWER_REQUIRED','記録を確定する担当者名を JT_REVIEWER_NAME に設定してください。自動で別の氏名は補いません。')
        headers=dict(self.headers);headers['Idempotency-Key']=key or str(uuid.uuid4())
        if files:
            boundary='jt'+hashed(key or str(uuid.uuid4()))[:24];chunks=[]
            for name,value in data.items():chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            filename,mime,content=files
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode()+content+b'\r\n')
            chunks.append(f'--{boundary}--\r\n'.encode());payload=b''.join(chunks);headers['Content-Type']='multipart/form-data; boundary='+boundary
        else:
            payload=json.dumps(data).encode() if data is not None else None;headers['Content-Type']='application/json'
        req=urllib.request.Request(self.url+'/api/v1'+path,data=payload,headers=headers,method='POST' if payload is not None else 'GET')
        try:
            with urllib.request.urlopen(req,timeout=170) as response:value=json.load(response)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read()).get('error',{});message=detail.get('code','HTTP_'+str(error.code))+': '+detail.get('message','Request stopped.')
            except (ValueError,AttributeError):message='HTTP_'+str(error.code)+'。Cloud Runの権限またはポリシーを確認してください。'
            raise Stop('APP_REQUEST_FAILED',message)
        except (urllib.error.URLError,TimeoutError):raise Stop('NETWORK_INTERRUPTED','通信が中断されました。保存済みrun IDと同じrequest IDで再開できます。')
        if 'error' in value:raise Stop('APP_REQUEST_FAILED',value['error']['code']+': '+value['error']['message'])
        return value

def step05():
    api=API(private=True);health=api.call('/health')
    if health['mode']!='LIVE' or health['code_hash']!=manifest()['code_hash']:raise Stop('DEPLOY_MISMATCH','モデルモードまたはコード版が異なります。')
    ws=api.call('/workspaces',{'goal':'Describe the supplier invoice routing procedure and the evidence needed before a case enters an isolated approval queue. Never pay invoices.'},key='smoke-workspace-v1')
    wid=ws['workspace_id'];folder=ROOT/'app/fixtures/invoice_routing'
    for filename,mime,path in [('source_sop.txt','text/plain',folder/'source_sop.txt'),('walkthrough.mp4','video/mp4',folder/'media/synthetic_invoice_walkthrough_15s.mp4')]:
        api.call('/sources',{'workspace_id':wid},key='smoke-'+filename.replace('.','-'),files=(filename,mime,path.read_bytes()))
    attempt=state()['steps']['05'].get('attempt',1)
    draft=api.call('/sources/extract',{'workspace_id':wid},key='smoke-extract-v1-'+str(attempt))
    summary=api.call('/workspaces/'+wid);sources={s['source_id']:s for s in summary['sources']}
    kinds={sources[r['source_id']]['mime'] for o in draft.get('observations',[]) if o['status']=='OBSERVED' for r in o['source_refs'] if r['source_id'] in sources}
    report={'health':health,'workspace_id':wid,'trace_ids':[draft['trace_id']],'observed_mime_types':sorted(kinds),'checked_at':stamp()}
    save(PRIVATE/'live-smoke.json',report)
    if not {'text/plain','video/mp4'}.issubset(kinds):raise Stop('MEDIA_EVIDENCE_REQUIRED','Geminiの応答は保存されましたが、文書と動画の両方にOBSERVED参照が揃っていません。T04は未完了として停止します。素材・応答を確認し、再試行理由を記録してください。モデルを自動変更しません。')
    print('LIVE接続と文書・動画の参照検証が完了。性能比較はまだ実行していません。')

def step06():
    c=config()
    gc('run','services','update',c['service'],'--region='+c['region'],'--no-invoker-iam-check',action='06-public')
    health=API(admin=False).call('/health')
    if health['mode']!='LIVE':raise Stop('MODE_MISMATCH','公開URLがLIVEではありません。')
    print('審査用URL: '+c['url']);print('次に画面で2つのサンプルを人がレビューし、判断ルールを承認します。手順はSTART_HERE_ja.mdの07を参照。')

def benchmark_step(api,rid,entry,evaluation,label,before):
    provider_stop=None
    pending=entry.get('pending_step')
    if not pending:
        task=next((t for t in before['tasks'] if t['status']=='PENDING' or t['status']=='LEASED' and t['lease_until']<=time.time()),None)
        if not task:raise Stop('BENCHMARK_PENDING','対象は実行中です。状態を保存して停止しました。同じ工程で後から再開できます。')
        n=entry['next_step'];pending={'task_id':task['task_id'],'case_id':task['case_id'],'step_index':task['step_index'],
                                   'number':n,'key':'bench-'+rid+'-'+str(n)}
        entry['pending_step']=pending
        save(PRIVATE/'benchmark.json',evaluation) # BEFORE submission; no lost failed-task checkpoint.
    task=next((t for t in before['tasks'] if t['task_id']==pending['task_id']),None)
    if not task:raise Stop('BENCHMARK_TASK_MISSING','保存した対象が見つかりません。比較を停止しました。')
    progressed=lambda t:t['status'] in ('COMPLETED','FAILED','CANCELLED') or t['step_index']>pending['step_index']
    value=before
    if not progressed(task):
        done=threading.Event();started=time.monotonic()
        def progress():
            while not done.wait(10):print(label+f' · 応答待機 {int(time.monotonic()-started)}秒',flush=True)
        worker=threading.Thread(target=progress,daemon=True);worker.start()
        try:api.call('/runs/'+rid+'/step',{},key=pending['key'])
        except Stop as error:
            pending['api_error']={'code':error.code,'message':str(error)}
            save(PRIVATE/'benchmark.json',evaluation)
        finally:done.set();worker.join(timeout=1)
        value=api.call('/runs/'+rid)
        task=next((t for t in value['tasks'] if t['task_id']==pending['task_id']),None)
        if not task or not progressed(task):
            raise Stop('BENCHMARK_PENDING','処理の完了を確認できず停止しました。対象とリクエストIDは保存済みです。')
    if task['status']=='FAILED':
        code=task.get('error',{}).get('code','UNKNOWN')
        if code in ('COST_LIMIT','CALL_LIMIT','UNAUTHORIZED','ADMIN_REQUIRED','PERMISSION_DENIED'):
            raise Stop(code,'予算・回数・権限の停止条件に達しました。対象と失敗記録を保持しています。')
        if code=='MODEL_FAILED':
            export=api.call('/exports/'+rid)
            ids=set(task.get('trace_ids',[]))
            denied=any(str(a.get('provider_code')) in ('401','403') for tr in export['traces'] if tr['trace_id'] in ids for a in tr.get('attempts',[]))
            if denied:raise Stop('PERMISSION_DENIED','Googleの認証・権限エラーを記録したため停止しました。自動変更はしません。')
            attempts=[a for tr in export['traces'] if tr['trace_id'] in ids for a in tr.get('attempts',[]) if a.get('status')=='FAILED']
            providers=sorted({str(a.get('provider_code','unknown')) for a in attempts})
            entry['provider_stop']={'task_id':task['task_id'],'trace_ids':task.get('trace_ids',[]),'provider_codes':providers,'recorded_at':stamp()}
            # Keep this terminal failure, but never create a chain of new failed
            # cases against an unavailable provider. No automatic retry/backoff.
            provider_stop=Stop('PROVIDER_BLOCKED','モデル応答の失敗を保存して停止しました（Googleコード: '+', '.join(providers or ['unknown'])+'）。次の案件は呼び出していません。失敗記録・残りの案件・予算を保持しています。')
        entry.setdefault('failures',[]).append({'task_id':task['task_id'],'case_id':task['case_id'],'code':code,'recorded_at':stamp()})
    entry['next_step']=pending['number']+1
    entry.pop('pending_step',None)
    save(PRIVATE/'benchmark.json',evaluation)
    counts=value['metrics']['counts']
    print(label+f" · step {entry['next_step']} 保存済み / 終了 {counts['COMPLETED']+counts['FAILED']}/{value['metrics']['total']}、失敗 {counts['FAILED']}",flush=True)
    if provider_stop:raise provider_stop

def step07():
    c=config();api=API();evaluation=load(PRIVATE/'benchmark.json',{'workspaces':{},'runs':{}})
    health=api.call('/health')
    if health['mode']!='LIVE' or health['code_hash']!=manifest()['code_hash']:raise Stop('DEPLOY_MISMATCH','比較対象のアプリ版が一致しません。')
    for sample in ('invoice_routing','support_triage'):
        wid=evaluation['workspaces'].get(sample)
        if not wid:wid=ask(sample+' の管理者Workspace ID');evaluation['workspaces'][sample]=wid;save(PRIVATE/'benchmark.json',evaluation)
        if not re.fullmatch(r'ws_[a-f0-9]{32}',wid):raise Stop('WORKSPACE_ID','画面の管理者欄のWorkspace IDを入力してください。')
        ws=api.call('/workspaces/'+wid)
        if ws['sample']!=sample or ws['mode']!='LIVE' or not ws['approved_count']:raise Stop('HUMAN_REVIEW_REQUIRED','このサンプルのLIVEワークスペースで、人が提案ルールを確認・承認してください。MOCK結果は流用できません。')
        api.call('/workspaces/freeze',{'workspace_id':wid},key='freeze-'+wid)
        for arm in ('A_SOURCE_ONLY','B_TEXT_ADDED','C_JT_RULES'):
            label=sample+'-'+arm;entry=evaluation['runs'].setdefault(label,{})
            if not entry.get('run_id'):
                result=api.call('/runs',{'workspace_id':wid,'arm':arm,'split':'holdout','repeats':3},key='benchmark-'+wid+'-'+arm)
                entry.update(run_id=result['run_id'],next_step=0);save(PRIVATE/'benchmark.json',evaluation)
            rid=entry['run_id']
            while True:
                value=api.call('/runs/'+rid)
                if value['metrics']['complete'] and not entry.get('pending_step'):break
                benchmark_step(api,rid,entry,evaluation,label,value)
            value=api.call('/exports/'+rid);out=ROOT/'deliverables/evidence';out.mkdir(parents=True,exist_ok=True)
            save(out/(label+'.json'),value);entry['complete']=True;save(PRIVATE/'benchmark.json',evaluation)
    print('正式比較が完了。失敗も分母に含めた結果を保存しました。数値が目標未達でも改変しません。')

def step08():
    run([str(ROOT/'.venv/bin/python'),'steps/export_evidence.py'],action='08-export')
    print('deliverables/ に実測レポート、170秒のデモ構成、提出用ソースZIPを出力しました。')
    print('動画の実録・公式テンプレートへの転記・提出は START_HERE_ja.md の完了条件で確認してください。')

def support():
    s=state();c=load(CONFIG);report={'package_version':s['package_version'],'package_hash':hashed(manifest()),'code_hash':manifest().get('code_hash'),
        'steps':s['steps'],'actions':{k:{field:v.get(field) for field in ('status','exit_code','diagnostic','started_at','finished_at')} for k,v in s['actions'].items()},
        'cloud_config':{k:c.get(k) for k in ('region','model','model_location')},'created_at':stamp()}
    # Intentionally exclude account, billing ID, URLs, tokens, cookies, sources and full logs.
    save(PRIVATE/'support.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2));print('\n共有用ファイル: .jt/support.json')
def status():
    s=state();print('Judgment Transfer / package '+s['package_version'])
    for number,title in STEPS.items():
        item=s['steps'].get(number,{});print(number+' '+item.get('status','NOT_STARTED').ljust(12)+' '+title+((' / '+item['error_code']) if item.get('error_code') else ''))
    pending=next((n for n in STEPS if s['steps'].get(n,{}).get('status')!='DONE'),None)
    print('次のコマンド: '+('bash jt '+pending if pending else 'なし。提出チェックリストを確認。'))

def main():
    parser=argparse.ArgumentParser(description='Judgment Transfer 固定実行パッケージ');parser.add_argument('step',nargs='?',default='status');parser.add_argument('--retry',action='store_true');args=parser.parse_args()
    if args.step=='status':status();return
    if args.step=='support':support();return
    if args.step=='admin-token':
        print('手元の画面の管理者欄だけに貼り付けてください。チャットやGitへ貼らないでください。')
        print(gc('secrets','versions','access','latest','--secret=jt-admin',sensitive=True));return
    if args.step=='local':
        os.environ['JT_MODE']='MOCK';os.environ['JT_DATA']=str(PRIVATE/'local-data')
        run([str(ROOT/'.venv/bin/python'),'app/main.py']);return
    if args.step=='close':
        c=config();gc('run','services','update',c['service'],'--region='+c['region'],'--invoker-iam-check');print('公開アクセスを停止しました。リソースは削除していません。');return
    if args.step not in STEPS:raise Stop('UNKNOWN_STEP','00〜08、status、support、local、admin-token、close のいずれかを指定してください。')
    number=args.step;m=integrity();s=state()
    if s['steps'].get(number,{}).get('status')=='DONE':print(number+' は完了済み。再実行しません。');return
    earlier=[n for n in STEPS if n<number and s['steps'].get(n,{}).get('status')!='DONE']
    if earlier:raise Stop('PREVIOUS_STEP','先に bash jt '+earlier[0]+' を実行してください。')
    old=s['steps'].get(number,{})
    if old.get('status') in ('FAILED','RUNNING') and not args.retry:raise Stop('EXPLICIT_RETRY','前回の停止状態を保持しています。内容を確認後、bash jt '+number+' --retry で同じ工程を再開してください。')
    s['steps'][number]={'status':'RUNNING','started_at':stamp(),'package_hash':hashed(m),'attempt':old.get('attempt',0)+1};save(STATE,s)
    print(number+' '+STEPS[number],flush=True)
    try:globals()['step'+number]()
    except (Stop,KeyboardInterrupt) as error:
        s=state();s['steps'][number].update(status='FAILED',error_code=getattr(error,'code','USER_INTERRUPTED'),stopped_at=stamp());save(STATE,s);raise
    s=state();s['steps'][number].update(status='DONE',finished_at=stamp());save(STATE,s);print(number+' DONE');status()

if __name__=='__main__':
    try:
        with (PRIVATE/'runbook.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise Stop('RUNBOOK_BUSY','別の工程が実行中です。並行して実行しないでください。')
            main()
    except Stop as e:print('\nSTOP '+e.code+'\n'+str(e));sys.exit(1)
    except KeyboardInterrupt:print('\nSTOP USER_INTERRUPTED / 状態を保存しました。bash jt status で確認してください。');sys.exit(130)
    except Exception as e:print('\nSTOP RUNBOOK_ERROR / '+type(e).__name__+'。bash jt support の結果を共有してください。');sys.exit(1)

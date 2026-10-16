"""Bounded actual-Service test. Only generation and external API boundaries are doubles."""
import base64,copy,io,json,sys,tempfile,types,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'app')]
import config
config.CODE_HASH='offline-receipt139'
from core.models import digest,JTError,validate_domain,validate_case
from service import Service,now
from storage.repository import LocalRepository,Blobs
from adapters.evidence import inspect_file,validate_ref
import history,expense_demo
from approved_execution import decision
from steps import receipt_demo139 as controller
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
def rejects(name,fn,code):
    try:fn()
    except JTError as e:ok(name,e.code==code)
    else:raise AssertionError(name)
fixture=ROOT/'app/fixtures/expense_review_usd139'
load=lambda p:json.loads(p.read_text()) if p.exists() else {}
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
d0=load(fixture/'domain_v0.json');reference=load(fixture/'rules_v1_reference.json');cases=load(fixture/'cases.json');labels=load(fixture/'expected_private_to_scorer.json')
pack=load(ROOT/'app/web/samples/expense_files.json');z=zipfile.ZipFile(io.BytesIO(base64.b64decode(pack['base64'])))
ok('sample contains six PDFs and no evaluation files',len([n for n in z.namelist() if n.endswith('.pdf')])==6 and not any('evaluation' in n or 'reference.json' in n for n in z.namelist()))
with tempfile.TemporaryDirectory() as td:
    root=Path(td);repo=LocalRepository(root/'repo');blobs=Blobs(root)
    for c in cases:validate_case(c,d0)
    for doc in load(fixture/'case_documents.json')['documents']:
        raw=z.read(doc['relative_path']);metadata,text=inspect_file(doc['filename'],raw,'application/pdf')
        sid=doc['source_id'];source={**metadata,'source_id':sid,'blob_id':sid};blobs.put(sid,raw,'application/pdf')
        ok('PDF matches saved hash and two pages '+doc['claim_id'],metadata['version_hash']==doc['version_hash'] and metadata['pages']==2)
        for fid,obs in doc['field_evidence'].items():
            for ref in obs['source_refs']:validate_ref(ref,source,blobs)
            ok('PDF field matches case '+doc['claim_id']+' '+fid,obs['value']==next(c for c in cases if c['case_id']==doc['case_id'])['facts'][fid])
    usage={'session':{'calls':565,'decisions':300},'budget':{'calls':575,'decisions':38,'spent_usd':19.9433211}}
    class GenerationDouble:
        mode='LIVE'
        def __init__(self):self.calls=0;self.payloads=[]
        def trace(self,purpose,payload,result,source_hashes):
            self.calls+=1;usage['session']['calls']+=1;usage['budget']['calls']+=1;usage['budget']['spent_usd']+=.01
            trace={'trace_id':'test_generation_'+str(self.calls),'purpose':purpose,'mode':'LIVE','payload':copy.deepcopy(payload),
                   'source_hashes':source_hashes,'settings':config.SETTINGS,'attempts':[{'status':'OK','cost_usd':.01}],'result':copy.deepcopy(result)}
            self.payloads.append(payload);repo.put('traces',trace['trace_id'],trace);return copy.deepcopy(result),trace
        def propose_question(self,domain,failures,sources,*_):
            ok('question sees only blocked Sam, no holdout',len(failures)==1 and failures[0]['case_id']==cases[1]['case_id'])
            q={'question_id':'pending','affected_dev_case_ids':[cases[1]['case_id']],'missing_field_ids':[],
               'text':'When can a receipt addressed to the employee rather than the company be accepted?',
               'why_needed':'The initial procedure omits the acceptance condition.',
               'source_refs':[{'source_id':'expense_sop','version_hash':domain['source_hashes']['expense_sop'],'locator':'line:10','quote':(fixture/'source_sop.txt').read_text().splitlines()[9]}]}
            return self.trace('propose_question',{'domain':domain,'development_cases':failures},q,domain['source_hashes'])
        def draft_rules(self,domain,question,text,source,*_):
            rules=copy.deepcopy(reference['rules'][len(d0['rules']):])
            for r in rules:
                r['source_refs']=[{'source_id':source['source_id'],'version_hash':source['version_hash'],'locator':'human:1','quote':text.splitlines()[0]}]
            return self.trace('draft_rules',{'domain':domain,'question':question,'human_text':text},{'rules':rules},{source['source_id']:source['version_hash']})
        def decide(self,*_):raise AssertionError('Case execution must not call a model')
    adapter=GenerationDouble();service=Service(repo,blobs,adapter)
    oldviews={rid:{'run':{'run_id':rid},'tasks':[{'status':'COMPLETED'}],'receipts':[],'traces':[]} for rid in controller.OLD_RUNS}
    oldpublic={'demo_version':'1.0.38','cases':[{'title':'Company-addressed receipt'}]};repo.put('public_demo','expense_usd134',oldpublic)
    class API:
        def __init__(self):self.posts=[];self.cache={}
        def call(self,path,data=None,key=None,files=None):
            ctx={'owner':'test-owner','admin':True,'operation':key or 'read'}
            if key in self.cache:return copy.deepcopy(self.cache[key])
            if data is not None:self.posts.append(path)
            if path=='/health':v={'package_version':'1.0.39','code_hash':config.CODE_HASH,'mode':'LIVE','max_cost_usd':100}
            elif path=='/recovery115':v=copy.deepcopy(usage)
            elif path=='/workspaces':v=service.create_workspace(data,ctx)
            elif path=='/sources':v=service.add_source(data['workspace_id'],files[0],files[2],files[1],ctx,data['source_id'])
            elif path=='/domains/draft':v=service.draft_domain(data,ctx)
            elif path=='/domains/approve':v=service.approve_domain(data,ctx)
            elif path=='/cases/import':v=service.import_cases(data,ctx)
            elif path=='/runs':v=service.create_run(data,ctx)
            elif path.endswith('/step'):v=service.step(path.split('/')[2],ctx)
            elif path.startswith('/exports/'):
                rid=path.split('/')[-1];v=copy.deepcopy(oldviews[rid]) if rid in oldviews else service.run_view(rid,ctx,True)
            elif path=='/questions':v=service.question(data,ctx)
            elif path=='/teachings':v=service.teach(data,ctx)
            elif path.startswith('/teachings/') and path.endswith('/approve'):v=service.approve_teaching(path.split('/')[2],data,ctx)
            elif path=='/history/fix':v=history.fix_result(service,data,ctx)
            elif path=='/workspaces/freeze':v=service.freeze(data,ctx)
            elif path=='/demo/expense/publish':v=expense_demo.publish(service,data,ctx)
            elif path=='/demo/expense':v=repo.get('public_demo','expense_receipt139') or repo.get('public_demo','expense_usd134')
            else:raise AssertionError(path)
            if key:self.cache[key]=copy.deepcopy(v)
            return v
    api=API()
    import shutil
    shutil.copytree(fixture,root/'app/fixtures/expense_review_usd139')
    save(root/'package-manifest.json',{'code_hash':config.CODE_HASH})
    save(root/'.jt/upgrades/1.0.34/usd-demo.json',{'steps':{'authorize':{'authorized':True,'max_cost_usd':100,'base_calls':509,'additional_calls':64}}})
    r=types.SimpleNamespace(load=load,save=save,stamp=now,Stop=JTError)
    result=controller.run(root,api,r,'Shinji Okada')
    ok('full controller passes actual source/schema/approval/history/execution/publication',result['status']=='PASSED')
    ok('two generation-double calls and ten zero-model case executions',adapter.calls==2 and result['report']['case_executions']==10 and result['report']['execution_model_calls']==0)
    ok('old public record preserved under its original key',repo.get('public_demo','expense_usd134')==oldpublic)
    ok('no allowance or budget mutation requested','/validation123/authorize' not in api.posts)
    public=api.call('/demo/expense');ok('new published story has own scenario marker and personal receipt',public['scenario_id']==controller.SCENARIO and public['cases'][1]['facts']['receipt_addressed_to']=='Sam Rivera')
    ok('Sam sole-payer amount is 348 dollars',cases[1]['facts']['claimed_amount_usd']==cases[1]['facts']['employee_payment_amount_usd']==cases[1]['facts']['receipt_total_usd']==348 and cases[1]['facts']['company_payment_amount_usd']==0)
    fixed=history.records(service,result['workspace_id'],{'owner':'test-owner','admin':True,'operation':'read'})
    ok('all seven finalized records carry reviewer and time',len(fixed)==7 and all(v['reviewer_name']=='Shinji Okada' and v['recorded_at'] for v in fixed))
    before=len(api.posts);controller.run(root,api,r,'Shinji Okada');ok('repeat run creates no new request or approval',len(api.posts)==before)
    body={k+'_run_id':result[k+'_run_id'] for k in ('baseline','after','holdout')}|{'scenario_id':controller.SCENARIO,'publish_fictional_usd_demo':True,'reviewer_name':'Shinji Okada'}
    ctx={'owner':'test-owner','admin':True,'operation':'tamper'}
    rejects('new cases cannot publish under old scenario',lambda:expense_demo.publish(service,{k:v for k,v in body.items() if k!='scenario_id'},ctx),'DEMO_RESULT_MISMATCH')
    rejects('unknown scenario refused',lambda:expense_demo.publish(service,{**body,'scenario_id':'other'},ctx),'INVALID_INPUT')
    rid=result['after_run_id'];run=repo.get('runs',rid);run['domain']['rules'][0]['source_refs'][0]['quote']='invented';repo.put('runs',rid,run)
    rejects('invalid evidence cannot replace public record',lambda:expense_demo.publish(service,body,ctx),'INVALID_INPUT')
    ok('failed publication keeps old and new public records',api.call('/demo/expense')==public and repo.get('public_demo','expense_usd134')==oldpublic)
report={'status':'PASSED','passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
'scope':'Actual schema, source/PDF evidence validators, local repository/blobs, Service, history, engine/executor, comparison, release controller and publication. Generation and owner-operated HTTP API are explicit test doubles. Live Gemini/Cloud Run comparison remains pending.'}
(ROOT/'verification/receipt139_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

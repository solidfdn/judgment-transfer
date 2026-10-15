"""Bounded offline checks: exact USD files, grant persistence and publication guards."""
import copy,json,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
import config
from core.models import digest,validate_domain,permitted,JTError
from adapters.evidence import inspect_file,validate_ref
from storage.repository import LocalRepository,Blobs
from service import Service
from validation123 import authorize
from expense_demo import publish
F=ROOT/'app/fixtures/expense_review_usd';checks=[]
def ok(name,condition=True):
    assert condition,name;checks.append(name)
def reject(name,call,code):
    try:call()
    except JTError as e:ok(name,e.code==code)
    else:raise AssertionError(name)
domain=json.loads((F/'domain_v0.json').read_text());full=json.loads((F/'rules_v1_reference.json').read_text())
cases=json.loads((F/'cases.json').read_text());labels=json.loads((F/'expected_private_to_scorer.json').read_text())
validate_domain(domain);validate_domain(full)
ok('all six cases and fields explicitly use USD',len(cases)==6 and '_jpy' not in json.dumps([domain,cases,full]) and 'JPY' not in json.dumps([domain,cases,full]))
ok('new dollar amounts retain intended payment relationships',cases[1]['facts']['claimed_amount_usd']==348 and cases[5]['facts']['claimed_amount_usd']-cases[5]['facts']['employee_payment_amount_usd']==160)
ok('USD reference preserves all four before/after decisions and both held-out targets',
   [permitted(domain,{**c['facts'],**c['initial_state']})[0] for c in cases[:4]]==['ready_for_approval','hold_case','hold_case','hold_case'] and
   [permitted(full,{**c['facts'],**c['initial_state']})[0] for c in cases]==[x['expected_action_id'] for x in labels])
with tempfile.TemporaryDirectory() as td:
    repo=LocalRepository(td);blobs=Blobs(td);service=Service(repo,blobs,types.SimpleNamespace(mode='LIVE'))
    docs=json.loads((F/'case_documents.json').read_text())['documents'];refs=0
    for doc in docs:
        raw=(ROOT/'output/Expense_Demo_USD_Data'/doc['relative_path']).read_bytes()
        metadata,_=inspect_file(doc['filename'],raw,'application/pdf');blobs.put(doc['source_id'],raw,'application/pdf')
        metadata.update(blob_id=doc['source_id'],human=False)
        ok('USD PDF hash and page evidence '+doc['claim_id'],metadata['version_hash']==doc['version_hash'])
        for observation in doc['field_evidence'].values():
            for ref in observation['source_refs']:validate_ref(ref,metadata,blobs);refs+=1
    ok('every generated USD field citation matches its exact PDF',refs==78)
    config.MAX_COST=100;ctx={'owner':'offline-owner','admin':True,'operation':'offline-usd134'}
    sk=('budget',digest(ctx['owner'])[:40]);repo.put(*sk,{'calls':538,'decisions':510});repo.put('budget','global',{'spent_usd':18.4,'calls':550})
    old=authorize(service,{'max_cost_usd':100,'reviewer_name':'Offline reviewer'},ctx)
    budgets=copy.deepcopy([repo.get(*sk),repo.get('budget','global')])
    updated=authorize(service,{'max_cost_usd':100,'demo_revision':'USD_134','reviewer_name':'Offline reviewer'},ctx)
    ok('new one-time grant adds 24 attempts and 20 decisions with original baseline intact',updated['additional_calls']==64 and updated['additional_decisions']==44 and updated['base_calls']==old['base_calls'])
    ok('repeating the same USD grant cannot enlarge it',authorize(service,{'max_cost_usd':100,'demo_revision':'USD_134','reviewer_name':'Offline reviewer'},ctx)==updated)
    ok('grant preserves counters and historical spend',budgets==[repo.get(*sk),repo.get('budget','global')])
    reject('public users cannot extend the grant',lambda:authorize(service,{'max_cost_usd':100,'demo_revision':'USD_134','reviewer_name':'Offline reviewer'},{**ctx,'admin':False}),'ADMIN_REQUIRED')
    reject('publishing needs explicit owner authorization',lambda:publish(service,{'reviewer_name':'Offline reviewer'},ctx),'ADMIN_REQUIRED')
    # Explicit saved-view doubles exercise the publication gate; they are not model runs.
    views={};policy=(F/'source_sop.txt').read_text();text='\n'.join((F/'expert_teaching_reference.txt').read_text().splitlines()[2:])
    for kind,selected,targets,version,split in [('baseline',cases[:4],['ready_for_approval','hold_case','hold_case','hold_case'],0,'dev'),('after',cases[:4],[x['expected_action_id'] for x in labels[:4]],1,'dev'),('holdout',cases[4:],[x['expected_action_id'] for x in labels[4:]],1,'holdout')]:
        d=domain if version==0 else full
        run={'run_id':kind,'workspace_id':'offline','mode':'LIVE','split':split,'dataset_hash':digest(selected),'repeats':1,
          'case_ids':[c['case_id'] for c in selected],'model_settings':{'test_double':True},'code_hash':'offline-explicit-double',
          'domain':d,'domain_hash':digest(d),'source_hashes':d['source_hashes'],'arm':'C_JT_RULES','created_at':'2026-10-15T02:00:00+00:00'}
        tasks=[];receipts=[]
        for c,target in zip(selected,targets):
            effect={e['field_id']:e['value'] for a in d['actions'] if a['action_id']==target for e in a['effects']}
            tasks.append({'task_id':c['case_id'],'case_id':c['case_id'],'status':'COMPLETED','decision':{'action_id':target,'explanation':'OFFLINE DOUBLE'},'raw_decision':{'action_id':target},'state':effect,'trace_ids':['offline-'+c['case_id']]})
            receipts.append({'task_id':c['case_id'],'case_hash':digest(c),'before_state':c['initial_state']})
        traces=[{'trace_id':t['trace_ids'][0],'mode':'LIVE','purpose':'decide','settings':run['model_settings'],'attempts':[{'status':'OK'}],'result':t['raw_decision']} for t in tasks]
        views[kind]={'run':run,'tasks':tasks,'receipts':receipts,'traces':traces,'metrics':{'complete':True,'stale':False}}
    service.run_view=lambda rid,ctx,export=False:copy.deepcopy(views[rid])
    service.workspace=lambda wid,ctx:{'frozen':True,'version':1,'approved_count':1,'teaching_ids':['t'],'run_ids':list(views),'freeze':{'frozen_at':'2026-10-15T01:00:00+00:00'}}
    service.owned=lambda kind,rid,ctx:({'teaching':{'human_text':text,'approval_state':'APPROVED','question_id':'q'}} if kind=='teachings' else {'question':{'text':'Offline question','question_id':'q'}})
    body={'reviewer_name':'Offline reviewer','publish_fictional_usd_demo':True,**{k+'_run_id':k for k in views}}
    data=publish(service,body,ctx)
    ok('verified fixture-shaped records publish USD facts and original run identities',data['currency']=='USD' and data['cases'][1]['facts']['claimed_amount']==348 and data['after_run_id']=='after')
    ok('repeat publication returns the same immutable public snapshot',publish(service,body,ctx)==data)
    views['after']['traces'][0]['mode']='MOCK'
    reject('mock or missing trace cannot publish as live USD evidence',lambda:publish(service,body,ctx),'DEMO_RESULT_MISMATCH')
    views['after']['traces'][0]['mode']='LIVE'
    views['after']['tasks'][1]['raw_decision']['action_id']='hold_case'
    reject('raw model answer cannot be relabelled as a passing USD result',lambda:publish(service,body,ctx),'DEMO_RESULT_MISMATCH')
    views['after']['tasks'][1]['raw_decision']['action_id']='ready_for_approval';views['after']['receipts'][1]['case_hash']='changed'
    reject('changed facts or currency without a matching receipt cannot publish',lambda:publish(service,body,ctx),'DEMO_RESULT_MISMATCH')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Local fixture PDF/hash/citation checks, existing rule engine, one-time grant and publication guards with explicitly fabricated saved views. No live USD result is claimed.'}
(ROOT/'verification/usd134_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

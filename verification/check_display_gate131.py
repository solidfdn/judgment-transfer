"""Verify shipped text/case/trace association before deployment, using explicit exports."""
import copy,importlib.util,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from core.models import digest
spec=importlib.util.spec_from_file_location('gate',ROOT/'steps/verify_display131.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
evidence=(ROOT/'app/web/demo/evidence.js').read_text();demo=json.loads(evidence.split('=',1)[1].strip().removesuffix(';'))
class Stop(Exception):
 def __init__(self,code,msg):self.code=code;super().__init__(msg)
class R:
 Stop=Stop
 @staticmethod
 def load(p):return json.loads(p.read_text())
 @staticmethod
 def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
class API:
 def __init__(self,views):self.views=views;self.calls=[];self.bad_pair=False;self.changed_usage=False
 def call(self,path):
  self.calls.append(path)
  if path=='/recovery115':return {'budget':{'calls':538+int(self.changed_usage and self.calls.count(path)>1),'spent_usd':17.925672}}
  if path.startswith('/exports/'):return copy.deepcopy(self.views[path.split('/')[-1]])
  if path.startswith('/comparisons/'):return {'comparable':not self.bad_pair,'code_review':'Audited teaching patch','checks':{'evidence':True}}
  raise AssertionError(path)
def setup(folder):
 root=Path(folder);views={};readings=[]
 for c in demo['cases']:readings.append({'case_id':c['id'],'case':{'case_id':c['id'],'facts':c['facts'],'initial_state':{'review_status':None}}})
 for kind,key in [('baseline','baseline_run_id'),('after','after_run_id'),('holdout','holdout_run_id')]:
  selected=demo['cases'][4:] if kind=='holdout' else demo['cases'][:4];tasks=[];receipts=[]
  for c in selected:
   case={'case_id':c['id'],'facts':c['facts'],'initial_state':{'review_status':'NEW'}};action=c['before'] if kind=='baseline' else c['after']
   tasks.append({'case_id':c['id'],'status':'COMPLETED','decision':{'action_id':action,'explanation':c['explanation']},'raw_decision':{'action_id':action},'trace_ids':[c['trace_id']]})
   receipts.append({'case_id':c['id'],'case_hash':digest(case)})
  views[demo[key]]={'run':{'run_id':demo[key]},'tasks':tasks,'receipts':receipts,'traces':[],'source_metadata':[],'case_evidence':[]}
  R.save(root/'deliverables/release130/comparison'/(kind+'.json'),views[demo[key]])
 R.save(root/'.jt/upgrades/1.0.28/pdf-intake-resume.json',{'readings':readings})
 R.save(root/'.jt/upgrades/1.0.30/expense-comparison.json',{'status':'PASSED','model_calls':6,'judgment_calls':6,'after_run_id':demo['after_run_id'],'holdout_run_id':demo['holdout_run_id'],'report':{'baseline_run_id':demo['baseline_run_id']}})
 return root,API(views)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
import contextlib,io
with contextlib.redirect_stdout(io.StringIO()):
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);result=g.verify(root,api,R,False,evidence);ok('predeployment verifies all six cases without new endpoint',result['verified_cases']==6 and result['new_model_calls']==0 and not result['comparison_endpoint_verified'])
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);result=g.verify(root,api,R,True,evidence);ok('postdeployment also requires the read-only comparison endpoint',result['comparison_endpoint_verified'])
 for name,mutate in [('changed payment amount',lambda e:e['cases'][1]['facts'].update(receipt_employee_paid_amount=1)),('changed action',lambda e:e['cases'][2].update(after='ready_for_business_approval')),('wrong trace',lambda e:e['cases'][0].update(trace_id='other')),('altered explanation',lambda e:e['cases'][0].update(explanation='Invented explanation')),('missing case',lambda e:e['cases'].pop())]:
  with tempfile.TemporaryDirectory() as f:
   root,api=setup(f);e=copy.deepcopy(demo);mutate(e)
   try:g.verify(root,api,R,False,'window.JT_DEMO_EVIDENCE = '+json.dumps(e)+';')
   except Stop:ok(name+' blocks deployment')
   else:raise AssertionError(name)
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);api.bad_pair=True
  try:g.verify(root,api,R,True,evidence)
  except Stop as e:ok('unverified native comparison stops display gate',e.code=='COMPARISON_DISPLAY_FAILED')
  else:raise AssertionError('pair')
 with tempfile.TemporaryDirectory() as f:
  root,api=setup(f);api.changed_usage=True
  try:g.verify(root,api,R,False,evidence)
  except Stop as e:ok('unexpected model usage detected',e.code=='USAGE_CHANGED')
  else:raise AssertionError('usage')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual display pre/post controller using explicit local saved-export doubles. No cloud success claimed.'}
(ROOT/'verification/display131_gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

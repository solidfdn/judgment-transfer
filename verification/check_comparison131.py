"""Bounded comparison guard checks using immutable explicit run-view doubles."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from comparison import compare,AUDITED_TEACHING_PATCH
from core.models import JTError
hashes=sorted(AUDITED_TEACHING_PATCH)
def views():
 base={'run':{'workspace_id':'owned','mode':'LIVE','split':'dev','dataset_hash':'same-cases','repeats':1,'case_ids':['case1','case2'],
              'model_settings':{'model':'recorded','request_tier':'priority'},'code_hash':'same-build','domain':{'version':0,'source_hashes':{'policy':'sha'}},
              'source_hashes':{'policy':'sha'},'arm':'C_JT_RULES'},'metrics':{'complete':True,'stale':False}}
 after=copy.deepcopy(base);after['run']['domain']['version']=1;after['run']['source_hashes']['human']='sha2';return {'before':base,'after':after}
class Saved:
 def __init__(self):self.views=views();self.reads=[]
 def run_view(self,rid,ctx):
  if ctx['owner']!='owner':raise JTError('NOT_FOUND','Not owned',404)
  self.reads.append(rid);return copy.deepcopy(self.views[rid])
ctx={'owner':'owner'};checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
s=Saved();ok('same-build C version zero can compare to later guidance',compare(s,'before','after',ctx)['comparable'])
s.views['before']['run']['code_hash']=hashes[0];s.views['after']['run']['code_hash']=hashes[1]
r=compare(s,'before','after',ctx);ok('only audited teaching-only package pair is accepted with disclosure',r['comparable'] and bool(r['code_review']) and r['baseline_code_hash']!=r['after_code_hash'])
original=copy.deepcopy(s.views);compare(s,'before','after',ctx);ok('comparison never edits original run views',s.views==original)
for name,key,value in [('different workspace','workspace_id','other'),('different cases','dataset_hash','other'),('different split','split','holdout'),('different repeats','repeats',2),('different settings','model_settings',{'model':'other'}),('different package','code_hash','unaudited')]:
 s=Saved();s.views['after']['run'][key]=value;ok(name+' rejected',not compare(s,'before','after',ctx)['comparable'])
for name,change in [('reordered case ids',lambda v:v['after']['run'].update(case_ids=['case2','case1'])),('stale evidence',lambda v:v['before']['metrics'].update(stale=True)),('unfinished run',lambda v:v['after']['metrics'].update(complete=False)),('changed source hash',lambda v:v['after']['run']['source_hashes'].update(policy='changed')),('not a later rule version',lambda v:v['after']['run']['domain'].update(version=0)),('text arm not guidance',lambda v:v['after']['run'].update(arm='B_TEXT_ADDED'))]:
 s=Saved();change(s.views);ok(name+' rejected',not compare(s,'before','after',ctx)['comparable'])
s=Saved()
try:compare(s,'before','after',{'owner':'other'})
except JTError:ok('cross-owner view refused')
else:raise AssertionError('owner')
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual read-only comparison implementation with explicit owned-view doubles.'}
(ROOT/'verification/comparison131_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

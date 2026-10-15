"""Bounded read-only citation diagnostic checks; no cloud or model clients."""
import ast,copy,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
spec=importlib.util.spec_from_file_location('inspect129',ROOT/'releases/jt_inspect_teaching_129.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from adapters.evidence import inspect_file
raw=json.loads((ROOT/'app/fixtures/expense_review/domain_v0.json').read_text());domain=copy.deepcopy(raw);domain['rules']=[];domain['source_hashes']={}
text='Payment must be PAID.\nMissing payment evidence requires HOLD.'
meta,_=inspect_file('answer.txt',text.encode());source={**meta,'source_id':'human_test','human':True,'blob_id':'human_blob'}
pmeta,_=inspect_file('policy.txt',b'Policy.');policy={**pmeta,'source_id':'policy_test','blob_id':'policy_blob'}
rule=copy.deepcopy(raw['rules'][0]);rule['approved_by']=None
checks=[]
def inspect(quote,locator='human:1',hash_value=None):
 r=copy.deepcopy(rule);r['source_refs']=[{'source_id':'human_test','version_hash':hash_value or source['version_hash'],'locator':locator,'quote':quote}]
 trace={'result':{'rules':[r]}};before=copy.deepcopy(trace)
 report=m.analyze(domain,source,policy,trace,text,b'Policy.');assert trace==before
 return report
r=inspect(text);assert r['invalid_reference_count']==0 and r['revalidation']['status']=='PASSED_IN_MEMORY';checks.append('literal source passes original validators')
r=inspect(text.replace('\n',' '));assert r['invalid_reference_count']==1 and r['invalid_references'][0]['whitespace_only_recoverable'];checks.append('whitespace difference diagnosed without changing answer')
for quote,locator,hash_value in [('Payment may be PAID.','human:1',None),('Payment must be PAID.','line:1',None),('Payment must be PAID.','human:1','0'*64)]:
 r=inspect(quote,locator,hash_value);assert r['invalid_reference_count']==1 and not r['invalid_references'][0]['whitespace_only_recoverable']
checks.append('changed wording invalid location and stale hash stay invalid')
code=(ROOT/'releases/jt_inspect_teaching_129.py').read_text();tree=ast.parse(code)
assert 'method=\'GET\'' in code and 'print-access-token' in code and 'gcloud' in code
assert not any(isinstance(n,ast.Attribute) and n.attr in ('invoke','generate_content','put','atomic','teach','approve_teaching') for n in ast.walk(tree))
checks.append('no model or cloud mutation entrypoint')
print(json.dumps({'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0}))

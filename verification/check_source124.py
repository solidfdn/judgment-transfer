"""Bounded regression for the provider grammar and unchanged acceptance checks.

Real adapter/service code and JSON Schema validation; provider/HTTP are doubles.
This does not establish that Google accepts the schema or returns a useful review.
"""
import ast
import copy
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'app'), str(ROOT)]
from jsonschema import Draft202012Validator
from requirements_review import ASPECTS, REVIEW_SCHEMA, review_requirements
from case_intake import EXTRACT
from core.models import JTError
from storage.repository import LocalRepository, Blobs
from service import Service

checks = []
def ok(name, value=True):
    assert value, name
    checks.append(name)

# Compile the real adapter, substituting only the unavailable HTTP transport.
tree = ast.parse((ROOT/'app/adapters/model.py').read_text())
tree.body = [n for n in tree.body if not (isinstance(n, ast.Import) and any(a.name == 'httpx' for a in n.names))]
transport = types.SimpleNamespace(**{name: type(name, (Exception,), {}) for name in
    ('TimeoutException', 'ReadTimeout', 'NetworkError', 'RemoteProtocolError')})
scope = {'httpx': transport, '__name__': 'adapter_source124_test'}
exec(compile(tree, str(ROOT/'app/adapters/model.py'), 'exec'), scope)
Adapter = scope['LiveAdapter']
compact = scope['extraction_response_schema']
original = copy.deepcopy(REVIEW_SCHEMA)
wire = compact(REVIEW_SCHEMA)
ok('provider construction does not mutate the validation contract', REVIEW_SCHEMA == original)
ok('wire retains object keys, required fields and additional-property rejection',
   wire['required'] == REVIEW_SCHEMA['required'] and wire['additionalProperties'] is False)
ok('wire retains the six aspect identifiers', wire['properties']['checks']['items']['properties']['aspect']['enum'] == list(ASPECTS))
ok('schema property names that match constraint names are retained',
   'pattern' in compact({'type':'object', 'properties':{'pattern':{'type':'string','maxLength':3}}})['properties'])
def keywords(schema):
    if isinstance(schema, dict):
        return set(schema) | set().union(*(keywords(v) for v in schema.values()))
    if isinstance(schema, list): return set().union(*(keywords(v) for v in schema))
    return set()
for label, contract in [('review', REVIEW_SCHEMA), ('case', EXTRACT), ('legacy extraction', scope['EXTRACT_SCHEMA'])]:
    ok(label+' provider grammar has no array, string-length or pattern bounds',
       not keywords(compact(contract)) & {'minItems','maxItems','minLength','maxLength','pattern'})

class Item(types.SimpleNamespace):
    @classmethod
    def from_text(cls, **kw): return cls(**kw)
class Models:
    def __init__(self, result): self.result=result; self.generations=[]
    def count_tokens(self, **kw): return Item(total_tokens=100)
    def generate_content(self, **kw):
        self.generations.append(kw)
        if isinstance(self.result, Exception): raise self.result
        return Item(text=json.dumps(self.result), usage_metadata=Item(prompt_token_count=100,
            candidates_token_count=200, thoughts_token_count=0, traffic_type='ON_DEMAND'), model_version='SDK_DOUBLE')

with tempfile.TemporaryDirectory() as folder:
    repo=LocalRepository(folder); blobs=Blobs(folder)
    adapter=Adapter.__new__(Adapter)
    adapter.types=Item(Part=Item,Content=Item,HttpOptions=Item,HttpRetryOptions=Item,
        CountTokensConfig=Item,GenerateContentConfig=Item,ThinkingConfig=Item)
    adapter.repo=repo; adapter.blobs=blobs; adapter.budget=scope['Budget'](repo)
    adapter.client=Item(models=Models(None))
    service=Service(repo,blobs,adapter)
    ctx={'owner':'offline-124','admin':True,'operation':'source124-test-workspace'}
    ws=service.create_workspace({'goal':'Read fictional expense policy'},ctx); wid=ws['workspace_id']
    data=(ROOT/'app/web/samples/expense_policy.txt').read_bytes()
    source=service.add_source(wid,'policy.txt',data,'text/plain',ctx,'expense_policy')
    ref={'source_id':source['source_id'],'version_hash':source['version_hash'],'locator':'line:1','quote':data.decode().splitlines()[0]}
    valid={'observations':[{'field_id':'purpose','value':ref['quote'],'status':'OBSERVED','source_refs':[ref]}],
        'summary':'Review the job and clarify missing conditions.',
        'checks':[{'aspect':a,'status':'documented','finding':'The source contains a policy.', 'source_refs':[ref]} for a in ASPECTS],
        'questions':[{'aspect':'decision_conditions','question':'Which evidence permits a company-addressed receipt?',
                      'why_needed':'The source leaves this condition open.','source_refs':[ref]}]}
    adapter.client.models.result=valid
    review=review_requirements(service,{'workspace_id':wid},ctx)
    trace=repo.get('traces',review['trace_id']); sent=adapter.client.models.generations[-1]['config']
    ok('real invoke sends compact schema and no duplicated contract in system prompt',
       sent.response_json_schema == wire and sent.system_instruction == scope['SYSTEM'])
    ok('actual trace records both schemas and nonstream extraction transport',
       trace['settings']['response_schema_hash'] != trace['settings']['validation_schema_hash'] and
       trace['settings']['transport']=='generateContent')
    ok('real service saves the six-perspective review with exact evidence',
       service.workspace(wid,ctx)['requirements_review']['trace_id']==trace['trace_id'])
    for label, mutate in [
        ('too few perspectives', lambda v:v['checks'].pop()),
        ('long finding', lambda v:v['checks'][0].update(finding='x'*501)),
        ('too many questions', lambda v:v.update(questions=v['questions']*6)),
        ('invalid field identifier', lambda v:v['observations'][0].update(field_id='bad field'))]:
        bad=copy.deepcopy(valid); mutate(bad)
        ok(label+' remains rejected by strict server contract', bool(list(Draft202012Validator(REVIEW_SCHEMA).iter_errors(bad))))
    adapter.client.models.result={**valid,'checks':valid['checks'][:5]}
    start=len(adapter.client.models.generations)
    try: review_requirements(service,{'workspace_id':wid},ctx)
    except JTError as e:
        ok('wrong count is rejected after generation, within the existing two-attempt cap',
           e.code=='MODEL_FAILED' and len(adapter.client.models.generations)-start==2)
        ok('contract failure trace includes path and keyword, no returned content',
           e.trace['attempts'][0]['validation_errors']==[{'path':['checks'],'constraint':'minItems'}])
    else: raise AssertionError('invalid review accepted')
    ok('failed review cannot replace the last valid review',service.workspace(wid,ctx)['requirements_review']['trace_id']==trace['trace_id'])
    for label, mutate in [('duplicate aspect',lambda v:v['checks'][1].update(aspect=ASPECTS[0])),
                          ('invented quotation',lambda v:v['checks'][0]['source_refs'][0].update(quote='a quote absent from the policy'))]:
        bad=copy.deepcopy(valid); mutate(bad); adapter.client.models.result=bad
        try: review_requirements(service,{'workspace_id':wid},ctx)
        except JTError: ok(label+' rejected by real service evidence/coverage validation')
        else: raise AssertionError(label+' accepted')
    class InvalidRequest(Exception):
        code=400; status='INVALID_ARGUMENT'; message='Request contains an invalid argument.'
    adapter.client.models.result=InvalidRequest(); start=len(adapter.client.models.generations)
    try: review_requirements(service,{'workspace_id':wid},ctx)
    except JTError as e:
        ok('400 is recorded once and not automatically retried',len(adapter.client.models.generations)-start==1 and e.trace['attempts'][0]['provider_code']=='400')
    else: raise AssertionError('400 accepted')

# Exercise the exact admin-only error-body function, including cached failures.
main=ast.parse((ROOT/'app/main.py').read_text())
factory=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='create_app')
body=next(n for n in factory.body if isinstance(n,ast.FunctionDef) and n.name=='error_body')
g=Item(ctx={'admin':True},request_id='req_test'); s={'g':g}
exec(compile(ast.Module(body=[body],type_ignores=[]),'main-error-body','exec'),s)
failure=JTError('MODEL_FAILED','Stopped',503)
failure.trace={'trace_id':'trace_test','payload':{'secret':'NEVER EXPOSE'},'attempts':[{'attempt':1,'stage':'generate_content','status':'FAILED','provider_code':'400','provider_error':{'message':'NEVER EXPOSE'}}]}
detail=s['error_body'](failure)
ok('administrator receives only this request bounded diagnostic', 'diagnostic' in detail['error'] and 'NEVER EXPOSE' not in json.dumps(detail))
g.ctx={'admin':False}
ok('public caller receives no provider diagnostic', 'diagnostic' not in s['error_body'](failure)['error'])

report={'passed':len(checks),'checks':checks,'provider':'explicit SDK/HTTP doubles',
        'real_google_acceptance':'not executed here; required deployed gate', 'new_model_calls':0}
(ROOT/'verification/source_contract_124.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

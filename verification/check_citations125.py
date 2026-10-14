"""Replay the five reported bad citations; reject substantive or ambiguous edits."""
import ast
import copy
import importlib.util
import io
import json
import sys
import tempfile
import types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
from adapters.citations import resolve_reference, unique_span
from adapters.evidence import inspect_file, validate_ref
from core.models import JTError
from requirements_review import ASPECTS, review_requirements
from service import Service
from storage.repository import LocalRepository, Blobs
checks=[]
def ok(n,v=True):
    assert v,n
    checks.append(n)
def reject(n,fn):
    try:fn()
    except JTError:checks.append(n)
    else:raise AssertionError(n)
reported=json.loads((ROOT/'verification/failed_quotes124.json').read_text())
with tempfile.TemporaryDirectory() as folder:
    repo=LocalRepository(folder);blobs=Blobs(folder)
    class Saved:
        mode='RECORDED_TEST_DOUBLE'
        def invoke(self,*args):return copy.deepcopy(self.value),copy.deepcopy(self.trace)
    adapter=Saved();svc=Service(repo,blobs,adapter)
    ctx={'owner':'offline125','admin':True,'operation':'citation125-workspace'}
    w=svc.create_workspace({'goal':'Review fictional policy'},ctx);wid=w['workspace_id']
    data=(ROOT/'app/web/samples/expense_policy.txt').read_bytes()
    source=svc.add_source(wid,'policy.txt',data,'text/plain',ctx,'expense_policy')
    def ref(locator,quote):return {'source_id':source['source_id'],'version_hash':source['version_hash'],'locator':locator,'quote':quote}
    originals=[]
    for entry in reported['references']:
        original=ref(entry['locator'],entry['quote']);originals.append(original)
        reject(entry['path']+' reproduces original exact-quote failure',lambda:validate_ref(original,source,blobs))
        fixed,note=resolve_reference(original,source,blobs,True)
        validate_ref(fixed,source,blobs)
        ok(entry['path']+' becomes an exact source excerpt with original provenance',note['original_reference']==original and fixed['locator']==original['locator'] and fixed['version_hash']==original['version_hash'])
    exact=ref('line:1',data.decode().splitlines()[0])
    fixed,note=resolve_reference(exact,source,blobs,True)
    ok('already exact references remain unchanged',fixed==exact and note is None)
    reject('ellipsis expansion forbidden for raw observations',lambda:resolve_reference(originals[2],source,blobs,False))
    for name,bad in [('wrong range',{**originals[0],'locator':'line:3'}),
                     ('wrong source',{**originals[0],'source_id':'other_source'}),
                     ('wrong hash',{**originals[0],'version_hash':'0'*64}),
                     ('rewritten negation',{**originals[0],'quote':originals[0]['quote'].replace('Never approve','Always approve')}),
                     ('reordered fragments',{**originals[2],'quote':'Do not subtract a company payment from a total, reverse-calculate from the claim, or infer who paid. ... Mark the documentary precheck complete only when claimant and guest match'})]:
        reject(name+' is not repaired',lambda:resolve_reference(bad,source,blobs,True))
    ok('ambiguous alignments rejected',unique_span('same text same text',['same text']) is None)
    ok('adversarial repeated fragments stop within bounded search',unique_span('a '*1000,['a']*7+['missing']) is None)
    # Numeric and omitted-negation cases use their own source, not the fixture.
    numeric=svc.add_source(wid,'literal.txt',b'Limit 20\nDo not approve payments.\n','text/plain',ctx,'literal_source')
    quote={'source_id':'literal_source','version_hash':numeric['version_hash'],'locator':'line:1-2','quote':'Limit 200 Do not approve payments.'}
    reject('changed number is not repaired',lambda:resolve_reference(quote,numeric,blobs,True))
    restored,note=resolve_reference({**quote,'locator':'line:2','quote':'Do ... approve payments.'},numeric,blobs,True)
    ok('omitted negation is restored visibly in the literal source quote',restored['quote']=='Do not approve payments.')
    # The complete review envelope below is explicit test data. Only the five
    # problematic references are copied from the actual reported trace.
    value={'observations':[{'field_id':'policy_title','value':exact['quote'],'status':'OBSERVED','source_refs':[exact]}],
        'summary':'Offline service regression.', 'checks':[{'aspect':a,'status':'documented','finding':'Offline finding.',
            'source_refs':[originals[i] if i<5 else exact]} for i,a in enumerate(ASPECTS)],
        'questions':[{'aspect':'decision_conditions','question':'What are the company-addressed folio acceptance conditions?',
                      'why_needed':'The original procedure leaves them unspecified.','source_refs':[exact]}]}
    adapter.value=value;adapter.trace={'trace_id':'trace_offline125','result':copy.deepcopy(value),'attempts':[{'status':'OK'}]}
    before=copy.deepcopy(adapter.trace)
    review=review_requirements(svc,{'workspace_id':wid},ctx)
    ok('actual service saves all five resolved findings',len(review['citation_resolutions'])==5)
    ok('raw provider answer remains unchanged',adapter.trace==before and adapter.value==value)
    from steps import verify_saved125 as stored
    saved_workspace={**svc.workspace(wid,ctx),'workspace_id':stored.WORKSPACE,'source_ids':[stored.SOURCE]}
    saved_source={**source,'workspace_id':stored.WORKSPACE,'source_id':stored.SOURCE}
    saved_value=copy.deepcopy(value)
    for section in ('observations','checks','questions'):
        for item in saved_value[section]:
            for citation in item['source_refs']:citation['source_id']=stored.SOURCE
    saved_trace={'trace_id':'offline_saved_answer','payload':{'goal':saved_workspace['goal']},
                 'source_hashes':{stored.SOURCE:source['version_hash']},'result':saved_value}
    replay=stored.inspect_saved(ROOT,saved_workspace,saved_source,saved_trace,data)
    ok('pre-deploy saved-answer validator restores five references without persistence',
       replay['revalidation']=={'status':'PASSED_IN_MEMORY','saved_to_cloud':False,'restored_citations':5})
    bad=copy.deepcopy(value);bad['checks'][1]['source_refs'][0]['quote']='Invented evidence absent from the policy'
    adapter.value=bad
    try:review_requirements(svc,{'workspace_id':wid},ctx)
    except JTError as error:
        ok('failed evidence reports the precise path and saved trace',error.validation['path']=='checks[1].source_refs[0]' and error.trace['trace_id']=='trace_offline125')
    else:raise AssertionError('invented evidence passed')
    ok('failed evidence cannot replace the last accepted review',len(svc.workspace(wid,ctx)['requirements_review']['citation_resolutions'])==5)

    # Text PDF line breaks use the same exact source restoration.
    from reportlab.pdfgen import canvas
    stream=io.BytesIO();pdf=canvas.Canvas(stream);pdf.drawString(40,700,'Employee paid:');pdf.drawString(40,680,'26800 JPY');pdf.save()
    p=svc.add_source(wid,'example.pdf',stream.getvalue(),'application/pdf',ctx,'pdf_source')
    pr={'source_id':'pdf_source','version_hash':p['version_hash'],'locator':'page:1','quote':'Employee paid: 26800 JPY'}
    fixed,note=resolve_reference(pr,p,blobs,False);validate_ref(fixed,p,blobs)
    ok('PDF whitespace restoration stays inside the cited page',note['method']=='whitespace_restored' and fixed['locator']=='page:1')

# Exercise the new administrator-only validation path, without Flask imports.
tree=ast.parse((ROOT/'app/main.py').read_text());factory=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_app')
function=next(n for n in factory.body if isinstance(n,ast.FunctionDef) and n.name=='error_body')
g=types.SimpleNamespace(ctx={'admin':True},request_id='req_test');scope={'g':g}
exec(compile(ast.Module(body=[function],type_ignores=[]),'error_body125','exec'),scope)
err=JTError('INVALID_INPUT','Evidence location or quotation is invalid.');err.trace={'trace_id':'trace_test','attempts':[{'status':'OK'}]};err.validation={'stage':'requirements_validation','path':'checks[1].source_refs[0]'}
ok('administrator receives post-model validation location',scope['error_body'](err)['error']['diagnostic']['validation']==err.validation)
g.ctx={'admin':False};ok('public error keeps existing bounded response','diagnostic' not in scope['error_body'](err)['error'])
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
    'scope':'Five actual reported references; other response fields and HTTP context are explicit test data. Full saved answer is checked in Cloud Shell before deployment.'}
(ROOT/'verification/citations_125.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

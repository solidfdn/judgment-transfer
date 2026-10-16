"""Bounded updater guards using a temporary copy of the exact accepted package."""
import copy,importlib.util,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release139',ROOT/'releases/jt_release_139.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
decoded=release.payload();baseline=release.DATA['baselines']['1.0.38'];checks=[]
def ok(name,v=True):assert v,name;checks.append(name)
def rejects(name,fn):
    try:fn()
    except RuntimeError as e:ok(name,str(e).startswith('STOP '))
    else:raise AssertionError(name)
# The changed scenario must not alter the reusable engine, validators, prompts or contracts.
for name in ('app/core/models.py','app/approved_execution.py','app/adapters/model.py','app/adapters/evidence.py','app/service.py','app/history.py','app/contracts/jt_contracts.schema.json','requirements.lock'):
    ok('unchanged '+name,release.DATA['new']['files'][name]==baseline['files'][name])
ok('no file deleted',set(baseline['files']).issubset(release.DATA['new']['files']))
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    archive=subprocess.check_output(['git','archive','188478b95e588c5c3af2094972a885c7d32cd3d1'],cwd=ROOT)
    import io,tarfile
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(root,filter='data')
    ok('exact baseline accepted',release.verify_package(root,baseline,None)==baseline)
    progress={'payload_hash':release.sha(release.DATA),'phase':'PREPARED','from_version':'1.0.38','baseline_hash':release.sha(baseline)}
    first=next(n for n in decoded if n!='package-manifest.json');p=root/first;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(decoded[first])
    ok('interrupted update resumes only known old/new bytes',release.verify_package(root,baseline,progress)==baseline)
    p.write_text('unexpected local edit');rejects('unexpected local edit stops before applying',lambda:release.verify_package(root,baseline,progress))
    for name,raw in decoded.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    progress['phase']='DEPLOYED'
    ok('installed package verifies every manifest hash',release.verify_package(root,release.DATA['new'],progress)==baseline)
    rejects('unrecognized baseline refused',lambda:release.verify_package(root,{'version':'1.0.37'},None))
text=(ROOT/'releases/jt_release_139.py').read_text()
ok('all prior USD checkpoints retained',all("'"+v+"/usd-demo.json'" in text for v in ('1.0.34','1.0.35','1.0.36','1.0.37','1.0.38')))
ok('new controller and reviewer flags connected',"'steps/receipt_demo139.py'" in text and '--validate-receipts' in text and '--reviewed-receipt-demo' in text)
ok('unchanged historical display gate can be read from disk',"decoded.get('steps/verify_display138.py') or (root/'steps/verify_display138.py').read_bytes()" in text)
report={'status':'PASSED','checks':checks,'changed_files':len(decoded),'new_model_calls':0,'cloud_writes':0,'scope':'Actual updater payload and baseline/resume/tamper guards. No deploy or model execution.'}
(ROOT/'verification/release139_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

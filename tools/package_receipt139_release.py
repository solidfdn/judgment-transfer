#!/usr/bin/env python3
"""Package the reviewed 1.0.38 -> 1.0.39 change; exclude installers from their own manifest."""
import base64,hashlib,json,subprocess,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def build():
    baseline=json.loads(subprocess.check_output(['git','show','188478b95e588c5c3af2094972a885c7d32cd3d1:package-manifest.json'],cwd=ROOT))
    if baseline['version']!='1.0.38':raise RuntimeError('Expected reviewed 1.0.38 baseline')
    names=set(baseline['files'])
    for parent in ('app/fixtures/expense_review_usd139','steps','tools','verification'):
        for p in (ROOT/parent).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                relative=p.relative_to(ROOT).as_posix()
                if relative in baseline['files'] or '139' in p.name or parent=='app/fixtures/expense_review_usd139':names.add(relative)
    files={n:sha((ROOT/n).read_bytes()) for n in sorted(names)}
    code_hash=sha({n:h for n,h in files.items() if n.startswith('app/')})
    new={**baseline,'version':'1.0.39','app_version':'1.0.39','created':'2026-10-16','previous_code_hash':baseline['code_hash'],'code_hash':code_hash,'files':files}
    (ROOT/'package-manifest.json').write_text(json.dumps(new,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    changed={n:base64.b64encode((ROOT/n).read_bytes()).decode() for n,h in files.items() if baseline['files'].get(n)!=h}
    changed['package-manifest.json']=base64.b64encode((ROOT/'package-manifest.json').read_bytes()).decode()
    data={'baselines':{'1.0.38':baseline},'new':new,'files':changed}
    template=(ROOT/'releases/jt_release_138.py').read_text()
    lines=template.splitlines();lines=[l for l in lines if not l.startswith('DATA = ')]
    template='\n'.join(lines)+'\n'
    template=template.replace('1.0.38','1.0.39').replace('1.0.37','1.0.38').replace('release138','release139')
    # The historical display gate remains the unchanged read-only gate from 1.0.38.
    template=template.replace("decoded['steps/verify_display138.py']", "decoded.get('steps/verify_display138.py') or (root/'steps/verify_display138.py').read_bytes()")
    # compile needs its first argument grouped when the unchanged gate is read from disk.
    template=template.replace("compile(decoded.get('steps/verify_display138.py') or (root/'steps/verify_display138.py').read_bytes(),'verify-display138','exec')", "compile((decoded.get('steps/verify_display138.py') or (root/'steps/verify_display138.py').read_bytes()),'verify-display138','exec')")
    template=template.replace("'1.0.36/usd-demo.json','1.0.38/usd-demo.json'):","'1.0.36/usd-demo.json','1.0.37/usd-demo.json','1.0.38/usd-demo.json'):")
    template=template.replace('--validate-usd','--validate-receipts').replace('args.validate_usd','args.validate_receipts')
    template=template.replace('Replay existing approved USD versions using the rule engine; zero model attempts','Validate the revised receipt scenario: at most four preparation attempts, ten zero-model case executions')
    template=template.replace("'steps/usd_demo138.py'","'steps/receipt_demo139.py'").replace('--reviewed-usd-demo','--reviewed-receipt-demo')
    template=template.replace('"""Versioned 1.0.39: approved-rule execution and zero-model USD comparison."""','"""Versioned 1.0.39: revised employee-addressed receipt scenario and verified new comparison."""')
    encoded=base64.b64encode(zlib.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),9)).decode()
    template=template.replace("VERSION = '1.0.39'", "DATA = json.loads(zlib.decompress(base64.b64decode('"+encoded+"')))\n\nVERSION = '1.0.39'",1)
    destination=ROOT/'releases/jt_release_139.py';destination.write_text(template)
    return {'version':new['version'],'code_hash':code_hash,'changed_files':len(changed),'installer_bytes':destination.stat().st_size}
if __name__=='__main__':print(json.dumps(build(),indent=2))

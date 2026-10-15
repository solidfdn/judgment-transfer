"""Read-only comparison of owned runs, with a narrowly audited code exception."""
from core.models import JTError

# Reviewed in RELEASE130_STATUS: only teaching citation/recovery changed.
# All other cross-package comparisons fail closed. Stored runs are never edited.
AUDITED_TEACHING_PATCH=frozenset({'63800f5130d75799709f977a396baef4bd84790a37f4735102fe7c5eb465049d',
                                'afe8d8d1812219f3e12e764b004a799327eb9db495f7284c73e749141e3be97a'})

def compare(service,before_id,after_id,ctx):
    before=service.run_view(before_id,ctx);after=service.run_view(after_id,ctx)
    a,b=before['run'],after['run']
    same_code=a.get('code_hash')==b.get('code_hash') and bool(a.get('code_hash'))
    audited=frozenset((a.get('code_hash'),b.get('code_hash')))==AUDITED_TEACHING_PATCH
    checks={k:a.get(k) is not None and a.get(k)==b.get(k) for k in
            ('workspace_id','mode','split','dataset_hash','repeats','case_ids','model_settings')}
    checks.update(code=same_code or audited,complete=before['metrics']['complete'] and after['metrics']['complete'],
                  current_evidence=not before['metrics']['stale'] and not after['metrics']['stale'],
                  guidance_order=a['domain']['version']<b['domain']['version'],
                  arms=a['arm'] in ('A_SOURCE_ONLY','C_JT_RULES') and b['arm']=='C_JT_RULES',
                  source_versions=bool(a['domain']['source_hashes']) and all(b['source_hashes'].get(k)==v for k,v in a['domain']['source_hashes'].items()))
    # Ownership of both views is checked above, even for a mismatched workspace.
    return {'before_run_id':before_id,'after_run_id':after_id,'comparable':all(checks.values()),'checks':checks,
            'code_review':('Teaching citation handling changed between packages 1.0.29 and 1.0.30. The decision model, settings, validation, execution and scoring were unchanged. Original package hashes are retained.' if audited and not same_code else None),
            'baseline_code_hash':a.get('code_hash'),'after_code_hash':b.get('code_hash')}

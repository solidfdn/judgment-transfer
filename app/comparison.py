"""Read-only comparison of owned runs, with a narrowly audited code exception."""
from core.models import JTError
import config

# Reviewed in RELEASE130_STATUS: only teaching citation/recovery changed.
# All other cross-package comparisons fail closed. Stored runs are never edited.
AUDITED_TEACHING_PATCH=frozenset({'63800f5130d75799709f977a396baef4bd84790a37f4735102fe7c5eb465049d',
                                'afe8d8d1812219f3e12e764b004a799327eb9db495f7284c73e749141e3be97a'})

# RELEASE136_STATUS and RELEASE137_STATUS audit these directional pairs.
# Preparation transport and its run-start compatibility changed; decision
# behavior is unchanged. Bind to the verified current package to avoid a
# self-hashing constant; unrelated/future packages and reverse pairs fail closed.
PREPARATION_BASELINE='f4b530aabfbec8766e476e83e7a02e2ed3b13412c8d52fc6e435871a18cc5a1e'
PREPARATION_136='80510025398bd5c2f601462122e60210aa451ef8914fe535370078c3af4282ae'

def preparation_transport_pair(a,b):
    if a.get('code_hash')!=PREPARATION_BASELINE:return False
    if b.get('code_hash')==PREPARATION_136:return True
    return b.get('code_hash')=='d45fc6052024e9852054fff188aec41b9558c1886d4950c1876bc6cc82f6d036'

def compare(service,before_id,after_id,ctx):
    before=service.run_view(before_id,ctx);after=service.run_view(after_id,ctx)
    a,b=before['run'],after['run']
    same_code=a.get('code_hash')==b.get('code_hash') and bool(a.get('code_hash'))
    audited=frozenset((a.get('code_hash'),b.get('code_hash')))==AUDITED_TEACHING_PATCH
    preparation_patch=preparation_transport_pair(a,b)
    checks={k:a.get(k) is not None and a.get(k)==b.get(k) for k in
            ('workspace_id','mode','split','dataset_hash','repeats','case_ids','model_settings')}
    checks.update(execution_protocol=a.get('execution_protocol')==b.get('execution_protocol'),code=same_code or audited or preparation_patch,complete=before['metrics']['complete'] and after['metrics']['complete'],
                  current_evidence=not before['metrics']['stale'] and not after['metrics']['stale'],
                  guidance_order=a['domain']['version']<b['domain']['version'],
                  arms=a['arm'] in ('A_SOURCE_ONLY','C_JT_RULES') and b['arm']=='C_JT_RULES',
                  source_versions=bool(a['domain']['source_hashes']) and all(b['source_hashes'].get(k)==v for k,v in a['domain']['source_hashes'].items()))
    # Ownership of both views is checked above, even for a mismatched workspace.
    return {'before_run_id':before_id,'after_run_id':after_id,'comparable':all(checks.values()),'checks':checks,
            'code_review':('The saved baseline is package 1.0.35. Package 1.0.36 corrected preparation transport; 1.0.37 applies the same audited compatibility check when starting the after run. The decision invocation, model, settings, prompt, evidence validator, executor and scorer are unchanged. Original hashes and failure records are retained.' if preparation_patch else 'Teaching citation handling changed between packages 1.0.29 and 1.0.30. The decision model, settings, validation, execution and scoring were unchanged. Original package hashes are retained.' if audited and not same_code else None),
            'preparation_transport_only':preparation_patch,
            'baseline_code_hash':a.get('code_hash'),'after_code_hash':b.get('code_hash')}

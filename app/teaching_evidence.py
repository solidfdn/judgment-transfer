"""Canonical human citations and explicit reuse of an owned saved model answer."""
import copy
import re
from adapters.evidence import validate_ref, text_for
from core.models import JTError, digest

def prepare_rules(service,wid,rules):
    resolutions=[]
    for i,rule in enumerate(rules):
        for j,ref in enumerate(rule.get('source_refs',[])):
            source=service.source(wid,ref['source_id'])
            try:validate_ref(ref,source,service.blobs)
            except JTError as original:
                # No search or wording changes. Require the claimed original lines
                # to contain the exact nonempty quotation under the same hash.
                if (not source.get('human') or source.get('mime')!='text/plain' or
                    source.get('source_id')!=ref.get('source_id') or
                    not re.fullmatch(r'line:\d+(?:-\d+)?',ref.get('locator','')) or
                    not isinstance(ref.get('quote'),str) or not ref['quote'].strip()):raise original
                validate_ref(ref,{**source,'human':False},service.blobs)
                canonical={**ref,'locator':'human:1'}
                validate_ref(canonical,source,service.blobs)
                rule['source_refs'][j]=canonical
                resolutions.append({'path':f'rules[{i}].source_refs[{j}]','method':'verified_human_line_to_canonical_locator',
                                    'original_reference':copy.deepcopy(ref),'resolved_reference':copy.deepcopy(canonical)})
    return rules,resolutions

def recover_teaching(service,body,ctx):
    from service import ident, now, required
    if not ctx.get('admin'):raise JTError('ADMIN_REQUIRED','Saved-answer recovery requires administrator access.',403)
    reviewer=body.get('reviewer_name','')
    if not isinstance(reviewer,str) or not reviewer.strip():raise JTError('REVIEWER_REQUIRED','Enter the responsible reviewer name.')
    operation=required(body,'original_operation')
    if not isinstance(operation,str) or not 8<=len(operation)<=128 or not all(c.isalnum() or c in '-_' for c in operation):
        raise JTError('INVALID_INPUT','Invalid original request key.')
    q=service.owned('questions',required(body,'question_id'),ctx);wid=q['workspace_id'];ws=service.workspace(wid,ctx)
    if ws['frozen'] or ws['approved_count']>=3 or ws['status']!='READY' or q['base_version']!=ws['version']:
        raise JTError('VERSION_CONFLICT','Saved answer no longer matches the active workflow.',409)
    original_ctx={**ctx,'operation':operation};sid=ident('human',original_ctx)
    source=service.source(wid,sid);text=text_for(source,service.blobs)
    request_key=digest([ctx['owner'],'/api/v1/teachings',operation]);request=service.repo.get('requests',request_key)
    error=((request or {}).get('result') or {}).get('error',{})
    trace=service.repo.get('traces',required(body,'trace_id'))
    if (not trace or error.get('code')!='INVALID_INPUT' or error.get('request_id')!=required(body,'original_request_id') or
        trace.get('mode')!='LIVE' or trace.get('purpose')!='draft_rules' or trace.get('error') or
        not trace.get('attempts') or trace['attempts'][-1].get('status')!='OK' or
        trace.get('source_hashes')!={sid:source['version_hash']} or not source.get('human') or
        source.get('workspace_id')!=wid or source['version_hash']!=digest(text.encode()) or
        trace.get('payload',{}).get('human_text')!=text or trace['payload'].get('question')!=q['question'] or
        trace['payload'].get('domain')!=service.domain(ws) or not isinstance(trace.get('result'),dict)):
        raise JTError('SAVED_ANSWER_MISMATCH','The failed request, evidence and saved answer do not match.',409)
    # One stable draft per saved answer, even if the caller uses a different key.
    stable_ctx={**ctx,'operation':'saved-teaching-'+trace['trace_id']}
    record={'origin':'RECOVERED_MODEL_RESPONSE','trace_id':trace['trace_id'],'original_request_id':error['request_id'],
            'original_operation':operation,'reviewer_name':reviewer.strip(),'recorded_at':now(),'memo':str(body.get('memo',''))[:2000],
            'raw_result_hash':digest(trace['result']),'new_model_calls':0}
    return service.save_teaching(ws,q,text,source,trace['result'],trace,stable_ctx,record)

"""Read case evidence separately from shared work instructions and teaching."""
import copy
import re
from adapters.evidence import inspect_file
from core.models import JTError, check, digest, scalar_ok, validate_case
from requirements_review import expanded, obj
from service import ident, now, required

EXTRACT = obj({'observations': {'type': 'array', 'maxItems': 60, 'items': expanded('Observation')}})

def editable(ws):
    if ws['frozen'] or ws['run_ids']:
        raise JTError('FROZEN', 'Add case files before the first test. Start a new check for another dataset.', 409)
    if ws['status'] == 'STALE': raise JTError('STALE', 'Review the changed instructions before adding cases.', 409)

def read_case(service, form, name, data, mime, ctx):
    wid = required(form, 'workspace_id'); ws = service.workspace(wid, ctx); editable(ws)
    domain = service.domain(ws)
    split = form.get('split', 'dev'); stratum = form.get('stratum', 'normal')
    if split not in ('dev', 'holdout') or stratum not in ('normal', 'transfer', 'must_hold'):
        raise JTError('INVALID_INPUT', 'Choose a valid case kind.')
    if split == 'holdout' and not ctx['admin']: raise JTError('ADMIN_REQUIRED', 'Evaluation cases require administrator access.', 403)
    cid = form.get('case_id') or ident('case', ctx)
    if not isinstance(cid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', cid): raise JTError('INVALID_INPUT', 'Invalid case ID.')
    if cid in ws['case_ids']: raise JTError('INVALID_INPUT', 'This case ID is already saved.')
    metadata, _ = inspect_file(name, data, mime)
    sid, did = ident('case_source', ctx), ident('case_draft', ctx)
    blob_id = digest([wid, sid, metadata['version_hash']])
    source = {**metadata, 'source_id': sid, 'workspace_id': wid, 'blob_id': blob_id, 'human': False, 'case_id': cid, 'split': split}
    draft = {'case_draft_id': did, 'workspace_id': wid, 'case_id': cid, 'split': split, 'status': 'READING',
             'domain_hash': digest(domain), 'domain_version': ws['version'], 'source_ids': [sid],
             'source_hashes': {sid: metadata['version_hash']}, 'created_at': now()}
    wk, sk, dk = ('workspaces', wid), ('sources', wid+'-'+sid), ('case_drafts', did)
    def reserve(values):
        w = values[wk]; editable(w)
        if w['version'] != ws['version']: raise JTError('STALE', 'The conditions changed. Read the case again.', 409)
        if len(w.get('case_draft_ids', [])) >= 40 or len(w['case_ids']) >= 40 or w.get('case_source_bytes', 0) + len(data) > 20*1024*1024:
            raise JTError('INPUT_TOO_LARGE', 'Maximum 40 case files and 20 MiB per workspace.', 413)
        w.setdefault('case_source_ids', []).append(sid)
        w.setdefault('case_draft_ids', []).append(did)
        w['case_source_bytes'] = w.get('case_source_bytes', 0) + len(data)
        values[sk], values[dk] = source, draft
    service.blobs.put(blob_id, data, source['mime'])
    service.repo.atomic([wk, sk, dk], reserve)
    try:
        if not hasattr(service.adapter, 'invoke'): raise JTError('LIVE_REQUIRED', 'Document reading requires LIVE mode. No synthetic reading was substituted.', 409)
        payload = {'instruction': (
            'Read this one case document using only the listed input fields. Return English text. '
            'The document may contain a form and its supporting evidence on separate pages. '
            'Return exactly one observation per field. Copy explicitly stated values and cite their exact locations. '
            'Do not calculate missing amounts, infer payment allocation, decide whether the case should pass, '
            'invent matching flags, or read values from expected answers. Missing or contradictory values are UNRESOLVED/null. '
            'Interpretations are INFERRED and will not become facts automatically. Do not extract or assume an initial workflow state.'),
            'fields': domain['input_fields'], 'case_id': cid}
        result, trace = service.adapter.invoke('extract', payload, EXTRACT, [source], ctx['owner'], ctx['admin'])
        facts = {f['field_id']: None for f in domain['input_fields']}
        definitions = {f['field_id']: f for f in domain['input_fields']}; seen = set()
        observations = result.get('observations')
        if not isinstance(observations, list) or len(observations) > 60: raise JTError('INVALID_INPUT', 'Invalid case observations.')
        for observation in observations:
            check('Observation', observation); fid = observation['field_id']
            if fid not in definitions or fid in seen: raise JTError('INVALID_INPUT', 'Case fields must be declared and appear at most once.')
            seen.add(fid)
            if not scalar_ok(observation['value'], definitions[fid]['type']): raise JTError('INVALID_INPUT', 'A case observation has an incorrect type.')
            for ref in observation['source_refs']:
                if ref['source_id'] != sid or ref['version_hash'] != source['version_hash']:
                    raise JTError('INVALID_EVIDENCE', 'Case observations must cite this case file.')
                service.source_check(wid, ref)
            if observation['status'] == 'OBSERVED': facts[fid] = observation['value']
        case = {'case_id': cid, 'domain_id': domain['domain_id'], 'split': split, 'stratum': stratum,
                'facts': facts, 'raw_text': str(form.get('description') or ('Case from '+source['name']))[:4000],
                'initial_state': {f['field_id']: None for f in domain['state_fields']}}
        validate_case(case, domain)
        draft.update(status='DRAFT', case=case, observations=observations, trace_id=trace['trace_id'])
        def save(values):
            w = values[wk]; editable(w)
            if w['version'] != ws['version']: raise JTError('STALE', 'The conditions changed during reading.', 409)
            if values[sk]['version_hash'] != source['version_hash']: raise JTError('STALE', 'The case source changed.', 409)
            values[dk] = draft
        service.repo.atomic([wk, sk, dk], save)
        return {**draft, 'sources': [{k:v for k,v in source.items() if k != 'blob_id'}]}
    except Exception as error:
        def failed(values):
            if values[dk] and values[dk]['status'] == 'READING':
                values[dk].update(status='READ_FAILED', error_code=error.code if isinstance(error, JTError) else 'INTERNAL_ERROR')
        service.repo.atomic([dk], failed)
        raise

def confirm_case(service, body, ctx):
    wid = required(body, 'workspace_id'); ws = service.workspace(wid, ctx); editable(ws)
    draft = service.owned('case_drafts', required(body, 'case_draft_id'), ctx)
    if draft['workspace_id'] != wid or draft['status'] != 'DRAFT': raise JTError('INVALID_INPUT', 'Open an unconfirmed draft from this workspace.')
    if draft['split'] == 'holdout' and not ctx['admin']: raise JTError('ADMIN_REQUIRED', 'Evaluation cases require administrator access.', 403)
    domain = service.domain(ws)
    if digest(domain) != draft['domain_hash']: raise JTError('STALE', 'The conditions changed. Read the case again.', 409)
    case = copy.deepcopy(required(body, 'case')); validate_case(case, domain)
    if case['case_id'] != draft['case_id'] or case['split'] != draft['split']:
        raise JTError('INVALID_INPUT', 'A reviewed case must retain its original identity and split.')
    evidence = {**copy.deepcopy(draft), 'status': 'CONFIRMED', 'confirmed_at': now(),
                'confirmed_by': 'human:'+digest(ctx['owner'])[:12], 'reviewed_case': case, 'case_hash': digest(case)}
    wk, dk, ck, ek = ('workspaces', wid), ('case_drafts', draft['case_draft_id']), ('cases', wid+'-'+case['case_id']), ('case_evidence', wid+'-'+case['case_id'])
    source_keys = [('sources', wid+'-'+sid) for sid in draft['source_ids']]
    from history import prepared
    hk, record, fix = prepared(service, ws, ctx, body, 'case_confirmation',
        {'case': case, 'input_fields': domain['input_fields'], 'observations': draft['observations'], 'trace_id': draft['trace_id']},
        [service.source(wid, sid) for sid in draft['source_ids']])
    evidence.update(reviewer_name=record['reviewer_name'], memo=record['memo'], recorded_at=record['recorded_at'], record_id=record['record_id'])
    def commit(values):
        w = values[wk]; editable(w)
        if w['version'] != draft['domain_version']: raise JTError('STALE', 'The conditions changed.', 409)
        if values[dk]['status'] != 'DRAFT': raise JTError('VERSION_CONFLICT', 'This case was already confirmed.', 409)
        if case['case_id'] in w['case_ids'] or values[ck]: raise JTError('INVALID_INPUT', 'This case ID is already saved.')
        if len(w['case_ids']) >= 40: raise JTError('INPUT_TOO_LARGE', 'Maximum 40 cases.', 413)
        for key in source_keys:
            src = values[key]
            if not src or draft['source_hashes'].get(src['source_id']) != src['version_hash']:
                raise JTError('STALE', 'The case evidence changed.', 409)
        values[ck], values[ek] = case, evidence
        fix(values)
        values[dk] = {**values[dk], 'status': 'CONFIRMED', 'confirmed_at': evidence['confirmed_at']}
        w['case_ids'].append(case['case_id'])
        return {'case_id': case['case_id'], 'count': len(w['case_ids']), 'status': 'CONFIRMED'}
    return service.repo.atomic([wk, dk, ck, ek, hk] + source_keys, commit)

def case_evidence(service, wid, case_ids):
    records = []
    for cid in case_ids:
        item = service.repo.get('case_evidence', wid+'-'+cid)
        if item and item['case_hash'] == digest(service.case(wid, cid)):
            records.append({**item, 'sources': [service.source(wid, sid) for sid in item['source_ids']],
                            'extraction_trace': service.repo.get('traces', item['trace_id'])})
    return records

"""Named, non-editable snapshots with explicit owner-confirmed deletion."""
import copy
from core.models import JTError, digest
from service import ident, now, required
from storage.repository import DELETE

def actor(body):
    name = body.get('reviewer_name'); memo = body.get('memo', '')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120 or any(ord(c) < 32 for c in name):
        raise JTError('REVIEWER_REQUIRED', 'Enter the responsible person’s name before finalizing this record.')
    if not isinstance(memo, str) or len(memo) > 2000: raise JTError('INVALID_INPUT', 'The optional note must be no more than 2000 characters.')
    return {'reviewer_name': name.strip(), 'memo': memo.strip()}

def prepared(service, ws, ctx, body, kind, snapshot, sources):
    person = actor(body); rid = ident('record', ctx, kind); key = ('history', rid)
    record = {'record_id': rid, 'workspace_id': ws['workspace_id'], 'kind': kind,
              **person, 'recorded_at': now(), 'snapshot': copy.deepcopy(snapshot),
              'source_metadata': copy.deepcopy(sources),
              'source_hashes': {s['source_id']: s['version_hash'] for s in sources},
              'actor_session_hash': digest(ctx['owner'])[:24]}
    def append(values):
        w = values[('workspaces', ws['workspace_id'])]
        if values[key] is not None: raise JTError('VERSION_CONFLICT', 'This record already exists and cannot be overwritten.', 409)
        ids = w.setdefault('history_ids', [])
        if len(ids) >= 200: raise JTError('INPUT_TOO_LARGE', 'Maximum 200 finalized records per workspace.', 413)
        record['previous_record_id'] = ids[-1] if ids else None
        record['record_hash'] = digest(record)
        values[key] = copy.deepcopy(record); ids.append(rid)
        return rid
    return key, record, append

def fix_review(service, body, ctx):
    wid = required(body, 'workspace_id'); ws = service.workspace(wid, ctx)
    review = ws.get('requirements_review')
    if not review: raise JTError('EXTRACTION_REQUIRED', 'Review the materials before finalizing a record.', 409)
    sources = service.sources(ws); hashes = {s['source_id']: s['version_hash'] for s in sources}
    if review['source_hashes'] != hashes or review['goal'] != ws['goal']:
        raise JTError('STALE', 'Review the current materials before finalizing.', 409)
    key, record, append = prepared(service, ws, ctx, body, 'requirements_review', review, sources)
    wk = ('workspaces', wid); source_keys = [('sources', wid+'-'+sid) for sid in hashes]
    def commit(values):
        w = values[wk]
        if w.get('requirements_review') != review or w['goal'] != ws['goal'] or w['source_ids'] != ws['source_ids']:
            raise JTError('STALE', 'The review changed before it was finalized.', 409)
        if any(not values[k] or hashes.get(values[k]['source_id']) != values[k]['version_hash'] for k in source_keys):
            raise JTError('STALE', 'The source changed before fixation.', 409)
        append(values)
        return record
    return service.repo.atomic([wk, key] + source_keys, commit)

def fix_result(service, body, ctx):
    run = service.owned('runs', required(body, 'run_id'), ctx)
    ws = service.workspace(run['workspace_id'], ctx)
    result = service.run_view(run['run_id'], ctx, export=True)
    if not result['metrics']['complete']:
        raise JTError('NOT_READY', 'Wait for the test to finish or stop before finalizing its result.', 409)
    snapshot = {k:result[k] for k in ('run','tasks','metrics','receipts')}
    # Evidence trace references stay linked to the original immutable run;
    # copying every provider payload would needlessly inflate the fixed record.
    snapshot['case_evidence'] = [{k:v for k,v in x.items() if k != 'extraction_trace'} for x in result.get('case_evidence', [])]
    sources = run.get('evidence_sources_snapshot', result['source_metadata'])
    if {s['source_id']:s['version_hash'] for s in sources} != run['source_hashes']:
        raise JTError('STALE', 'The original evidence versions must be available before finalizing this result.', 409)
    key, record, append = prepared(service, ws, ctx, body, 'test_result', snapshot, sources)
    def commit(values):
        append(values)
        return record
    return service.repo.atomic([('workspaces', ws['workspace_id']), key], commit)

def records(service, wid, ctx):
    ws = service.workspace(wid, ctx)
    wk = ('workspaces', wid); ids = ws.get('history_ids', [])
    keys = [('history', rid) for rid in ids]
    def read(values):
        if values[wk].get('history_ids', []) != ids:
            raise JTError('HISTORY_CHANGED', 'History changed. Open it again to see the latest records.', 409)
        return [{k:values[key][k] for k in ('record_id','kind','reviewer_name','memo','recorded_at','record_hash','previous_record_id')}
                for key in reversed(keys) if values[key] is not None]
    return service.repo.atomic([wk] + keys, read)

def remove(service, body, ctx, reset=False):
    """Delete only named history snapshots, keeping active work and test results."""
    wid = required(body, 'workspace_id'); ws = service.workspace(wid, ctx)
    if body.get('confirmed') is not True:
        raise JTError('CONFIRMATION_REQUIRED', 'Confirm the history deletion before continuing.', 409)
    ids = body.get('record_ids') if reset else [required(body, 'record_id')]
    if not isinstance(ids, list) or len(ids) > 200 or any(not isinstance(rid, str) or not rid for rid in ids) or len(set(ids)) != len(ids):
        raise JTError('INVALID_INPUT', 'Select the history records to delete.')
    if reset and set(ids) != set(ws.get('history_ids', [])):
        raise JTError('HISTORY_CHANGED', 'History changed. Open it again before resetting.', 409)
    wk = ('workspaces', wid); keys = [('history', rid) for rid in ids]
    def commit(values):
        w = values[wk]
        if not w or w['owner'] != ctx['owner']:
            raise JTError('NOT_FOUND', 'Workspace not found.', 404)
        if reset and set(ids) != set(w.get('history_ids', [])):
            raise JTError('HISTORY_CHANGED', 'History changed. Open it again before resetting.', 409)
        for key in keys:
            record = values[key]
            if key[1] not in w.get('history_ids', []) or not record or record['workspace_id'] != wid:
                raise JTError('NOT_FOUND', 'History record not found in this workspace.', 404)
        w['history_ids'] = [rid for rid in w.get('history_ids', []) if rid not in ids]
        for key in keys: values[key] = DELETE
        return {'workspace_id': wid, 'deleted_record_ids': ids, 'deleted_count': len(ids)}
    return service.repo.atomic([wk] + keys, commit)

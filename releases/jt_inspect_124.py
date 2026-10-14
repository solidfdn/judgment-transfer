#!/usr/bin/env python3
"""Read saved 1.0.24 review and replay validation in memory; zero model calls.

Only Firestore GETs. No application POST, Cloud Storage write, approval, quota
change, installation or deployment. Never print credentials or workspace owner.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'jt-261013-a79fce'
CODE_HASH = '4b1073a4f37c7f7ae9b9c4d03ad001b037cfa306574aa7ab191b29c7a821b76f'
WORKSPACE = 'ws_1fc7f906adcf832815c6347e20fde077'
SOURCE = 'expense_policy_124'


def unpack(document):
    return json.loads(document.get('fields', {}).get('payload', {}).get('stringValue', '{}'))


def inspect_saved(root, workspace, source, trace, data):
    """Use the installed validators on copies; never construct a cloud/model client."""
    sys.path.insert(0, str(root/'app'))
    from adapters.evidence import validate_ref
    from core.models import JTError, check
    from requirements_review import ASPECTS, REVIEW_SCHEMA, review_requirements
    from service import Service
    from jsonschema import Draft202012Validator

    class MemoryRepository:
        def __init__(self):
            self.records = {('workspaces', WORKSPACE): workspace,
                            ('sources', WORKSPACE+'-'+SOURCE): source}
        def get(self, kind, identifier): return copy.deepcopy(self.records.get((kind, identifier)))
        def atomic(self, keys, callback):
            # Isolated copies: a successful replay cannot alter stored history.
            return callback({key: copy.deepcopy(self.records.get(key)) for key in keys})
    class SavedBlob:
        def get(self, identifier):
            if identifier != source['blob_id']: raise RuntimeError('Unexpected evidence requested.')
            return data
    class SavedAnswer:
        mode = 'RECORDED_VALIDATION_ONLY'
        def invoke(self, purpose, payload, contract, sources, owner, admin):
            if (purpose != 'extract' or contract != REVIEW_SCHEMA or
                    payload.get('goal') != trace['payload'].get('goal') or
                    {s['source_id']:s['version_hash'] for s in sources} != trace['source_hashes']):
                raise RuntimeError('Saved answer does not match this validation input.')
            return copy.deepcopy(trace['result']), copy.deepcopy(trace)
    blob = SavedBlob()
    svc = Service(MemoryRepository(), blob, SavedAnswer())
    context = {'owner':workspace['owner'], 'admin':True, 'operation':'read-only-validation-replay124'}
    try:
        review_requirements(svc, {'workspace_id':WORKSPACE, 'goal':trace['payload']['goal']}, context)
        replay = {'status':'PASSED_IN_MEMORY', 'saved_to_cloud':False}
    except JTError as error:
        replay = {'status':'REPRODUCED_FAILURE', 'code':error.code, 'message':error.message[:600]}
    value = trace['result']
    errors = [{'path':list(e.absolute_path), 'constraint':e.validator, 'message':e.message[:500]}
              for e in list(Draft202012Validator(REVIEW_SCHEMA).iter_errors(value))[:8]]
    semantic = []; refs = []; lines = data.decode('utf-8-sig').splitlines()
    aspects = [x.get('aspect') for x in value.get('checks', [])]
    if len(aspects) != 6 or set(aspects) != set(ASPECTS):
        semantic.append({'path':'checks', 'message':'Exactly one of each perspective is required.', 'actual':aspects})
    for section in ('observations', 'checks', 'questions'):
        for i, item in enumerate(value.get(section, [])):
            if section == 'observations':
                try: check('Observation', item)
                except JTError as error:
                    semantic.append({'path':f'{section}[{i}]', 'field_id':item.get('field_id'),
                        'status':item.get('status'), 'value':item.get('value'), 'message':error.message[:500]})
            if item.get('status') == 'documented' and not item.get('source_refs'):
                semantic.append({'path':f'{section}[{i}]', 'message':'Documented finding has no evidence.'})
            for j, ref in enumerate(item.get('source_refs', [])):
                try:
                    if ref.get('source_id') != SOURCE: raise JTError('INVALID_INPUT', 'Wrong source identifier.')
                    validate_ref(ref, source, blob)
                except (JTError, KeyError, TypeError) as error:
                    quote = ref.get('quote', '')
                    refs.append({'path':f'{section}[{i}].source_refs[{j}]', 'locator':ref.get('locator'),
                        'quote':str(quote)[:500], 'message':str(error)[:300],
                        'exact_quote_line_candidates':[n for n,line in enumerate(lines,1) if isinstance(quote,str) and quote and quote in line][:8]})
    return {'revalidation':replay, 'schema_errors':errors, 'semantic_errors':semantic[:8],
            'invalid_reference_count':len(refs), 'invalid_references':refs[:8],
            'question_preview':[x.get('question','')[:250] for x in value.get('questions',[])[:5]]}


def main():
    sys.dont_write_bytecode = True
    root = Path.cwd().resolve()
    config = json.loads((root/'.jt/config.json').read_text())
    manifest = json.loads((root/'package-manifest.json').read_text())
    if config.get('project_id') != PROJECT or manifest.get('code_hash') != CODE_HASH or manifest.get('version') != '1.0.24':
        raise RuntimeError('Expected the existing Judgment Transfer 1.0.24 project/package. No cloud request was sent.')
    # Reuse the original pinned environment; do not install or upgrade anything.
    venv = root/'.venv'
    if Path(sys.prefix).resolve() != venv.resolve():
        executable = venv/'bin/python'
        if not executable.is_file(): raise RuntimeError('The existing .venv is missing. No packages were installed.')
        os.execv(str(executable), [str(executable), str(Path(__file__).resolve())])
    source_path = root/'app/web/samples/expense_policy.txt'
    data = source_path.read_bytes(); source_hash = hashlib.sha256(data).hexdigest()
    if source_hash != manifest['files']['app/web/samples/expense_policy.txt']:
        raise RuntimeError('The local fictional policy has changed. No cloud request was sent.')
    process = subprocess.run(['gcloud','auth','print-access-token'], capture_output=True, text=True)
    if process.returncode or not process.stdout.strip():
        raise RuntimeError('The existing Cloud Shell login could not be used. No credentials were printed.')
    token = process.stdout.strip()
    base = 'https://firestore.googleapis.com/v1/projects/'+PROJECT+'/databases/(default)/documents/'
    def read(path):
        request = urllib.request.Request(base+path, method='GET', headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request, timeout=30) as response: return json.load(response)
    workspace = unpack(read('jt_workspaces/'+WORKSPACE))
    source = unpack(read('jt_sources/'+WORKSPACE+'-'+SOURCE))
    if (workspace.get('workspace_id') != WORKSPACE or workspace.get('source_ids') != [SOURCE] or
            source.get('source_id') != SOURCE or source.get('version_hash') != source_hash or source.get('mime') != 'text/plain'):
        raise RuntimeError('The saved input differs from the fixed fictional source-review gate.')
    key = hashlib.sha256(json.dumps([workspace['owner'],'/api/v1/requirements/review','source-review124-check'],
        ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    request_record = unpack(read('jt_requests/'+key))
    error = (request_record.get('result') or {}).get('error', {})
    matches = []; page_token = None; scanned = 0
    for page in range(20):
        query = {'pageSize':'200', 'mask.fieldPaths':'payload'}
        if page_token: query['pageToken'] = page_token
        page_result = read('jt_traces?'+urllib.parse.urlencode(query))
        for document in page_result.get('documents', []):
            scanned += 1; trace = unpack(document)
            if (trace.get('purpose') == 'extract' and trace.get('settings', {}).get('code_hash') == CODE_HASH and
                    trace.get('source_hashes') == {SOURCE:source_hash} and
                    trace.get('payload', {}).get('goal') == workspace['goal']):
                matches.append(trace)
        page_token = page_result.get('nextPageToken')
        if not page_token: break
    if page_token or len(matches) != 1 or not isinstance(matches[0].get('result'), dict):
        raise RuntimeError('Expected exactly one saved model answer; matched '+str(len(matches))+'. No generation was attempted.')
    trace = matches[0]
    report = {'diagnostic':'Judgment Transfer 1.0.24 saved-answer validation', 'read_only':True,
        'new_model_calls':0, 'cloud_writes':0, 'workspace_id':WORKSPACE, 'trace_id':trace['trace_id'],
        'trace_documents_scanned':scanned,
        'saved_application_error':{k:error[k] for k in ('code','message','request_id') if k in error},
        'model_attempt_statuses':[a.get('status') for a in trace.get('attempts', [])]}
    report.update(inspect_saved(root, workspace, source, trace, data))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try: main()
    except urllib.error.HTTPError as error:
        sys.exit('STOP CLOUD_READ_'+str(error.code)+' / Saved records could not be read. No access settings were changed.')
    except Exception as error:
        detail = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        sys.exit('STOP READ_ONLY_DIAGNOSTIC / '+detail+'. No model call or cloud write was made.')

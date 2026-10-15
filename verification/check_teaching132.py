"""Real teaching adapter/service with an explicit unary SDK double; no network."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
# The isolated test environment may omit the production HTTP client. No request
# is made here; exception names are sufficient for the unary SDK double.
try:
    import httpx
except ModuleNotFoundError:
    sys.modules['httpx'] = types.SimpleNamespace(**{name: type(name, (Exception,), {}) for name in
        ('ReadTimeout', 'TimeoutException', 'NetworkError', 'RemoteProtocolError')})
from adapters.evidence import inspect_file, validate_ref
from adapters.model import Budget, LiveAdapter, TEACHING_PROPOSAL_SCHEMA
from core.models import CONTRACT, JTError, digest, permitted
from service import Service
from storage.repository import Blobs, LocalRepository

checks = []
def ok(name, condition=True):
    assert condition, name
    checks.append(name)

class Item(types.SimpleNamespace):
    @classmethod
    def from_text(cls, **kwargs): return cls(**kwargs)

EXPLANATION = ('A laptop may be prepared when its recorded training status is COMPLETED.\n'
               'If the training status is missing, keep the request on hold.\n'
               'Preparation does not authorize release of the equipment.')
RULE = {'rule_id': 'prepare_laptop', 'priority': 1,
        'statement': 'Prepare a laptop after recorded training is complete.',
        'when': {'all': [{'field_id': 'equipment_type', 'operator': 'eq', 'value': 'LAPTOP'},
                         {'field_id': 'training_status', 'operator': 'eq', 'value': 'COMPLETED'}], 'any': []},
        'action_id': 'prepare', 'approved_by': None}
DOMAIN = {'schema_version': '1.0', 'domain_id': 'equipment_test', 'version': 0,
          'title': 'Equipment preparation', 'goal': 'Prepare equipment for a later release decision.',
          'input_fields': [{'field_id': name, 'label': name, 'type': 'string', 'description': 'Recorded ' + name,
                            'required': True} for name in ('equipment_type', 'training_status')],
          'state_fields': [{'field_id': 'status', 'label': 'Status', 'type': 'string',
                            'description': 'Isolated preparation status', 'required': True}],
          'actions': [{'action_id': action, 'label': action, 'description': 'Isolated ' + action,
                       'effects': [{'field_id': 'status', 'value': action.upper()}], 'terminal': True}
                      for action in ('hold', 'prepare')],
          'rules': [], 'default_action_id': 'hold', 'source_hashes': {}}

with tempfile.TemporaryDirectory() as folder:
    repo, blobs = LocalRepository(folder), Blobs(folder)
    adapter = LiveAdapter.__new__(LiveAdapter)
    adapter.repo, adapter.blobs, adapter.budget = repo, blobs, Budget(repo)
    adapter.types = Item(Part=Item, Content=Item, HttpOptions=Item, HttpRetryOptions=Item,
                         CountTokensConfig=Item, GenerateContentConfig=Item, ThinkingConfig=Item)
    proposal = {'rules': [copy.deepcopy(RULE)]}
    calls = []
    def generate(**kwargs):
        raw = json.dumps(proposal, ensure_ascii=False, indent=2) + '\n'
        calls.append({'request': kwargs, 'raw': raw, 'proposal': copy.deepcopy(proposal)})
        return Item(text=raw, model_version='EXPLICIT_OFFLINE_DOUBLE',
                    usage_metadata=Item(prompt_token_count=100, candidates_token_count=100,
                                        thoughts_token_count=0, traffic_type='ON_DEMAND'))
    adapter.client = Item(models=Item(count_tokens=lambda **kwargs: Item(total_tokens=100),
                                     generate_content=generate))
    service = Service(repo, blobs, adapter)
    ctx = {'owner': 'offline_teaching132', 'admin': False, 'operation': 'create_workspace132'}
    wid = service.create_workspace({'goal': DOMAIN['goal']}, ctx)['workspace_id']
    ws = service.workspace(wid, ctx)
    ws.update(version=0, status='READY')
    repo.put('workspaces', wid, ws)
    repo.put('domains', wid + '-v0', {'domain': copy.deepcopy(DOMAIN), 'origin': 'EXPLICIT_OFFLINE_DOUBLE'})
    question = {'question_id': 'question_equipment', 'text': 'When may this laptop be prepared?',
                'affected_dev_case_ids': ['equipment_02'], 'missing_field_ids': [], 'source_refs': [],
                'why_needed': 'The supplied workflow leaves this condition unresolved.'}
    repo.put('questions', question['question_id'], {'workspace_id': wid, 'question': question, 'base_version': 0})
    ctx['operation'] = 'teaching132-first'
    doc = service.teach({'question_id': question['question_id'], 'human_text': EXPLANATION}, ctx)
    trace = repo.get('traces', doc['trace_id'])
    original_trace = copy.deepcopy(trace)
    source = service.source(wid, doc['source_id'])
    ref = doc['teaching']['proposed_rules'][0]['source_refs'][0]
    ok('provider proposal contains business conditions without generated citations',
       calls[-1]['request']['config'].response_json_schema == TEACHING_PROPOSAL_SCHEMA and
       'source_refs' not in TEACHING_PROPOSAL_SCHEMA['properties']['rules']['items']['properties'])
    ok('global Rule contract still requires source references',
       'source_refs' in CONTRACT['$defs']['Rule']['required'] and
       CONTRACT['$defs']['Rule']['properties']['source_refs']['minItems'] == 1)
    ok('one exact persisted human source accompanies the generation',
       trace['source_hashes'] == {source['source_id']: source['version_hash']} and
       trace['payload']['human_text'] == EXPLANATION and len(calls) == 1)
    ok('application binds the full explanation under its original source version',
       ref == {'source_id': source['source_id'], 'version_hash': digest(EXPLANATION.encode()),
               'locator': 'human:1', 'quote': EXPLANATION})
    validate_ref(ref, source, blobs)
    ok('provider parsed answer and literal response remain unchanged',
       trace['result'] == calls[-1]['proposal'] == proposal and
       trace['raw_response_text'] == calls[-1]['raw'] and 'source_refs' not in trace['result']['rules'][0])
    binding = doc['application_source_binding']
    ok('saved provenance explicitly requires human semantic review',
       binding['method'] == 'single_saved_human_explanation' and
       binding['semantic_support'] == 'requires_human_review' and
       binding['source_ref'] == ref and binding['provider_result_hash'] == digest(trace['result']) and
       binding['trace_id'] == trace['trace_id'] and binding['rule_ids'] == ['prepare_laptop'] and
       repo.get('teachings', doc['teaching']['teaching_id'])['application_source_binding'] == binding)
    ok('new source binding is not labeled as recovered model quotation', 'citation_resolutions' not in doc)
    ok('draft has no activation or approval', doc['teaching']['approval_state'] == 'DRAFT' and
       all(rule['approved_by'] is None for rule in doc['teaching']['proposed_rules']) and
       service.workspace(wid, ctx)['version'] == 0 and service.domain(ws)['rules'] == [])

    for name, change in [('wrong location', {'locator': 'line:1'}),
                         ('invented text', {'quote': 'This sentence is absent.'}),
                         ('wrong version', {'version_hash': '0' * 64})]:
        try: validate_ref({**ref, **change}, source, blobs)
        except JTError: ok(name + ' still rejected by the unchanged evidence validator')
        else: raise AssertionError(name)
    count = len(calls)
    for name, text, src in [('different explanation', EXPLANATION + ' Altered.', source),
                            ('nonhuman source', EXPLANATION, {**source, 'human': False}),
                            ('different source hash', EXPLANATION, {**source, 'version_hash': '0' * 64})]:
        try: adapter.draft_rules(DOMAIN, question, text, src, ctx['owner'], False)
        except JTError: ok(name + ' rejected before generation', len(calls) == count)
        else: raise AssertionError(name)
    blobs.put(source['blob_id'], b'Changed persisted bytes', 'text/plain')
    try: adapter.draft_rules(DOMAIN, question, EXPLANATION, source, ctx['owner'], False)
    except JTError: ok('changed source bytes rejected before generation', len(calls) == count)
    else: raise AssertionError('tampered source')
    blobs.put(source['blob_id'], EXPLANATION.encode(), 'text/plain')

    long_text = (EXPLANATION + '\r\n' + '\u00e9' * 6000)[:6000]
    metadata, _ = inspect_file('long_explanation.txt', long_text.encode(), 'text/plain')
    long_source = {**metadata, 'source_id': 'human_long132', 'blob_id': 'long_explanation132', 'human': True}
    blobs.put(long_source['blob_id'], long_text.encode(), 'text/plain')
    long_result, _ = adapter.draft_rules(DOMAIN, question, long_text, long_source, ctx['owner'], False)
    long_ref = long_result['rules'][0]['source_refs'][0]
    validate_ref(long_ref, long_source, blobs)
    ok('full 6000-character explanation preserves Unicode and original line endings', long_ref['quote'] == long_text)
    count = len(calls)
    try: service.teach({'question_id': question['question_id'], 'human_text': long_text + 'x'}, ctx)
    except JTError as error: ok('existing explanation length limit remains enforced before generation',
                              error.code == 'INVALID_INPUT' and len(calls) == count)
    else: raise AssertionError('oversize explanation')

    proposal = {'rules': [{**copy.deepcopy(RULE), 'source_refs': [ref]}]}
    ctx['operation'] = 'teaching132-injected-reference'
    try: service.teach({'question_id': question['question_id'], 'human_text': EXPLANATION}, ctx)
    except JTError as error:
        ok('unexpected provider citations fail the proposal contract in one attempt',
           error.code == 'MODEL_FAILED' and len(error.trace['attempts']) == 1 and
           error.trace['raw_response_text'] == calls[-1]['raw'] and 'result' not in error.trace)
    else: raise AssertionError('provider reference injected')
    proposal = {'rules': [copy.deepcopy(RULE)]}
    proposal['rules'][0]['when']['all'][0]['field_id'] = 'undeclared_field'
    ctx['operation'] = 'teaching132-unknown-field'
    try: service.teach({'question_id': question['question_id'], 'human_text': EXPLANATION}, ctx)
    except JTError as error:
        ok('source binding cannot bypass declared-field validation',
           error.code == 'INVALID_INPUT' and error.trace['result'] == proposal)
    else: raise AssertionError('unknown field accepted')
    proposal = {'rules': [copy.deepcopy(RULE), {**copy.deepcopy(RULE), 'rule_id': 'conflicting', 'action_id': 'hold'}]}
    ctx['operation'] = 'teaching132-conflict'
    try: service.teach({'question_id': question['question_id'], 'human_text': EXPLANATION}, ctx)
    except JTError as error: ok('conflicting rules still rejected', error.code == 'RULE_CONFLICT')
    else: raise AssertionError('conflict accepted')
    ok('rejected proposals cannot create a teaching or replace the active workflow',
       service.workspace(wid, ctx)['teaching_ids'] == [doc['teaching']['teaching_id']] and
       service.workspace(wid, ctx)['version'] == 0)

    ctx['operation'] = 'teaching132-approval'
    try: service.approve_teaching(doc['teaching']['teaching_id'], {'base_version': 0}, ctx)
    except JTError as error: ok('named reviewer remains required', error.code == 'REVIEWER_REQUIRED')
    else: raise AssertionError('unnamed approval')
    approved = service.approve_teaching(doc['teaching']['teaching_id'],
                                       {'base_version': 0, 'reviewer_name': 'Offline validation', 'memo': 'Explicit test double.'}, ctx)
    current = service.workspace(wid, ctx)
    record = repo.get('history', current['history_ids'][-1])
    ok('named approval creates the next version and dated history', approved['version'] == 1 and
       record['reviewer_name'] == 'Offline validation' and bool(record['recorded_at']) and
       repo.get('domains', wid + '-v0')['domain']['rules'] == [])
    ok('approved known condition prepares equipment',
       permitted(approved['domain'], {'equipment_type': 'LAPTOP', 'training_status': 'COMPLETED'})[0] == 'prepare')
    ok('unknown condition still holds',
       permitted(approved['domain'], {'equipment_type': 'LAPTOP', 'training_status': None})[0] == 'hold')
    ok('approval never rewrites the provider response', repo.get('traces', trace['trace_id']) == original_trace)

report = {'passed': len(checks), 'checks': checks, 'new_model_calls': 0, 'cloud_writes': 0,
          'scope': 'Actual LIVE adapter, service, evidence and approval paths with an explicit local SDK double. No live reliability claim.'}
(ROOT / 'verification/teaching132_offline.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))

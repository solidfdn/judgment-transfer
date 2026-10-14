"""Source-grounded requirements review; no business-specific execution logic."""
import copy
from jsonschema import Draft202012Validator
from core.models import CONTRACT, JTError, check
from service import ident, now, required

ASPECTS = ('purpose_scope', 'required_information', 'steps_operations',
           'decision_conditions', 'exceptions_human_review', 'completion')

def expanded(name):
    def walk(value):
        if isinstance(value, dict):
            if '$ref' in value: return walk(CONTRACT['$defs'][value['$ref'].split('/')[-1]])
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list): return [walk(v) for v in value]
        return value
    return walk(CONTRACT['$defs'][name])

def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

def words(maximum): return {'type': 'string', 'minLength': 1, 'maxLength': maximum}
REFS = {'type': 'array', 'maxItems': 8, 'items': expanded('SourceRef')}
REVIEW_SCHEMA = obj({
    'observations': {'type': 'array', 'maxItems': 60, 'items': expanded('Observation')},
    'summary': words(400),
    'checks': {'type': 'array', 'minItems': 6, 'maxItems': 6, 'items': obj({
        'aspect': {'type': 'string', 'enum': list(ASPECTS)},
        'status': {'type': 'string', 'enum': ['documented', 'needs_clarification', 'not_provided']},
        'finding': words(500), 'source_refs': REFS})},
    'questions': {'type': 'array', 'maxItems': 5, 'items': obj({
        'question': words(250), 'why_needed': words(350),
        'aspect': {'type': 'string', 'enum': list(ASPECTS)}, 'source_refs': REFS})}
})

def review_requirements(service, body, ctx):
    wid = required(body, 'workspace_id'); ws = service.workspace(wid, ctx)
    if ws['frozen']: raise JTError('FROZEN', 'This evaluation is frozen.', 409)
    sources = service.sources(ws)
    if not sources: raise JTError('SOURCE_REQUIRED', 'Add a file or explanation first.')
    goal = str(body.get('goal') or ws['goal'])[:2000]
    hashes = {s['source_id']: s['version_hash'] for s in sources}
    payload = {'instruction': (
        'Review the supplied materials for the stated job, in any business domain. Return all text in clear English. '
        'Separate source observations from inference. Review exactly the six listed aspects once each. '
        'Describe what the material actually establishes and what remains missing or contradictory. '
        'Documented findings require exact source references. Missing information is not evidence of a negative fact. '
        'Ask at most five specific questions: identify the situation, what the owner must clarify, and why it changes the work. '
        'Prioritize the questions that prevent a correct decision. Avoid generic checklists, invented company policies, '
        'invented integrations, approvals or claims of automation readiness. If the job cannot yet be represented as a '
        'bounded practice workflow, still provide a useful requirements review. These are review findings, not numerical scores. '
        'Use OBSERVED for explicit content only, INFERRED for interpretation and UNRESOLVED with null for unavailable/conflicting facts. '
        'Never use hidden cases, expected answers or reference rules.'), 'goal': goal, 'aspects': list(ASPECTS)}
    if not hasattr(service.adapter, 'invoke'): raise JTError('LIVE_REQUIRED', 'Requirements review needs LIVE mode. No synthetic review was substituted.', 409)
    result, trace = service.adapter.invoke('extract', payload, REVIEW_SCHEMA, sources, ctx['owner'], ctx['admin'])
    errors = list(Draft202012Validator(REVIEW_SCHEMA).iter_errors(result))
    if errors: raise JTError('INVALID_INPUT', 'The requirements review did not match the response contract.')
    if {x['aspect'] for x in result['checks']} != set(ASPECTS):
        raise JTError('INVALID_INPUT', 'Each review perspective must appear exactly once.')
    for item in result['observations']: check('Observation', item)
    for item in result['observations'] + result['checks'] + result['questions']:
        if item.get('status') == 'documented' and not item['source_refs']:
            raise JTError('INVALID_EVIDENCE', 'A documented finding needs supporting evidence.')
        for ref in item['source_refs']:
            if hashes.get(ref['source_id']) != ref['version_hash']:
                raise JTError('INVALID_EVIDENCE', 'Review evidence must come from the supplied work materials.')
            service.source_check(wid, ref)
    review = {**copy.deepcopy(result), 'source_hashes': hashes, 'goal': goal,
              'trace_id': trace['trace_id'], 'created_at': now()}
    wk = ('workspaces', wid)
    source_keys = [('sources', wid + '-' + sid) for sid in hashes]
    def commit(values):
        current = values[wk]
        if current['frozen']: raise JTError('FROZEN', 'This evaluation is frozen.', 409)
        if current['version'] != ws['version'] or current['goal'] != ws['goal'] or current['source_ids'] != ws['source_ids']:
            raise JTError('STALE', 'The work changed during review. Review the current materials.', 409)
        if any(not values[k] or values[k]['version_hash'] != hashes[k[1][len(wid)+1:]] for k in source_keys):
            raise JTError('STALE', 'A source changed during review.', 409)
        if current['version'] >= 0 and current['goal'] != goal: current['status'] = 'STALE'
        current['goal'] = goal
        current['requirements_review'] = review
        current['extraction'] = {'observations': review['observations'], 'source_hashes': hashes, 'trace_id': trace['trace_id']}
        current['shared_trace_ids'].append(trace['trace_id'])
        return review
    return service.repo.atomic([wk] + source_keys, commit)

"""Declarative contracts and deterministic execution; no business-name branches."""
import copy
import hashlib
import json
import math
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'contracts/jt_contracts.schema.json').read_text())

class JTError(Exception):
    def __init__(self, code, message, status=400, retryable=False):
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        super().__init__(message)

def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()

def check(name, value):
    schema = {'$ref': '#/$defs/' + name, '$defs': CONTRACT['$defs']}
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        e = errors[0]
        raise JTError('INVALID_INPUT', f'{name}.{list(e.path)}: {e.message}')
    return value

def scalar_ok(value, kind):
    if value is None:
        return True
    return {'string': lambda: isinstance(value, str), 'number': lambda: type(value) in (int, float) and math.isfinite(value), 'boolean': lambda: type(value) is bool}[kind]()

def validate_domain(domain, source_check=None):
    check('DomainSpec', domain)
    fields = domain['input_fields'] + domain['state_fields']
    if len(fields) > 60 or len(domain['rules']) > 100 or len(domain['actions']) > 20:
        raise JTError('INVALID_INPUT', 'Maximum: 60 fields, 100 rules and 20 actions.')
    field_map = {f['field_id']: f for f in fields}
    actions = {a['action_id']: a for a in domain['actions']}
    if len(field_map) != len(fields) or len(actions) != len(domain['actions']) or len({r['rule_id'] for r in domain['rules']}) != len(domain['rules']):
        raise JTError('INVALID_INPUT', 'Identifiers must be unique, including input and state fields.')
    if domain['default_action_id'] not in actions:
        raise JTError('INVALID_INPUT', 'The hold action is not defined.')
    state_fields = {f['field_id']: f for f in domain['state_fields']}
    for action in actions.values():
        for effect in action['effects']:
            if effect['field_id'] not in state_fields or not scalar_ok(effect['value'], state_fields[effect['field_id']]['type']):
                raise JTError('INVALID_INPUT', 'An effect refers to an unknown or incorrectly typed state field.')
    identical = {}
    for rule in domain['rules']:
        if rule['action_id'] not in actions or not (rule['when']['all'] or rule['when']['any']):
            raise JTError('INVALID_INPUT', 'Every rule needs conditions and a declared action.')
        for condition in rule['when']['all'] + rule['when']['any']:
            f = field_map.get(condition['field_id'])
            if not f:
                raise JTError('INVALID_INPUT', 'Add and approve the new field before using it in a rule.')
            op, value = condition['operator'], condition['value']
            if op in ('gt', 'gte', 'lt', 'lte') and (f['type'] != 'number' or type(value) not in (int, float)):
                raise JTError('INVALID_INPUT', 'Ordered comparisons require numbers.')
            if op == 'in' and (not isinstance(value, list) or not value or any(v is None or not scalar_ok(v, f['type']) for v in value)):
                raise JTError('INVALID_INPUT', 'Membership requires a nonempty list of typed scalar values.')
            if op in ('eq', 'ne') and (value is None or not scalar_ok(value, f['type'])):
                raise JTError('INVALID_INPUT', 'Use exists for missing values; comparisons require a typed value.')
        signature = digest([rule['priority'], rule['when']])
        if signature in identical and identical[signature] != rule['action_id']:
            raise JTError('RULE_CONFLICT', 'Identical rules at the same priority prescribe different actions.', 422)
        identical[signature] = rule['action_id']
        for source in rule['source_refs']:
            if domain['source_hashes'].get(source['source_id']) != source['version_hash']:
                raise JTError('INVALID_INPUT', 'Rule evidence does not match the source version.')
            if source_check:
                source_check(source)
    return domain

def validate_case(case, domain):
    check('Case', case)
    if case['domain_id'] != domain['domain_id']:
        raise JTError('INVALID_INPUT', 'Case and workflow identifiers differ.')
    for container, definitions in [('facts', domain['input_fields']), ('initial_state', domain['state_fields'])]:
        values = case[container]
        allowed = {f['field_id'] for f in definitions}
        if set(values) - allowed:
            raise JTError('INVALID_INPUT', 'Unknown case field.')
        for f in definitions:
            if f['required'] and f['field_id'] not in values:
                raise JTError('INVALID_INPUT', 'Missing key: ' + f['field_id'])
            if not scalar_ok(values.get(f['field_id']), f['type']):
                raise JTError('INVALID_INPUT', 'Incorrect type: ' + f['field_id'])

def compare(c, values):
    a, b, op = values.get(c['field_id']), c['value'], c['operator']
    if op == 'exists':
        return a is not None
    if a is None:
        return None
    if op in ('gt', 'gte', 'lt', 'lte'):
        if type(a) not in (int, float) or type(b) not in (int, float):
            return None
        return {'gt': a > b, 'gte': a >= b, 'lt': a < b, 'lte': a <= b}[op]
    same = (type(a) is type(b) or type(a) in (int, float) and type(b) in (int, float))
    if op == 'eq': return same and a == b
    if op == 'ne': return not (same and a == b)
    if op == 'in': return any(compare({'field_id': c['field_id'], 'operator': 'eq', 'value': x}, values) for x in b)
    raise JTError('INVALID_INPUT', 'Unknown comparison.')

def and3(values):
    return False if False in values else None if None in values else True

def or3(values):
    return True if True in values else None if None in values else False

def evaluate(expression, values):
    return and3([and3([compare(c, values) for c in expression['all']]), or3([compare(c, values) for c in expression['any']]) if expression['any'] else True])

def permitted(domain, values):
    """UNKNOWN at the current priority cannot fall through to a lower permission."""
    for priority in sorted({r['priority'] for r in domain['rules']}):
        matches = [(r, evaluate(r['when'], values)) for r in domain['rules'] if r['priority'] == priority]
        if any(result is None for _, result in matches):
            return domain['default_action_id'], [], 'Evidence is incomplete at this priority.'
        accepted = [r for r, result in matches if result is True]
        if len({r['action_id'] for r in accepted}) > 1:
            return domain['default_action_id'], [], 'Conflicting rules require a human decision.'
        if accepted:
            return accepted[0]['action_id'], [r['rule_id'] for r in accepted], 'Approved conditions match.'
    return domain['default_action_id'], [], 'No approved condition permits completion.'

def execute(domain, case, state, decision, enforce_rules=True):
    check('Decision', decision)
    if decision['case_id'] != case['case_id']:
        raise JTError('INVALID_INPUT', 'Model returned a different case identifier.')
    actions = {a['action_id']: a for a in domain['actions']}
    if decision['action_id'] not in actions:
        raise JTError('INVALID_INPUT', 'Model requested an undeclared action.')
    result = copy.deepcopy(decision)
    if result['outcome'] == 'HOLD' or result['action_id'] == domain['default_action_id']:
        result['outcome'] = 'HOLD'
        result['action_id'] = domain['default_action_id']
    if enforce_rules and result['action_id'] != domain['default_action_id']:
        allowed, rules, reason = permitted(domain, {**case['facts'], **state})
        if result['action_id'] != allowed or not result['rule_ids'] or not set(result['rule_ids']).issubset(set(rules)):
            result.update(outcome='HOLD', action_id=domain['default_action_id'], rule_ids=[], explanation=reason + ' Proposed operation was held.')
    action = actions[result['action_id']]
    after = copy.deepcopy(state)
    for effect in action['effects']:
        after[effect['field_id']] = effect['value']
    return result, after, action['terminal'] or result['action_id'] == domain['default_action_id']

def score(case, decision, state, expected, completed=True):
    if expected is None:
        return {'labelled': False, 'correct': None, 'correct_completion': None, 'critical_error': None}
    correct = completed and decision.get('action_id') == expected['expected_action_id'] and state == expected['expected_state']
    return {'labelled': True, 'correct': correct, 'correct_completion': correct and decision.get('outcome') != 'HOLD', 'critical_error': decision.get('action_id') in expected['critical_wrong_actions']}

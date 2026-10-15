"""Execute only approved declarative conditions; no model or scoring labels."""
import copy
from core.models import JTError, digest, permitted, validate_domain

PROTOCOL = 'APPROVED_RULE_ENGINE_V1'


def decision(domain, case, state):
    validate_domain(domain)
    if not domain['rules'] or any(not str(r.get('approved_by') or '').startswith('human:') or not r['source_refs'] for r in domain['rules']):
        raise JTError('APPROVAL_REQUIRED', 'Only conditions with recorded human approval and evidence can execute.', 409)
    action, ids, reason = permitted(domain, {**case['facts'], **state})
    matched = [r for r in domain['rules'] if r['rule_id'] in ids]
    # Default holds cite the approved policy without claiming that a rule matched.
    refs = []; seen = set()
    for rule in matched or domain['rules']:
        for ref in rule['source_refs']:
            key = digest(ref)
            if key not in seen: refs.append(copy.deepcopy(ref)); seen.add(key)
    hold = action == domain['default_action_id']
    return {'case_id': case['case_id'], 'outcome': 'HOLD' if hold else 'PROPOSE',
        'action_id': action, 'rule_ids': ids, 'source_refs': refs,
        'missing_fields': [f['field_id'] for f in domain['input_fields'] if case['facts'].get(f['field_id']) is None],
        'explanation': ' '.join(r['statement'] for r in matched) if matched else reason + ' The approved default is to hold for review.'}

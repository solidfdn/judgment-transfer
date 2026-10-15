"""Apply an explicit approved stop before asking a model for a decision."""
import copy
from core.models import digest, permitted


def decision(domain, case, state, arm):
    if arm!='C_JT_RULES':return None
    action,ids,_=permitted(domain,{**case['facts'],**state})
    if action!=domain['default_action_id'] or not ids:return None
    rules=[r for r in domain['rules'] if r['rule_id'] in ids]
    if len(rules)!=len(set(ids)) or any(not str(r.get('approved_by') or '').startswith('human:') for r in rules):return None
    refs=[];seen=set()
    for rule in rules:
        if not rule['source_refs']:return None
        for ref in rule['source_refs']:
            key=digest(ref)
            if key not in seen:refs.append(copy.deepcopy(ref));seen.add(key)
    return {'case_id':case['case_id'],'outcome':'HOLD','action_id':action,'rule_ids':ids,'source_refs':refs,
        'missing_fields':[f['field_id'] for f in domain['input_fields'] if case['facts'].get(f['field_id']) is None],
        'explanation':' '.join(r['statement'] for r in rules)}

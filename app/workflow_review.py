"""Conservative draft checks, not a complete semantic verifier.

Common policy-result inputs and conditional amount inputs need revision before
approval. Explicit source-record checkboxes remain possible. Other errors still
require the existing source and human review; an empty list is not certification.
"""
import re


def input_issues(domain):
    issues = []
    verdict = re.compile(r'\b(accepted|acceptance|eligible|eligibility|compliant|compliance|valid|validity|permitted|permission|allowed|matches|matched|matching)\b', re.I)
    for field in domain['input_fields']:
        fid = field['field_id']
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', fid).replace('_', ' ').replace('-', ' ')
        name += ' ' + field['label']
        description = field.get('description', '')
        # This exemption is a declaration to review against the sources, not
        # independent proof that a checkbox exists or is accurate.
        recorded_checkbox = bool(re.search(r'\b(copy|read|transcribe)\b.*\b(checkbox|check box|tick box)\b', description, re.I))
        conclusion = bool(verdict.search(name)) and (field['type'] == 'boolean' or bool(re.match(r'^(is|can|meets|passes)\b', name, re.I)))
        if conclusion and not recorded_checkbox:
            issues.append({'code':'INPUT_IS_DECISION', 'field_id':fid,
                'message':field['label']+' asks for a judgment. Use the stated document values and express the decision in the conditions.'})
        if field['type'] == 'number' and re.search(r'\b(marked|only if|only when)\s+[\"\x27]?(paid|approved|accepted)\b', description, re.I):
            issues.append({'code':'CONDITIONAL_INPUT', 'field_id':fid,
                'message':field['label']+' combines an amount and a status. Read them separately, then check the status in the conditions.'})
    return issues

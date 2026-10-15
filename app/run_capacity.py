"""Read-only run selection and conservative ordinary-session capacity checks."""
import config
from core.models import JTError


def select_cases(service, body, ctx, ws, domain, cases, arm, split):
    chosen = body.get('case_ids')
    if 'case_ids' in body and (not isinstance(chosen, list) or not chosen or
            any(not isinstance(value, str) or not value for value in chosen) or len(set(chosen)) != len(chosen)):
        raise JTError('INVALID_INPUT', 'Select a nonempty list of distinct case IDs.')
    if 'plan_comparison' in body and type(body['plan_comparison']) is not bool:
        raise JTError('INVALID_INPUT', 'The comparison option must be true or false.')
    baseline_id = body.get('baseline_run_id')
    if 'baseline_run_id' in body:
        if not isinstance(baseline_id, str) or not baseline_id:
            raise JTError('INVALID_INPUT', 'Select the saved test to compare.')
        baseline = service.run_view(baseline_id, ctx)
        run = baseline['run']
        if (run['workspace_id'] != ws['workspace_id'] or run['split'] != split or split != 'dev' or
                arm != 'C_JT_RULES' or run['arm'] not in ('A_SOURCE_ONLY', 'C_JT_RULES') or
                run['domain']['version'] >= domain['version'] or not baseline['metrics']['complete'] or baseline['metrics'].get('stale')):
            raise JTError('INVALID_INPUT', 'Choose a completed earlier test from this workspace.')
        if run['code_hash'] != config.CODE_HASH or run['model_settings'] != config.SETTINGS or run['mode'] != service.adapter.mode:
            raise JTError('RUN_PROTOCOL_CHANGED', 'Start a baseline with the current application before comparing new guidance.', 409)
        if chosen is not None and chosen != run['case_ids']:
            raise JTError('INVALID_INPUT', 'The comparison must use the saved baseline cases in the same order.')
        chosen = run['case_ids']
    by_id = {case['case_id']: case for case in cases}
    if chosen is not None:
        if not set(chosen).issubset(by_id):
            raise JTError('INVALID_INPUT', 'Case selection is outside this split.')
        return [by_id[value] for value in chosen]
    if ctx['admin']:
        return cases
    selected = [case for stratum in ('normal', 'transfer', 'must_hold')
                for case in [next((c for c in cases if c['stratum'] == stratum), None)] if case]
    return selected or cases[:3]


def plan(service, body, ctx, inputs):
    ws, domain, cases, arm, split, repeats = inputs
    # execute() always ends a default-action hold. Any other nonterminal action
    # can use the full existing eight-step case cap; don't assume one call/case.
    steps = 8 if any(not action['terminal'] and action['action_id'] != domain['default_action_id']
                     for action in domain['actions']) else 1
    attempts = config.SETTINGS['attempts']
    pair = body.get('plan_comparison', False)
    if pair and (body.get('baseline_run_id') or split != 'dev' or repeats != 1):
        raise JTError('INVALID_INPUT', 'Plan a comparison from a single development baseline.')
    decisions = len(cases) * repeats * steps * attempts * (2 if pair else 1)
    # propose_question can use two attempts; draft_rules has one attempt.
    required = {'judgment_calls': decisions, 'model_calls': decisions + (3 if pair else 0)}
    limited = service.adapter.mode == 'LIVE' and not ctx['admin']
    remaining = service.adapter.budget.public_allowance(ctx['owner']) if limited else None
    can_start = not limited or all(required[key] <= remaining[key] for key in required)
    unit = steps * attempts * (2 if pair else 1)
    max_cases = max(0, min(40, remaining['judgment_calls'] // unit,
                          (remaining['model_calls'] - (3 if pair else 0)) // unit)) if limited else None
    scope = 'this comparison' if pair else 'this test'
    message = ('Select up to '+str(max_cases)+' cases for '+scope+'.' if max_cases else
               'The remaining allowance is too small for '+scope+'. Ask the application owner to review the test allowance.') if not can_start else ''
    return {'selected_case_ids': [case['case_id'] for case in cases], 'limited': limited,
            'comparison_planned': pair, 'max_cases': max_cases, 'max_steps_per_case': steps, 'attempts_per_step': attempts,
            'required': required, 'remaining': remaining, 'can_start': can_start, 'message': message,
            'basis': 'Current approved conditions. Allowance is checked again when each AI call starts.'}

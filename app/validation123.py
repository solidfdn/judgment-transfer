"""One owner-bound allowance for the newly authorized document validation."""
import config
from core.models import JTError, digest
from history import actor
from service import now

def authorize(service, body, ctx):
    if not ctx['admin']: raise JTError('ADMIN_REQUIRED', 'Only the owner can authorize additional validation.', 403)
    person = actor(body)
    if body.get('max_cost_usd') != 100 or config.MAX_COST != 100:
        raise JTError('INVALID_INPUT', 'This reviewed allowance requires the authorized cumulative USD 100 ceiling.')
    key, session_key = ('budget','validation123'), ('budget',digest(ctx['owner'])[:40])
    def commit(values):
        old = values[key]
        if old:
            if old['owner'] != ctx['owner']: raise JTError('FORBIDDEN', 'The validation allowance belongs to its original owner.', 403)
            if body.get('demo_revision') == 'USD_134' and not old.get('usd_demo_134'):
                # One explicit new-data allowance, never a counter reset or a
                # second recovery of the historical experiment.
                old['additional_calls'] += 24
                old['additional_decisions'] += 20
                old['retry_limit'] += 10
                old['usd_demo_134'] = {**person, 'authorized_at': now(),
                    'additional_calls': 24, 'additional_decisions': 20,
                    'purpose': 'New fictional USD demo: ten case decisions and one question/guidance pair, including bounded retries.'}
                values[key] = old
            return old
        session = values[session_key] or {'calls':0,'decisions':0}
        grant = {'owner':ctx['owner'], **person, 'authorized_at':now(), 'authorized':True,
                 'purpose':'Requirements review, document intake and bounded before/after validation',
                 'base_calls':session['calls'],'base_decisions':session['decisions'],
                 'additional_calls':40,'additional_decisions':24,'retry_limit':4,'retry_used':0,
                 'max_cost_usd':100}
        values[key] = grant
        return grant
    return service.repo.atomic([key,session_key],commit)

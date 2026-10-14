"""One explicitly authorized, bounded study; no model or business-policy shortcuts.

All labels remain in the scorer. Existing approvals are reused with provenance,
not newly granted. No original workspace, freeze, run or budget is reset.
"""
import copy
import datetime as dt
import hashlib
import json
import time
import config
from core.models import ROOT, JTError, digest, validate_case, validate_domain
from service import ARMS, now

STUDY = 'priority112'
KEY = ('studies', STUDY)
GRANT = ('budget', 'recovery111')
LIMIT = 235
PILOT_LATENCY_MS = 20000
PREVIOUS_KEY = ('studies', 'priority111')
PREVIOUS_HASH = '41e6f19d7d404318d093cfbc63fbec64bcd079189fa4d580542a8e06a259daaa'


class Recovery:
    def __init__(self, service):
        self.s = service
        self.repo = service.repo

    def admin(self, ctx):
        if not ctx['admin']:
            raise JTError('ADMIN_REQUIRED', 'This study requires administrator access.', 403)

    def load(self, ctx):
        self.admin(ctx)
        study = self.repo.get(*KEY)
        if not study or study['owner'] != ctx['owner']:
            raise JTError('NOT_FOUND', 'Study not found.', 404)
        if study['code_hash'] != config.CODE_HASH or study['settings'] != config.SETTINGS:
            raise JTError('RUN_PROTOCOL_CHANGED', 'Study protocol changed; saved evidence remains readable.', 409)
        return study

    def status(self, ctx):
        self.admin(ctx)
        study = self.repo.get(*KEY)
        if study and study['owner'] != ctx['owner']:
            raise JTError('FORBIDDEN', 'This grant belongs to another administrator.', 403)
        session = self.repo.get('budget', digest(ctx['owner'])[:40]) or {'decisions': 0, 'calls': 0}
        budget = self.repo.get('budget', 'global') or {'spent_usd': 0}
        grant = self.repo.get(*GRANT)
        return {'study': {k: v for k, v in study.items() if k != 'owner'} if study else None,
                'budget': budget, 'session': session, 'max_cost_usd': config.MAX_COST,
                'additional_decisions_used': session['decisions'] - grant['base_decisions'] if grant else 0,
                'additional_decisions_limit': grant['limit'] if grant else 234, 'request_tier': config.REQUEST_TIER}

    def previous_evidence(self, ctx, originals):
        """Reuse only the two verified, unaffected development checks. Never
        relabel the lost third response as successful or alter its ledger entry.
        All snapshots are rechecked in the preparation transaction.
        """
        old = self.repo.get(*PREVIOUS_KEY)
        if not old or old['owner'] != ctx['owner'] or old['code_hash'] != PREVIOUS_HASH or old['settings'] != config.SETTINGS or old['original_workspaces'] != originals or old['phase'] != 'PILOT' or old['cursor'] != 2 or (old.get('stop') or {}).get('reason') != 'MODEL_FAILED':
            raise JTError('RECOVERY_STATE_MISMATCH', 'Expected the recorded 1.0.11 third-call failure; no evidence was changed.', 409)
        schedule = old['schedules'].get('PILOT', [])
        if len(schedule) != 18 or any(not label.startswith('PILOT-') for label in old['runs']):
            raise JTError('RECOVERY_STATE_MISMATCH', 'The old study has unexpected execution history.', 409)
        snapshots = {PREVIOUS_KEY: old}; carried = []
        for i, item in enumerate(schedule):
            task = self.repo.get('tasks', item['task_id'])
            snapshots[('tasks', item['task_id'])] = task
            run = self.repo.get('runs', item['run_id'])
            snapshots[('runs', item['run_id'])] = run
            if not task or not run or task['run_id'] != run['run_id'] or task['task_id'] not in run['task_ids'] or run.get('code_hash') != PREVIOUS_HASH or run.get('mode') != 'LIVE':
                raise JTError('RECOVERY_STATE_MISMATCH', 'Previous task membership cannot be verified.', 409)
            if i < 2:
                if task['status'] != 'COMPLETED' or task['arm'] != 'A_SOURCE_ONLY' or self.problem({'tasks': [task]}, True):
                    raise JTError('RECOVERY_STATE_MISMATCH', 'Previously passed check no longer verifies.', 409)
                case = self.s.case(task['workspace_id'], task['case_id'])
                if case['stratum'] != 'normal':
                    raise JTError('RECOVERY_STATE_MISMATCH', 'Only the two completed normal A checks may be reused.', 409)
                trace = self.repo.get('traces', task['trace_ids'][0])
                snapshots[('traces', trace['trace_id'])] = trace
                carried.append({**item, 'trace_id': trace['trace_id'], 'case_id': task['case_id'],
                                'arm': task['arm'], 'code_hash': PREVIOUS_HASH,
                                'reason': 'Unchanged Priority-success path; development verification only, not formal evidence.'})
            elif i == 2:
                if task['status'] != 'FAILED' or task.get('receipt_ids') or len(task['trace_ids']) != 1:
                    raise JTError('RECOVERY_STATE_MISMATCH', 'Expected exactly one unexecuted failed response.', 409)
                trace = self.repo.get('traces', task['trace_ids'][0]); attempts = trace.get('attempts', [])
                snapshots[('traces', trace['trace_id'])] = trace
                if len(attempts) != 1 or any(attempts[0].get(k) != v for k, v in {
                    'stage': 'validate_response', 'status': 'FAILED', 'error_type': 'ValueError',
                    'provider_code': '0', 'traffic_type': 'ON_DEMAND', 'requested_tier': 'priority'}.items()) or 'result' in trace:
                    raise JTError('RECOVERY_STATE_MISMATCH', 'The failure is not the reviewed traffic-validation defect.', 409)
                failed = {**item, 'trace_id': trace['trace_id'], 'recorded_cost_usd': attempts[0]['cost_usd'],
                          'historical_cost_policy': 'Original conservative charge retained; no refund or history rewrite.'}
            elif task['status'] != 'PENDING' or task['attempts'] or task['step_index'] or task['trace_ids']:
                raise JTError('RECOVERY_STATE_MISMATCH', 'Unexpected further calls; no automatic restart.', 409)
        return snapshots, carried, failed

    def prepare(self, body, ctx):
        self.admin(ctx)
        if config.REQUEST_TIER != 'priority' or self.s.adapter.mode != 'LIVE':
            raise JTError('MODE_MISMATCH', 'This recovery requires the reviewed LIVE Priority configuration.', 409)
        existing = self.repo.get(*KEY)
        if existing:
            self.load(ctx)
            if existing['original_workspaces'] != body.get('workspaces'):
                raise JTError('IDEMPOTENCY_CONFLICT', 'This one-time study already uses other workspaces.', 409)
            return self.status(ctx)
        if body.get('authorize_one_replacement') is not True:
            raise JTError('AUTHORIZATION_REQUIRED', 'One failed-call replacement requires explicit approval: 234 to 235 total additional decisions, USD 20 unchanged.', 403)
        originals = body.get('workspaces')
        fixtures = json.loads((ROOT/'fixtures/recovery111.json').read_text())
        if not isinstance(originals, dict) or set(originals) != set(fixtures['domains']):
            raise JTError('INVALID_INPUT', 'Supply the two existing benchmark workspaces.')
        expected_original, carried, failed = self.previous_evidence(ctx, originals)
        if expected_original[PREVIOUS_KEY]['fixture_hash'] != digest(fixtures):
            raise JTError('RECOVERY_STATE_MISMATCH', 'The predeclared holdout fixtures changed.', 409)
        writes = {}; workspaces = {}
        for name, old_id in originals.items():
            old = self.s.workspace(old_id, ctx)
            if not old['frozen'] or old['status'] != 'READY' or old['version'] != 1 or old['approved_count'] != 1 or old['sample'] != name:
                raise JTError('NOT_READY', 'The original approved, frozen version 1 is required.', 409)
            new_id = 'ws_' + digest([STUDY, ctx['owner'], old_id])[:32]
            workspaces[name] = new_id
            original_key = ('workspaces', old_id); expected_original[original_key] = old
            source_hashes = {}
            for source in self.s.sources(old, True):
                if hashlib.sha256(self.s.blobs.get(source['blob_id'])).hexdigest() != source['version_hash']:
                    raise JTError('INVALID_EVIDENCE', 'Original source bytes no longer match their approved hash.')
                sid = source['source_id']; source_hashes[sid] = source['version_hash']
                expected_original[('sources', old_id+'-'+sid)] = source
                writes[('sources', new_id+'-'+sid)] = {**source, 'workspace_id': new_id}
            if source_hashes != old['freeze']['source_hashes']:
                raise JTError('INVALID_EVIDENCE', 'Original frozen sources changed.')
            for version in (0, 1):
                record = self.repo.get('domains', old_id+'-v'+str(version))
                validate_domain(record['domain'], lambda ref: self.s.source_check(old_id, ref))
                if any(not r['approved_by'] for r in record['domain']['rules']):
                    raise JTError('NOT_READY', 'Unapproved rules cannot be copied.')
                expected_original[('domains', old_id+'-v'+str(version))] = record
                writes[('domains', new_id+'-v'+str(version))] = copy.deepcopy(record)
            if digest(self.s.domain(old)) != old['freeze']['domain_hash']:
                raise JTError('INVALID_EVIDENCE', 'The frozen approved domain changed.')
            teachings = []
            for tid in old['teaching_ids']:
                record = self.repo.get('teachings', tid)
                expected_original[('teachings', tid)] = record
                if record['teaching']['approval_state'] != 'APPROVED':
                    continue
                new_tid = 'teaching_' + digest([STUDY, tid])[:32]
                cloned = copy.deepcopy(record); cloned['workspace_id'] = new_id
                cloned['teaching']['teaching_id'] = new_tid
                cloned['original_teaching_id'] = tid
                writes[('teachings', new_tid)] = cloned; teachings.append(new_tid)
            if len(teachings) != old['approved_count']:
                raise JTError('NOT_READY', 'Approval provenance is incomplete.')
            cases = []; labels = []
            for cid in old['case_ids']:
                case = self.s.case(old_id, cid)
                if case['split'] == 'dev':
                    label = self.repo.get('expected', old_id+'-'+cid)
                    expected_original[('cases', old_id+'-'+cid)] = case
                    expected_original[('expected', old_id+'-'+cid)] = label
                    cases.append(case); labels.append(label)
            cases += fixtures['domains'][name]['cases']; labels += fixtures['domains'][name]['labels']
            if len(cases) != 20 or len({c['case_id'] for c in cases}) != 20:
                raise JTError('INVALID_INPUT', 'Study requires eight development and twelve new sample records per domain.')
            for case, label in zip(cases, labels):
                validate_case(case, self.s.domain(old))
                if not label or label['case_id'] != case['case_id']:
                    raise JTError('LABELS_REQUIRED', 'Fixed labels are missing.')
                writes[('cases', new_id+'-'+case['case_id'])] = case
                writes[('expected', new_id+'-'+case['case_id'])] = label
            new = copy.deepcopy(old)
            new.update(workspace_id=new_id, created_at=now(), run_ids=[], question_ids=[], teaching_ids=teachings,
                       leases={}, case_ids=[c['case_id'] for c in cases], recovery_study=STUDY,
                       approval_reused_from={'workspace_id': old_id, 'freeze': old['freeze'],
                                             'domain_hash': old['freeze']['domain_hash']})
            new.pop('draft_id', None)
            new['freeze'] = {'frozen_at': now(), 'dataset_hash': digest(cases), 'label_hash': digest(labels),
                             'version': 1, 'domain_hash': old['freeze']['domain_hash'],
                             'source_hashes': source_hashes, 'model_settings': config.SETTINGS,
                             'code_hash': config.CODE_HASH, 'study': STUDY,
                             'dataset_description': fixtures['description']}
            writes[('workspaces', new_id)] = new
        study = {'owner': ctx['owner'], 'study_id': STUDY, 'created_at': now(), 'phase': 'PILOT',
                 'code_hash': config.CODE_HASH, 'settings': config.SETTINGS, 'workspaces': workspaces,
                 'original_workspaces': originals, 'runs': {}, 'pilot_passed': False, 'stop': None,
                 'cursor': 0, 'schedules': {},
                 'previous_study': 'priority111', 'reused_development_checks': carried,
                 'preserved_failed_development_check': failed,
                 'development_gate': {'required_checks': 18, 'reused_passed_checks': 2, 'new_checks': 16,
                                      'max_latency_ms': PILOT_LATENCY_MS},
                 'traffic_policy': 'Request Priority for every arm; accept documented ON_DEMAND downgrade with actual-tier pricing and disclosure.',
                 'fixture_hash': digest(fixtures), 'description': fixtures['description']}
        session_key = ('budget', digest(ctx['owner'])[:40]); global_key = ('budget', 'global')
        def commit(values):
            if values[KEY]:
                if values[KEY]['owner'] != ctx['owner'] or values[KEY]['original_workspaces'] != originals:
                    raise JTError('IDEMPOTENCY_CONFLICT', 'Study already prepared differently.', 409)
                return
            grant = values[GRANT]
            if not grant or grant['owner'] != ctx['owner'] or grant['limit'] != 234 or grant.get('replacement112'):
                raise JTError('GRANT_ALREADY_USED', 'Only the original unamended grant can receive one explicit replacement.', 409)
            for key, snapshot in expected_original.items():
                if values[key] != snapshot:
                    raise JTError('VERSION_CONFLICT', 'The original evidence changed during preparation.', 409)
            session = values[session_key] or {'decisions': 0, 'calls': 0}
            budget = values[global_key] or {'spent_usd': 0}
            if session['decisions'] - grant['base_decisions'] != 3:
                raise JTError('RECOVERY_STATE_MISMATCH', 'The original grant must have exactly the three reviewed decisions.', 409)
            remaining = LIMIT - 3
            if session['calls'] + remaining > 500:
                raise JTError('CALL_LIMIT', 'The unchanged 500-call session cap cannot fit this study.', 429)
            if budget['spent_usd'] + 0.20 > config.MAX_COST:
                raise JTError('COST_LIMIT', 'Insufficient budget for even the first bounded verification.', 429)
            if budget.get('day') == dt.datetime.now(dt.timezone.utc).date().isoformat() and budget.get('decisions', 0)+remaining > 600:
                raise JTError('CALL_LIMIT', 'The unchanged daily judgment cap cannot fit this study today.', 429)
            for key, value in writes.items():
                if values[key] is not None:
                    raise JTError('IDEMPOTENCY_CONFLICT', 'Study target already exists without its manifest.', 409)
                values[key] = value
            values[GRANT] = {**grant, 'limit': LIMIT, 'replacement112': {
                'authorized': True, 'authorized_at': now(), 'original_limit': 234, 'amended_limit': LIMIT,
                'reason': 'Explicit administrator approval for exactly one replacement of the 1.0.11 traffic-validation defect; cumulative USD 20 unchanged.'}}
            values[KEY] = study
        self.repo.atomic([KEY, GRANT, session_key, global_key]+list(expected_original)+list(writes), commit)
        return self.status(ctx)

    def stop(self, reason):
        def latch(values):
            values[KEY]['stop'] = values[KEY]['stop'] or {'reason': reason, 'at': now()}
        self.repo.atomic([KEY], latch)

    def run_for(self, study, name, arm, phase, ctx):
        label = phase+'-'+name+'-'+arm
        if label in study['runs']:
            return study['runs'][label]
        wid = study['workspaces'][name]
        body = {'workspace_id': wid, 'arm': arm, 'split': 'dev' if phase == 'PILOT' else 'holdout',
                'repeats': 1 if phase == 'PILOT' else 3}
        if phase == 'PILOT':
            ws = self.s.workspace(wid, ctx)
            cases = [self.s.case(wid, cid) for cid in ws['case_ids']]
            kinds = ('transfer', 'must_hold') if arm == 'A_SOURCE_ONLY' else ('normal', 'transfer', 'must_hold')
            body['case_ids'] = [next(c['case_id'] for c in cases if c['split'] == 'dev' and c['stratum'] == kind) for kind in kinds]
        internal = {**ctx, '_recovery111': True, 'operation': 'r112-'+label}
        result = self.s.create_run(body, internal)
        rid = result.get('run_id') or result['run']['run_id']
        def save(values): values[KEY]['runs'][label] = rid
        self.repo.atomic([KEY], save); study['runs'][label] = rid
        return rid

    def problem(self, view, pilot):
        for task in view['tasks']:
            if task['status'] in ('FAILED', 'CANCELLED'):
                return task.get('error', {}).get('code', task['status'])
            if task['status'] == 'LEASED' and task['lease_until'] <= time.time():
                return 'INTERRUPTED_CALL_NOT_RETRIED'
            if task['status'] != 'COMPLETED': continue
            if task.get('score', {}).get('critical_error'):
                return 'CRITICAL_ERROR'
            if len(task['trace_ids']) != 1 or len(task['receipt_ids']) != 1:
                return 'UNEXPECTED_DECISION_COUNT'
            trace = self.repo.get('traces', task['trace_ids'][0])
            attempts = trace.get('attempts', [])
            if trace.get('mode') != 'LIVE' or len(attempts) != 1 or attempts[0].get('status') != 'OK' or attempts[0].get('requested_tier') != 'priority' or attempts[0].get('traffic_type') not in ('ON_DEMAND_PRIORITY', 'ON_DEMAND'):
                return 'REQUEST_OR_RESPONSE_TIER_NOT_VERIFIED'
            if pilot:
                if trace.get('elapsed_ms', 10**9) > PILOT_LATENCY_MS:
                    return 'PILOT_LATENCY_OVER_20_SECONDS'
                case = self.s.case(task['workspace_id'], task['case_id'])
                if task['arm'] == 'A_SOURCE_ONLY' and case['stratum'] == 'transfer':
                    if task['decision']['outcome'] != 'HOLD': return 'A_MISSING_AUTHORITY_NOT_HELD'
                elif not task.get('score', {}).get('correct'):
                    return 'PILOT_INCORRECT_DECISION'
                if task['arm'] == 'B_TEXT_ADDED' and case['stratum'] == 'transfer':
                    ws = self.repo.get('workspaces', task['workspace_id'])
                    if not any(ref['source_id'] in ws['human_source_ids'] for ref in task['decision']['source_refs']):
                        return 'B_HUMAN_EVIDENCE_NOT_CITED'
        return None

    def advance(self, ctx, request_key=None):
        """At most one generation per HTTP request; all gates are server-side."""
        study = self.load(ctx)
        if study['stop'] or study['phase'] == 'COMPLETE': return self.status(ctx)
        # A duplicate/lost HTTP response must not turn the old cursor key into a
        # new judgment. The task itself also has a fixed receipt/idempotency key.
        expected_key = 'recovery112-'+study['phase']+'-'+str(study['cursor'])
        if request_key is not None and request_key != expected_key:
            return self.status(ctx)
        phase = study['phase']
        schedule = study['schedules'].get(phase)
        if schedule is None:
            runs = []
            for arm in ARMS:
                for name in sorted(study['workspaces']):
                    rid = self.run_for(study, name, arm, phase, ctx)
                    runs.append(self.repo.get('runs', rid))
            schedule = [{'run_id': r['run_id'], 'task_id': r['task_ids'][i]} for i in range(3 if phase == 'PILOT' else 36) for r in runs if i < len(r['task_ids'])]
            def save_schedule(values): values[KEY]['schedules'][phase] = schedule
            self.repo.atomic([KEY], save_schedule)
        cursor = study['cursor']
        if cursor == len(schedule):
            forecast = None
            if phase == 'PILOT':
                attempts = []
                for item in schedule + study['reused_development_checks']:
                    task = self.repo.get('tasks', item['task_id'])
                    trace = self.repo.get('traces', task['trace_ids'][0])
                    attempts.append(trace['attempts'][0])
                # Conservative forecast, not permission to exceed the ledger.
                # Use the largest pilot usage cost, not the cheapest successful call.
                projected = max(a['cost_usd'] for a in attempts)*216 + max(a.get('reserved_usd', .20) for a in attempts)
                budget = self.repo.get('budget', 'global') or {'spent_usd': 0}
                forecast = {'method': 'largest_pilot_usage_cost_times_216_plus_one_reservation',
                            'projected_usd': projected, 'remaining_ledger_usd': config.MAX_COST-budget['spent_usd'],
                            'guarantee': False}
                def save_forecast(values): values[KEY]['formal_cost_forecast'] = forecast
                self.repo.atomic([KEY], save_forecast)
                if projected > forecast['remaining_ledger_usd']:
                    self.stop('FORMAL_COST_FORECAST_EXCEEDS_REMAINING_BUDGET')
                    return self.status(ctx)
            def transition(values):
                if values[KEY]['phase'] != phase or values[KEY]['cursor'] != cursor: return
                values[KEY]['phase'] = 'FORMAL' if phase == 'PILOT' else 'COMPLETE'
                if phase == 'PILOT':
                    values[KEY]['pilot_passed'] = True
                    values[KEY]['cursor'] = 0
            self.repo.atomic([KEY], transition)
            return self.status(ctx)
        item = schedule[cursor]; task = self.repo.get('tasks', item['task_id'])
        problem = self.problem({'tasks': [task]}, phase == 'PILOT')
        if problem:
            self.stop(problem); return self.status(ctx)
        if task['status'] == 'LEASED':
            raise JTError('BUSY', 'A saved request is still running. No duplicate was dispatched.', 409, True)
        if task['status'] == 'PENDING':
            if task['attempts'] or task['step_index']:
                self.stop('UNEXPECTED_NONTERMINAL_DECISION'); return self.status(ctx)
            internal = {**ctx, '_recovery111': True, '_recovery_task': task['task_id'], 'operation': 'r112-step-'+task['task_id']}
            self.s.step(item['run_id'], internal)
            task = self.repo.get('tasks', item['task_id'])
        problem = self.problem({'tasks': [task]}, phase == 'PILOT')
        if problem or task['status'] != 'COMPLETED':
            self.stop(problem or 'UNEXPECTED_NONTERMINAL_DECISION')
        else:
            def advance_cursor(values):
                current = values[KEY]
                if current['phase'] == phase and current['cursor'] == cursor and not current['stop']:
                    current['cursor'] += 1
                    current['last_task'] = {'run_id': item['run_id'], 'case_id': task['case_id'], 'arm': task['arm'],
                                            'phase': phase, 'completed': cursor+1, 'total': len(schedule)}
            self.repo.atomic([KEY], advance_cursor)
        return self.status(ctx)

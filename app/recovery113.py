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

STUDY = 'bounded113'
KEY = ('studies', STUDY)
GRANT = ('budget', 'recovery111')
LIMIT = 242
PILOT_LATENCY_MS = 20000
PREVIOUS_KEY = ('studies', 'priority112')
PREVIOUS_HASH = 'd3cb2e62b96dd52cd52f6f158973793a11daf271a0202d3a846776a08345fd80'
EARLIER_HASH = '41e6f19d7d404318d093cfbc63fbec64bcd079189fa4d580542a8e06a259daaa'


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
                'extra_retry_attempts': {'limit': 6, 'used': (grant or {}).get('recovery113', {}).get('retry_used', 0)},
                'additional_decisions_limit': grant['limit'] if grant else 234, 'request_tier': config.REQUEST_TIER}

    def previous_evidence(self, ctx, originals):
        """Reuse six single-attempt checks below nine seconds. Validate and
        retain both failed calls and all prior protocols without rewriting them.
        """
        old = self.repo.get(*PREVIOUS_KEY)
        if not old or old['owner'] != ctx['owner'] or old['code_hash'] != PREVIOUS_HASH or old['original_workspaces'] != originals or old['phase'] != 'PILOT' or old['cursor'] != 4 or (old.get('stop') or {}).get('reason') != 'MODEL_FAILED':
            raise JTError('RECOVERY_STATE_MISMATCH', 'Expected the recorded 1.0.12 fifth-call timeout.', 409)
        unchanged = ('model', 'location', 'thinking_level', 'temperature', 'max_output_tokens', 'request_tier')
        if any(old['settings'].get(k) != config.SETTINGS[k] for k in unchanged) or old['settings'].get('attempts') != 1:
            raise JTError('RECOVERY_STATE_MISMATCH', 'Previous model protocol is not the reviewed configuration.', 409)
        schedule = old['schedules'].get('PILOT', [])
        if len(schedule) != 16 or any(not label.startswith('PILOT-') for label in old['runs']):
            raise JTError('RECOVERY_STATE_MISMATCH', 'The old study has unexpected execution history.', 409)
        snapshots = {PREVIOUS_KEY: old}; carried = []
        def reuse(item, expected_hash):
            task = self.repo.get('tasks', item['task_id']); run = self.repo.get('runs', item['run_id'])
            if not task or not run or run['code_hash'] != expected_hash or run['mode'] != 'LIVE' or task['task_id'] not in run['task_ids'] or task['run_id'] != run['run_id'] or task['status'] != 'COMPLETED' or self.problem({'tasks': [task]}, True):
                raise JTError('RECOVERY_STATE_MISMATCH', 'A reused development check cannot be verified.', 409)
            trace = self.repo.get('traces', task['trace_ids'][0])
            if len(trace['attempts']) != 1 or trace['elapsed_ms'] > 9000:
                raise JTError('RECOVERY_STATE_MISMATCH', 'Only fast, unaffected single-attempt checks may be reused.', 409)
            ws = self.s.workspace(task['workspace_id'], ctx)
            snapshots[('workspaces', ws['workspace_id'])] = ws
            snapshots[('tasks', task['task_id'])] = task
            snapshots[('runs', run['run_id'])] = run
            snapshots[('traces', trace['trace_id'])] = trace
            carried.append({'run_id': run['run_id'], 'task_id': task['task_id'], 'trace_id': trace['trace_id'],
                            'case_id': task['case_id'], 'sample': ws['sample'], 'arm': task['arm'],
                            'code_hash': expected_hash, 'reason': 'Unchanged fast first-attempt decision path; development checks only.'})
        if len(old.get('reused_development_checks', [])) != 2:
            raise JTError('RECOVERY_STATE_MISMATCH', 'The original two development checks are missing.', 409)
        for item in old['reused_development_checks']: reuse(item, EARLIER_HASH)
        for i, item in enumerate(schedule):
            task = self.repo.get('tasks', item['task_id'])
            snapshots[('tasks', item['task_id'])] = task
            run = self.repo.get('runs', item['run_id'])
            snapshots[('runs', item['run_id'])] = run
            if not task or not run or task['run_id'] != run['run_id'] or task['task_id'] not in run['task_ids'] or run.get('code_hash') != PREVIOUS_HASH or run.get('mode') != 'LIVE':
                raise JTError('RECOVERY_STATE_MISMATCH', 'Previous task membership cannot be verified.', 409)
            if i < 4:
                reuse(item, PREVIOUS_HASH)
            elif i == 4:
                if task['status'] != 'FAILED' or task.get('receipt_ids') or len(task['trace_ids']) != 1:
                    raise JTError('RECOVERY_STATE_MISMATCH', 'Expected exactly one unexecuted failed response.', 409)
                trace = self.repo.get('traces', task['trace_ids'][0]); attempts = trace.get('attempts', [])
                snapshots[('traces', trace['trace_id'])] = trace
                if len(attempts) != 1 or any(attempts[0].get(k) != v for k, v in {
                    'stage': 'generate_content', 'status': 'FAILED', 'error_type': 'ServerError',
                    'provider_code': '504'}.items()) or 'result' in trace:
                    raise JTError('RECOVERY_STATE_MISMATCH', 'The failure is not the reviewed provider timeout.', 409)
                failed = {**item, 'trace_id': trace['trace_id'], 'recorded_cost_usd': attempts[0]['cost_usd'],
                          'case_id': task['case_id'], 'arm': task['arm'],
                          'sample': self.s.workspace(task['workspace_id'], ctx)['sample'],
                          'historical_cost_policy': 'Original conservative charge retained; no refund or history rewrite.'}
            elif task['status'] != 'PENDING' or task['attempts'] or task['step_index'] or task['trace_ids']:
                raise JTError('RECOVERY_STATE_MISMATCH', 'Unexpected further calls; no automatic restart.', 409)
        if len({(x['sample'], x['arm'], x['case_id']) for x in carried}) != 6:
            raise JTError('RECOVERY_STATE_MISMATCH', 'Reused development checks overlap.', 409)
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
        if body.get('authorize_bounded_recovery') is not True:
            raise JTError('AUTHORIZATION_REQUIRED', 'Explicit opt-in is required for the bounded retry policy and 242 total additional generation attempts; USD 20 and 500 session calls unchanged.', 403)
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
                 'previous_study': 'priority112', 'reused_development_checks': carried,
                 'earlier_failed_development_check': expected_original[PREVIOUS_KEY]['preserved_failed_development_check'],
                 'preserved_failed_development_check': failed,
                 'development_gate': {'required_checks': 18, 'reused_passed_checks': 6, 'new_checks': 12,
                                      'max_latency_ms': PILOT_LATENCY_MS},
                 'reliability_policy': {'generation_attempts_per_decision_max': 2, 'total_model_seconds': 20,
                                        'generation_seconds': 9, 'backoff_seconds': 1,
                                        'extra_retry_attempts_total_max': 6, 'consecutive_formal_failures_stop': 3},
                 'consecutive_technical_failures': 0,
                 'traffic_policy': 'Request Priority for every arm; accept documented ON_DEMAND downgrade with actual-tier pricing and disclosure.',
                 'fixture_hash': digest(fixtures), 'description': fixtures['description']}
        session_key = ('budget', digest(ctx['owner'])[:40]); global_key = ('budget', 'global')
        def commit(values):
            if values[KEY]:
                if values[KEY]['owner'] != ctx['owner'] or values[KEY]['original_workspaces'] != originals:
                    raise JTError('IDEMPOTENCY_CONFLICT', 'Study already prepared differently.', 409)
                return
            grant = values[GRANT]
            if not grant or grant['owner'] != ctx['owner'] or grant['limit'] != 235 or not grant.get('replacement112', {}).get('authorized') or grant.get('recovery113'):
                raise JTError('GRANT_ALREADY_USED', 'Only the recorded 235-attempt grant can receive this one-time amendment.', 409)
            for key, snapshot in expected_original.items():
                if values[key] != snapshot:
                    raise JTError('VERSION_CONFLICT', 'The original evidence changed during preparation.', 409)
            session = values[session_key] or {'decisions': 0, 'calls': 0}
            budget = values[global_key] or {'spent_usd': 0}
            if session['decisions'] - grant['base_decisions'] != 8:
                raise JTError('RECOVERY_STATE_MISMATCH', 'The original grant must have exactly the eight reviewed attempts.', 409)
            remaining = LIMIT - 8
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
            values[GRANT] = {**grant, 'limit': LIMIT, 'recovery113': {
                'authorized': True, 'authorized_at': now(), 'previous_limit': 235, 'amended_limit': LIMIT,
                'retry_limit': 6, 'retry_used': 0,
                'reason': 'Explicit opt-in for 228 remaining decisions plus at most six extra transient retries; original grant baseline and USD 20 unchanged.'}}
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
            done = {x['case_id'] for x in study['reused_development_checks'] if x['sample'] == name and x['arm'] == arm}
            body['case_ids'] = [next(c['case_id'] for c in cases if c['split'] == 'dev' and c['stratum'] == kind) for kind in ('normal', 'transfer', 'must_hold')]
            body['case_ids'] = [cid for cid in body['case_ids'] if cid not in done]
        internal = {**ctx, '_recovery111': True, 'operation': 'r113-'+label}
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
            if trace.get('mode') != 'LIVE' or not 1 <= len(attempts) <= 2 or attempts[-1].get('status') != 'OK' or attempts[-1].get('requested_tier') != 'priority' or attempts[-1].get('traffic_type') not in ('ON_DEMAND_PRIORITY', 'ON_DEMAND') or any(not self.transient(a) for a in attempts[:-1]):
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

    @staticmethod
    def transient(attempt):
        return attempt.get('status') == 'FAILED' and (
            attempt.get('provider_code') in ('429', '500', '502', '503', '504') or
            attempt.get('error_type') in ('ReadTimeout', 'ConnectTimeout', 'WriteTimeout', 'PoolTimeout',
                                           'ConnectError', 'ReadError', 'WriteError', 'CloseError', 'RemoteProtocolError'))

    def technical_failure(self, task):
        if task['status'] != 'FAILED' or task.get('error', {}).get('code') != 'MODEL_FAILED' or len(task.get('trace_ids', [])) != 1:
            return False
        trace = self.repo.get('traces', task['trace_ids'][0])
        return bool(trace and trace.get('mode') == 'LIVE' and 1 <= len(trace.get('attempts', [])) <= 2 and all(self.transient(a) for a in trace['attempts']))

    def advance(self, ctx, request_key=None):
        """One logical decision, at most two bounded generations per request."""
        study = self.load(ctx)
        if study['stop'] or study['phase'] == 'COMPLETE': return self.status(ctx)
        # A duplicate/lost HTTP response must not turn the old cursor key into a
        # new judgment. The task itself also has a fixed receipt/idempotency key.
        expected_key = 'recovery113-'+study['phase']+'-'+str(study['cursor'])
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
            if phase == 'PILOT':
                failed = study['preserved_failed_development_check']
                def previous_failure_first(item):
                    task = self.repo.get('tasks', item['task_id'])
                    return 0 if task['case_id'] == failed['case_id'] and task['arm'] == failed['arm'] else 1
                schedule.sort(key=previous_failure_first)
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
                    attempts.append(trace['attempts'][-1])
                # Conservative forecast, not permission to exceed the ledger.
                # Use the largest pilot usage cost, not the cheapest successful call.
                grant = self.repo.get(*GRANT)
                retry_remaining = 6 - grant['recovery113']['retry_used']
                projected = max(a['cost_usd'] for a in attempts)*216 + (retry_remaining + 1)*max(a.get('reserved_usd', .20) for a in attempts)
                budget = self.repo.get('budget', 'global') or {'spent_usd': 0}
                forecast = {'method': 'largest_successful_attempt_cost_times_216_plus_remaining_retry_reservations_plus_one',
                            'remaining_extra_retry_attempts': retry_remaining,
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
        if problem and not (phase == 'FORMAL' and self.technical_failure(task)):
            self.stop(problem); return self.status(ctx)
        if task['status'] == 'LEASED':
            raise JTError('BUSY', 'A saved request is still running. No duplicate was dispatched.', 409, True)
        if task['status'] == 'PENDING':
            if task['attempts'] or task['step_index']:
                self.stop('UNEXPECTED_NONTERMINAL_DECISION'); return self.status(ctx)
            internal = {**ctx, '_recovery111': True, '_recovery_task': task['task_id'], 'operation': 'r113-step-'+task['task_id']}
            self.s.step(item['run_id'], internal)
            task = self.repo.get('tasks', item['task_id'])
        problem = self.problem({'tasks': [task]}, phase == 'PILOT')
        technical = phase == 'FORMAL' and self.technical_failure(task)
        if (problem or task['status'] != 'COMPLETED') and not technical:
            self.stop(problem or 'UNEXPECTED_NONTERMINAL_DECISION')
        else:
            def advance_cursor(values):
                current = values[KEY]
                if current['phase'] == phase and current['cursor'] == cursor and not current['stop']:
                    current['cursor'] += 1
                    current['consecutive_technical_failures'] = current.get('consecutive_technical_failures', 0)+1 if technical else 0
                    if current['consecutive_technical_failures'] >= 3:
                        current['stop'] = {'reason': 'THREE_CONSECUTIVE_TECHNICAL_FAILURES', 'at': now()}
                    current['last_task'] = {'run_id': item['run_id'], 'case_id': task['case_id'], 'arm': task['arm'],
                                            'phase': phase, 'completed': cursor+1, 'total': len(schedule),
                                            'status': task['status']}
            self.repo.atomic([KEY], advance_cursor)
        return self.status(ctx)

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

STUDY = 'watchdog115'
KEY = ('studies', STUDY)
GRANT = ('budget', 'recovery111')
LIMIT = 251
PILOT_LATENCY_MS = 20000
PREVIOUS_KEY = ('studies', 'streamed114')
PREVIOUS_HASH = '091ba6680828800b26c63f1ba8d4f4bb27dfd0278787cbb4a621c588eb811a2a'
PROBE_KEY = ('diagnostics', 'provider113-pair-v1')


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
                'additional_decisions_limit': grant['limit'] if grant else 234,
                'session_call_limit': 509 if (grant or {}).get('streamed114', {}).get('authorized') else 500,
                'request_tier': config.REQUEST_TIER}

    def previous_evidence(self, ctx, originals):
        old = self.repo.get(*PREVIOUS_KEY)
        if not old or old['owner'] != ctx['owner'] or old['code_hash'] != PREVIOUS_HASH or old['original_workspaces'] != originals or old['phase'] != 'PILOT' or old['cursor'] != 3 or (old.get('stop') or {}).get('reason') != 'MODEL_FAILED':
            raise JTError('RECOVERY_STATE_MISMATCH', 'Expected the preserved 1.0.14 fourth-case stop.', 409)
        expected_settings = {k:v for k,v in config.SETTINGS.items() if k != 'first_text_timeout_seconds'}
        expected_settings['retry_policy'] = 'one_transient_retry_in_remaining_window'
        if old['settings'] != expected_settings:
            raise JTError('RUN_PROTOCOL_CHANGED', 'The previous protocol differs beyond the reviewed watchdog fix.', 409)
        schedule = old['schedules'].get('PILOT', [])
        if len(schedule) != 18 or len(old['runs']) != 6 or any(not label.startswith('PILOT-') for label in old['runs']):
            raise JTError('RECOVERY_STATE_MISMATCH', 'Unexpected prior execution history.', 409)
        snapshots = {PREVIOUS_KEY: old}; carried = []; failed = None
        for i, item in enumerate(schedule):
            task = self.repo.get('tasks', item['task_id']); run = self.repo.get('runs', item['run_id'])
            if not task or not run or task['run_id'] != run['run_id'] or task['task_id'] not in run['task_ids'] or run.get('code_hash') != PREVIOUS_HASH or run.get('mode') != 'LIVE':
                raise JTError('RECOVERY_STATE_MISMATCH', 'Prior task membership is invalid.', 409)
            snapshots[('tasks', item['task_id'])] = task
            snapshots[('runs', item['run_id'])] = run
            if i <= 3:
                if len(task.get('trace_ids', [])) != 1:
                    raise JTError('RECOVERY_STATE_MISMATCH', 'Expected exactly one preserved trace.', 409)
                tid = task['trace_ids'][0]; trace = self.repo.get('traces', tid)
                snapshots[('traces', tid)] = trace
                attempts = trace.get('attempts', [])
                record = {**item, 'trace_id': tid, 'case_id': task['case_id'], 'arm': task['arm'],
                          'sample': self.s.workspace(task['workspace_id'], ctx)['sample'],
                          'code_hash': PREVIOUS_HASH, 'recorded_cost_usd': sum(a.get('cost_usd',0) for a in attempts)}
                if i < 3:
                    if task['status'] != 'COMPLETED' or self.problem({'tasks':[task]}, True) or len(attempts) != 1 or not isinstance(attempts[0].get('first_text_ms'), (int,float)) or attempts[0]['first_text_ms'] >= 10000 or trace['elapsed_ms'] >= 10000:
                        raise JTError('RECOVERY_STATE_MISMATCH', 'A carried success is not unaffected by the new watchdog.', 409)
                    carried.append(record)
                else:
                    if task['status'] != 'FAILED' or task.get('receipt_ids') or task['arm'] != 'B_TEXT_ADDED' or task['case_id'] != 'invoice_routing_dev_01' or 'result' in trace or len(attempts) != 1:
                        raise JTError('RECOVERY_STATE_MISMATCH', 'Expected the single uncommitted failed B check.', 409)
                    a = attempts[0]
                    if a.get('error_type') != 'ReadTimeout' or a.get('stage') != 'generate_content' or a.get('chunk_count') != 0 or a.get('first_text_ms') is not None or a.get('local_total_deadline_reached') is not True:
                        raise JTError('RECOVERY_STATE_MISMATCH', 'Failure differs from the reviewed zero-text deadline.', 409)
                    failed = record
            elif task['status'] != 'PENDING' or task['attempts'] or task['step_index'] or task['trace_ids']:
                raise JTError('RECOVERY_STATE_MISMATCH', 'Unexpected later execution; no reset.', 409)
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
                 'previous_study': 'streamed114', 'reused_development_checks': carried,
                 'historical_development_runs': sorted(set(expected_original[PREVIOUS_KEY]['runs'].values()) | set(expected_original[PREVIOUS_KEY]['historical_development_runs'])),
                 'diagnostic_evidence': expected_original[PREVIOUS_KEY]['diagnostic_evidence'],
                 'earlier_failed_development_check': expected_original[PREVIOUS_KEY]['preserved_failed_development_check'],
                 'preserved_failed_development_check': failed,
                 'development_gate': {'required_checks': 18, 'reused_passed_checks': 3, 'new_checks': 15,
                                      'max_latency_ms': PILOT_LATENCY_MS},
                 'reliability_policy': {'generation_attempts_per_decision_max': 2, 'total_model_seconds': 20,
                                        'generation_seconds': 20, 'first_text_seconds': 10, 'backoff_seconds': 1,
                                        'extra_retry_attempts_total_max': 6, 'extra_retries_already_used': 1, 'remaining_extra_retries': 4, 'preserved_failure_replacement_uses_retry_slot': True, 'consecutive_formal_failures_stop': 3},
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
            if not grant or grant['owner'] != ctx['owner'] or grant['limit'] != 251 or not grant.get('streamed114', {}).get('authorized') or grant.get('recovery113', {}).get('retry_used') != 1 or grant.get('recovery115'):
                raise JTError('RECOVERY_STATE_MISMATCH', 'Expected the unchanged authorized grant with one retry used.', 409)
            for key, snapshot in expected_original.items():
                if values[key] != snapshot:
                    raise JTError('VERSION_CONFLICT', 'The original evidence changed during preparation.', 409)
            session = values[session_key] or {'decisions': 0, 'calls': 0}
            budget = values[global_key] or {'spent_usd': 0}
            if session['decisions'] - grant['base_decisions'] != 16 or session['calls'] != 274:
                raise JTError('RECOVERY_STATE_MISMATCH', 'The original grant must have exactly the sixteen reviewed attempts.', 409)
            remaining = LIMIT - 16
            if session['calls'] + remaining > 509:
                raise JTError('CALL_LIMIT', 'The explicitly authorized 509-call session cap cannot fit this study.', 429)
            if budget['spent_usd'] + 0.20 > config.MAX_COST:
                raise JTError('COST_LIMIT', 'Insufficient budget for even the first bounded verification.', 429)
            if budget.get('day') == dt.datetime.now(dt.timezone.utc).date().isoformat() and budget.get('decisions', 0)+remaining > 600:
                raise JTError('CALL_LIMIT', 'The unchanged daily judgment cap cannot fit this study today.', 429)
            for key, value in writes.items():
                if values[key] is not None:
                    raise JTError('IDEMPOTENCY_CONFLICT', 'Study target already exists without its manifest.', 409)
                values[key] = value
            values[GRANT] = {**grant, 'recovery115': {
                'prepared_at': now(), 'pending_replacement': True, 'replacement_charged': False,
                'decision_key': digest([failed['case_id'], failed['arm']]),
                'replaces_trace': failed['trace_id'],
                'reason': 'One replacement consumes an existing retry slot on reservation. No limit, baseline, prior cost or result is reset.'}}
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
        internal = {**ctx, '_recovery111': True, 'operation': 'r115-'+label}
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
            if attempts[-1].get('transport') != 'streamGenerateContent' or attempts[-1].get('complete_stream') is not True or attempts[-1].get('finish_reason') != 'STOP' or trace.get('settings', {}).get('decision_schema_location') != 'api_only':
                return 'STREAM_PROTOCOL_NOT_VERIFIED'
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
        expected_key = 'recovery115-'+study['phase']+'-'+str(study['cursor'])
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
            internal = {**ctx, '_recovery111': True, '_recovery_task': task['task_id'], 'operation': 'r115-step-'+task['task_id']}
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

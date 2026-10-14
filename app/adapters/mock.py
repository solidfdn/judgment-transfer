"""Synthetic adapter. Outputs are always labelled MOCK, never used as LIVE evidence."""
import copy
import json
import time
import uuid
from core.models import ROOT, JTError, digest, permitted

class MockAdapter:
    mode = 'MOCK'
    def __init__(self, repo, blobs): self.repo, self.blobs = repo, blobs
    def out(self, purpose, value, payload):
        trace = {'trace_id':'trace_'+uuid.uuid4().hex, 'mode':'MOCK', 'purpose':purpose, 'prompt_hash':digest(payload),
                 'payload':payload, 'settings':{'model':'MOCK'}, 'attempts':[], 'elapsed_ms':0, 'result':value}
        self.repo.put('traces', trace['trace_id'], trace)
        return value, trace
    def extract(self, sources, owner, admin, fields=None):
        return self.out('extract', {'observations':[]}, {'sources':[s['source_id'] for s in sources], 'note':'MOCK does not read media.'})
    def draft_domain(self, goal, domain_id, version, sources, observations, owner, admin):
        path = ROOT/'fixtures'/domain_id/'domain_v0.json'
        if not path.exists(): raise JTError('MOCK_CUSTOM_WORKFLOW', 'For custom material, enter a workflow in Advanced or use the deployed LIVE app.')
        domain = json.loads(path.read_text()); domain['version']=version
        for rule in domain['rules']: rule['approved_by']=None
        return self.out('draft_domain', domain, {'domain_id':domain_id})
    def decide(self, domain, case, state, arm, human_text, sources, owner, admin):
        # B is a simulation, not a measured language-model baseline.
        action, rules, why = permitted(domain, {**case['facts'], **state})
        value = {'case_id':case['case_id'], 'outcome':'HOLD' if action==domain['default_action_id'] else 'PROPOSE',
                 'action_id':action, 'rule_ids':rules, 'source_refs':[], 'missing_fields':[k for k,v in case['facts'].items() if v is None],
                 'explanation':'MOCK: '+why}
        return self.out('decide', value, {'case':case, 'arm':arm})
    def propose_question(self, domain, failures, sources, owner, admin):
        value = {'question_id':'question_'+uuid.uuid4().hex, 'text':'What verified conditions permit completion of these held cases, and when must they stay on hold?',
                 'affected_dev_case_ids':[f['case_id'] for f in failures], 'missing_field_ids':[], 'source_refs':[],
                 'why_needed':'These development cases are unresolved by the approved source workflow.'}
        return self.out('propose_question', value, {'development_cases':failures})
    def draft_rules(self, domain, question, human_text, human_source, owner, admin):
        path = ROOT/'fixtures'/domain['domain_id']/'teaching_response_mock.json'
        if not path.exists(): raise JTError('MOCK_CUSTOM_WORKFLOW', 'Use LIVE to derive rules from custom answers.')
        fixture = json.loads(path.read_text())
        if human_text.strip() != fixture['human_text'].strip(): raise JTError('MOCK_ANSWER', 'MOCK only simulates the provided example answer. Use LIVE for your own answer.')
        rules = copy.deepcopy(fixture['proposed_rules'])
        for r in rules:
            r['approved_by']=None
            r['source_refs']=[{'source_id':human_source['source_id'],'version_hash':human_source['version_hash'],'locator':'human:1','quote':human_text}]
        return self.out('draft_rules', {'rules':rules}, {'human_text':human_text})

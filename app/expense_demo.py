"""Publish only the exact fictional USD scenario after validating owned results."""
import json
from pathlib import Path
from comparison import compare
from core.models import JTError, digest
from history import actor
from service import now

FIXTURE=Path(__file__).parent/'fixtures/expense_review_usd'


def recorded_decision_matches(view, task, case, target):
    traces={t['trace_id']:t for t in view.get('traces',[])}
    ids=task.get('trace_ids',[])
    if not ids:return False
    if task.get('decision_origin')=='APPROVED_RULE':
        from approved_stop import decision
        expected=decision(view['run']['domain'],case,case['initial_state'],view['run']['arm'])
        return (expected is not None and expected['action_id']==target and len(ids)==1 and
            task.get('raw_decision')==expected and task.get('decision')==expected and
            ids[0] in traces and traces[ids[0]].get('mode')=='RULE_ENGINE' and
            traces[ids[0]].get('purpose')=='approved_rule_hold' and traces[ids[0]].get('attempts')==[] and
            traces[ids[0]].get('settings')=={'engine':'three_valued_approved_rules','code_hash':view['run']['code_hash']} and
            traces[ids[0]].get('source_hashes')==view['run']['domain']['source_hashes'] and
            traces[ids[0]].get('result')==expected)
    return task.get('decision_origin','MODEL')=='MODEL' and all(
        tid in traces and traces[tid].get('mode')=='LIVE' and traces[tid].get('purpose')=='decide' and
        traces[tid].get('settings')==view['run']['model_settings'] and bool(traces[tid].get('attempts')) and
        traces[tid]['attempts'][-1].get('status')=='OK' and traces[tid].get('result',{}).get('action_id')==target for tid in ids)


def publish(service, body, ctx):
    if not ctx['admin'] or body.get('publish_fictional_usd_demo') is not True:
        raise JTError('ADMIN_REQUIRED','Explicit owner approval is required to publish fictional results.',403)
    person=actor(body)
    cases=json.loads((FIXTURE/'cases.json').read_text())
    labels=json.loads((FIXTURE/'expected_private_to_scorer.json').read_text())
    targets=[v['expected_action_id'] for v in labels]
    views={k:service.run_view(body.get(k+'_run_id',''),ctx,True) for k in ('baseline','after','holdout')}
    a,b,h=[views[k] for k in ('baseline','after','holdout')]
    wid=a['run']['workspace_id'];ws=service.workspace(wid,ctx)
    if (service.adapter.mode!='LIVE' or any(v['run']['mode']!='LIVE' for v in views.values()) or
        not compare(service,a['run']['run_id'],b['run']['run_id'],ctx)['comparable'] or
        not ws.get('frozen') or ws.get('version')!=1 or ws.get('approved_count')!=1 or
        len(ws.get('teaching_ids',[]))!=1 or len(ws.get('run_ids',[]))!=3 or
        {v['run']['workspace_id'] for v in views.values()}!={wid} or
        {v['run']['code_hash'] for v in views.values()}!={a['run']['code_hash']} or
        h['run']['model_settings']!=a['run']['model_settings'] or h['run']['split']!='holdout' or
        h['run']['domain_hash']!=b['run']['domain_hash'] or h['run']['created_at']<ws['freeze']['frozen_at']):
        raise JTError('DEMO_RESULT_MISMATCH','The USD comparison and first-use records do not match.',409)
    for kind, selected, expected in [('baseline',cases[:4],['ready_for_approval','hold_case','hold_case','hold_case']),('after',cases[:4],targets[:4]),('holdout',cases[4:],targets[4:])]:
        view=views[kind]
        if (not view['metrics']['complete'] or view['metrics']['stale'] or
            view['run']['dataset_hash']!=digest(selected) or view['run']['case_ids']!=[c['case_id'] for c in selected] or
            len(view['tasks'])!=len(selected)):
            raise JTError('DEMO_RESULT_MISMATCH','The exact six USD cases are required.',409)
        for task, case, target in zip(view['tasks'],selected,expected):
            receipts=[r for r in view['receipts'] if r['task_id']==task['task_id']]
            live_trace=recorded_decision_matches(view,task,case,target)
            effects={e['field_id']:e['value'] for action in view['run']['domain']['actions'] if action['action_id']==target for e in action['effects']}
            if (task['case_id']!=case['case_id'] or task['status']!='COMPLETED' or
                task['decision']['action_id']!=target or task.get('raw_decision',{}).get('action_id')!=target or
                task['state']!=effects or len(receipts)!=1 or receipts[0]['case_hash']!=digest(case) or
                receipts[0]['before_state']!=case['initial_state'] or not task.get('trace_ids') or not live_trace):
                raise JTError('DEMO_RESULT_MISMATCH','A raw decision, executed state or receipt does not match.',409)
    policy=(FIXTURE/'source_sop.txt').read_text()
    if a['run']['domain']['source_hashes']!={'expense_sop':digest(policy.encode())}:
        raise JTError('DEMO_RESULT_MISMATCH','The USD policy version differs.',409)
    teaching=service.owned('teachings',ws['teaching_ids'][0],ctx)['teaching']
    expected_text=(FIXTURE/'expert_teaching_reference.txt').read_text().splitlines()[2:]
    if teaching['human_text']!='\n'.join(expected_text) or teaching['approval_state']!='APPROVED':
        raise JTError('DEMO_RESULT_MISMATCH','The approved explanation differs.',409)
    question=service.owned('questions',teaching['question_id'],ctx)['question']
    titles=['Personal receipt','Company-addressed receipt','Employee payment missing','Stay extended','New company receipt','Claim exceeds employee payment']
    notes=['The original instructions already covered this receipt.','The owner’s explanation defines when a company-addressed receipt is acceptable.','A paid hotel total does not prove how much the employee paid.','An extra night still needs a manager’s decision.','The new guidance worked on a case excluded from the explanation.','The USD 424.00 claim exceeds the employee-paid amount of USD 264.00 by USD 160.00.']
    rows=[]
    for i,c in enumerate(cases):
        f=c['facts'];task=(b if i<4 else h)['tasks'][i if i<4 else i-4]
        facts={new:f[old] for old,new in [('claimant_name','claimant_name'),('receipt_guest_name','guest_name'),('approved_stay_start','approved_start_date'),('approved_stay_end','approved_end_date'),('receipt_stay_start','actual_start_date'),('receipt_stay_end','actual_end_date'),('receipt_addressee_name','receipt_addressed_to'),('claimed_amount_usd','claimed_amount'),('employee_payment_amount_usd','receipt_employee_paid_amount'),('employee_payment_status','receipt_payment_status')]}
        rows.append({'id':c['case_id'],'split':c['split'],'title':titles[i],'facts':facts,
            'before':a['tasks'][i]['decision']['action_id'] if i<4 else None,'after':task['decision']['action_id'],
            'trace_id':task['trace_ids'][-1],'run_id':(b if i<4 else h)['run']['run_id'],
            'decision_origin':task.get('decision_origin','MODEL'),
            'explanation':task['decision']['explanation'],'note':notes[i]})
    traces={t['trace_id']:t for v in (b,h) for t in v.get('traces',[])}
    data={'demo_version':'1.0.35','currency':'USD','kind':'RECORDED_LIVE_EXECUTION','recorded_at':now(),
        'reviewer_name':person['reviewer_name'],'source':policy,'source_id':'expense_sop','source_hash':digest(policy.encode()),
        'human_text':teaching['human_text'],'human_hash':digest(teaching['human_text'].encode()),
        'question':question['text'],'question_id':question['question_id'],'approval_version':1,'cases':rows,
        **{k+'_run_id':v['run']['run_id'] for k,v in views.items()},
        'baseline_code_hash':a['run']['code_hash'],'after_code_hash':b['run']['code_hash'],
        'model_calls':sum(len(t.get('attempts',[])) for t in traces.values()),
        'incremental_cost_usd':sum(x.get('cost_usd',0) for t in traces.values() for x in t.get('attempts',[])),
        'scope':'Fictional USD expense-document precheck. Four matched cases and two first-use cases. A person gives final business approval.',
        'protocol_note':'Same application, model settings, cases and starting states before and after. Explicit approved stop conditions run before Gemini; their traces identify the rule engine and contain no model attempts. Workflow conditions and case facts were explicitly reviewed; case facts are author-provided document transcriptions.'}
    key=('public_demo','expense_usd134')
    def commit(values):
        if values[key] and values[key]!=data:
            # Retrieval timestamps and cost summaries must not create a new demo.
            prior=values[key]
            if all(prior[k]==data[k] for k in ('baseline_run_id','after_run_id','holdout_run_id','cases','source_hash','human_hash')):
                return prior
            raise JTError('VERSION_CONFLICT','An approved USD demo is already published.',409)
        values[key]=data
        return data
    return service.repo.atomic([key],commit)

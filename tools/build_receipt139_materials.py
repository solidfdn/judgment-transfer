#!/usr/bin/env python3
"""Author a separate USD receipt-acceptance scenario; never rewrite old fixtures."""
import base64, copy, importlib.util, io, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCENARIO='PERSONAL_RECEIPT_139'

def build():
    spec=importlib.util.spec_from_file_location('expense_material_base',ROOT/'tools/build_expense_demo_materials.py')
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    base.FIXTURE=ROOT/'app/fixtures/expense_review_usd139';base.DOMAIN_ID='expense_review_usd139'
    base.POLICY_LINES[0]='Cedarline Services | Accommodation reimbursement precheck | Initial procedure, receipt revision 139'
    base.POLICY_LINES[6]='For a receipt addressed to Cedarline Services, use the explicitly stated employee-paid amount marked PAID. Compare the claim with that amount, not with a total that includes another payer.'
    base.POLICY_LINES[9]='The acceptance conditions for a receipt addressed to the employee rather than Cedarline Services are not recorded here. Ask the expense task owner before treating an employee-addressed receipt as accepted evidence.'
    base.POLICY_LINES.append('Currency: USD. All amounts in this fictional workflow are US dollars; no currency conversion is performed.')
    base.TEACHING_LINES[0]='DRAFT FOR TASK-OWNER REVIEW | Employee-addressed hotel receipts'
    base.TEACHING_LINES[2]='A receipt addressed to the employee rather than Cedarline Services is acceptable under this company policy when its addressee and named guest both match the claimant, the employee-paid amount is explicitly stated, that employee payment is marked PAID, and both stay dates match the approved dates.'
    base.TEACHING_LINES[3]='Once this receipt-acceptance condition is approved, apply the existing payment checks: compare the claimed amount directly with the stated employee-paid amount, not the total lodging charge. A known mismatch is returned for correction.'
    names=['Alex Morgan','Sam Rivera','Jordan Chen','Taylor Brooks','Casey Lee','Jamie Patel']
    for index,(record,name) in enumerate(zip(base.RECORDS,names)):
        record.update(name=name,recipient=base.COMPANY if index in (0,3) else name,claim=record['claim'].replace('EXP-','USD-'))
        for key in ('amount','total','company_paid','employee_paid'):
            if record[key] is not None:record[key]/=100
    base.RECORDS[1].update(total=348,company_paid=0,note='My receipt is addressed to me and explicitly records my paid card payment of USD 348.00.')
    base.RECORDS[2].update(total=312,note='The hotel statement is addressed to me. My payment amount and its payment status are not stated.')
    base.RECORDS[4].update(total=276,company_paid=0,note='My receipt records my card payment and is addressed to me.')
    def usd(v):
        if isinstance(v,str):return v.replace('_jpy','_usd').replace('JPY','USD')
        if isinstance(v,list):return [usd(x) for x in v]
        if isinstance(v,dict):return {usd(k):usd(x) for k,x in v.items()}
        return v
    original_domains=base.make_domains
    def domains():
        d,_=original_domains();d=usd(d)
        for rule in d['rules']:
            if 'personal' in rule['rule_id']:
                rule['rule_id']=rule['rule_id'].replace('personal','company')
                rule['statement']=rule['statement'].replace('personal receipt','company-addressed receipt')
                for c in rule['when']['all']:
                    if c['field_id']=='receipt_addressee_name':c.pop('rhs_field_id',None);c['value']=base.COMPANY
        v=copy.deepcopy(d);v['version']=1
        v['source_hashes']['expense_teaching_draft']=base.sha(base.text_bytes(base.TEACHING_LINES))
        # Author-prepared reference only. Live guidance must come from a new Gemini proposal.
        for r in d['rules']:
            if 'company' not in r['rule_id']:continue
            added=copy.deepcopy(r);added['rule_id']=added['rule_id'].replace('company','personal')
            added['statement']=added['statement'].replace('company-addressed receipt','employee-addressed receipt')
            for c in added['when']['all']:
                if c['field_id']=='receipt_addressee_name':c.pop('value',None);c['rhs_field_id']='claimant_name'
            added['source_refs']=[base.source_ref('expense_sop',base.POLICY_LINES,8 if added['action_id']=='return_for_correction' else 9),base.source_ref('expense_teaching_draft',base.TEACHING_LINES,3),base.source_ref('expense_teaching_draft',base.TEACHING_LINES,4)]
            v['rules'].append(added)
        return d,v
    base.make_domains=domains
    base.display=lambda v:'Not stated' if v is None else f'{v:,.2f}' if isinstance(v,(int,float)) else str(v)
    original_documents=base.make_documents
    base.make_documents=lambda r:tuple(usd(v) for v in original_documents(r))
    rationales=[
        'Company-addressed receipt: guest, approved dates and the explicitly paid USD 268.00 employee amount match.',
        'Employee-addressed receipt: the approved acceptance condition permits the existing payment checks. The claimed and explicitly paid employee amount are both USD 348.00.',
        'The employee payment amount and status are not stated. Keep them unknown; do not infer them from the hotel total.',
        'The actual stay ends on 2026-09-20, outside the approval ending 2026-09-19. A manager must decide on the extension.',
        'A new employee-addressed receipt, excluded from teaching, explicitly records a paid USD 276.00 employee amount matching the claim, names and approved dates.',
        'The claim is USD 424.00 but the employee explicitly paid USD 264.00. Return the mismatch; the company-paid USD 160.00 is not reimbursed to the employee.'
    ]
    original_json=base.write_json
    def write_json(path,value):
        value=usd(value)
        if path.name=='expected_private_to_scorer.json':
            for i,row in enumerate(value):row['rationale']='Private author-prepared label, not a measured result. '+rationales[i]
        original_json(path,value)
    base.write_json=write_json
    result=base.build(ROOT/'output/Expense_Demo_Receipt139_Data')
    fixture_readme=base.FIXTURE/'README.txt'
    fixture_readme.write_text(fixture_readme.read_text().replace('tools/build_expense_demo_materials.py','tools/build_receipt139_materials.py')+'\nScenario: '+SCENARIO+'\nCompany-addressed receipts are the initial-policy standard. Employee-addressed acceptance is the recorded gap.\n')
    source=Path(result['output']);assets=ROOT/'app/web/samples'
    (assets/'expense_policy.txt').write_bytes((source/'policy/source_sop.txt').read_bytes())
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        def add(name,data):
            info=zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
        add('README.txt',('Judgment Transfer | fictional USD receipt example\n\nCompany-addressed receipts follow the original policy. The task owner must explain when employee-addressed receipts can be accepted.\n\nUpload policy/source_sop.txt as work instructions. Read case_inputs/dev PDFs as separate case evidence. Review the owner explanation and derived conditions before approving them. Keep case_inputs/holdout out of teaching. Final business approval remains human. No payment or message is sent.\n\nAll amounts are USD and all organizations, people and transactions are fictional. Case facts in the published comparison are author-reviewed transcriptions, not new model extraction.\n').encode())
        for folder in ('policy','case_inputs','owner_review'):
            for p in sorted((source/folder).rglob('*')):
                if p.is_file():add(p.relative_to(source).as_posix(),p.read_bytes())
    (assets/'expense_files.json').write_text(json.dumps({'filename':'Judgment_Transfer_Receipt_Example_USD.zip','mime':'application/zip','base64':base64.b64encode(buffer.getvalue()).decode()},separators=(',',':'))+'\n')
    return result
if __name__=='__main__':print(json.dumps(build(),indent=2))

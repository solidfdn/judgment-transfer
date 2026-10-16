'use strict';
// Execute the actual demo renderer with explicit old/new data and a small DOM boundary double.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..'),script=fs.readFileSync(path.join(root,'app/web/demo/demo.js'),'utf8');
const fixture=JSON.parse(fs.readFileSync(path.join(root,'app/fixtures/expense_review_usd139/cases.json')));
const data={currency:'USD',cases:fixture.map((c,i)=>({title:'Test case',facts:{claimant_name:c.facts.claimant_name,receipt_addressed_to:c.facts.receipt_addressee_name,claimed_amount:c.facts.claimed_amount_usd,receipt_employee_paid_amount:c.facts.employee_payment_amount_usd,receipt_payment_status:c.facts.employee_payment_status,approved_start_date:c.facts.approved_stay_start,approved_end_date:c.facts.approved_stay_end,actual_start_date:c.facts.receipt_stay_start,actual_end_date:c.facts.receipt_stay_end},before:i===0?'ready_for_approval':'hold_case',after:i<2?'ready_for_approval':'hold_case',note:'Test note'})),source:'Test source',question:'Test question',human_text:'Test explanation'};
const els=new Map(),get=id=>{if(!els.has(id))els.set(id,{innerHTML:'',textContent:'',disabled:false});return els.get(id);};
let download;
const ctx={window:{JT_DEMO_EVIDENCE:data,addEventListener:()=>{}},document:{getElementById:get,querySelectorAll:()=>[],createElement:()=>({click(){}})},location:{hash:''},Intl,Blob:class{constructor(parts){download=parts[0];}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},setTimeout:()=>{},fetch:()=>({then(){return this},catch(){return this},finally(){}})};
vm.createContext(ctx);vm.runInContext(script,ctx);
vm.runInContext('render()',ctx);assert(get('stage').innerHTML.includes('A receipt addressed to the company'));
data.scenario_id='PERSONAL_RECEIPT_139';vm.runInContext('render()',ctx);
assert(get('stage').innerHTML.includes('A receipt addressed to the employee'));assert(get('stage').innerHTML.includes('Sam claims $348.'));
assert(!get('stage').innerHTML.includes('hotel records both a company payment'));
vm.runInContext('step=2;render()',ctx);assert(get('stage').innerHTML.includes('existing payment checks can then apply.'));assert(get('stage').innerHTML.includes('Sam Rivera'));assert(get('stage').innerHTML.includes('$348.00'));
vm.runInContext('step=3;render()',ctx);get('checklist').onclick();assert(download.includes('employee-addressed receipt'));assert(download.includes('addressee and guest match'));assert(!download.includes('For a company-addressed receipt,'));
const report={status:'PASSED',checks:['Old records retain the old story','New scenario uses employee-addressed receipt and USD348','Guidance reuses existing payment checks','Handover checklist reflects the approved receipt conditions'],scope:'Actual renderer with explicit DOM/data doubles; no browser or cloud request.'};
fs.writeFileSync(path.join(root,'verification/receipt139_ui.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));

// Actual guided-page code with an explicit read-only USD response double.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const checks=[];const ok=(name,value)=>{assert(value,name);checks.push(name);};
const original=JSON.parse(fs.readFileSync('verification/LIVE130_COMPARISON.json','utf8'));
const usd=structuredClone(original);usd.currency='USD';usd.source_id='expense_sop';
const cases=JSON.parse(fs.readFileSync('app/fixtures/expense_review_usd/cases.json','utf8'));
usd.cases.forEach((c,i)=>{const f=cases[i].facts;c.facts.claimant_name=f.claimant_name;c.facts.guest_name=f.receipt_guest_name;c.facts.receipt_addressed_to=f.receipt_addressee_name;c.facts.claimed_amount=f.claimed_amount_usd;c.facts.receipt_employee_paid_amount=f.employee_payment_amount_usd;});
const nodes={};const requests=[];const ctx={window:{JT_DEMO_EVIDENCE:original,addEventListener(){}},location:{hash:'#2'},
 document:{getElementById:id=>nodes[id]??={innerHTML:'',textContent:'',disabled:false},querySelectorAll:()=>[]},
 fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>usd};},Intl};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('app/web/demo/demo.js','utf8'),ctx);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 ok('page reads only the fixed public result endpoint',requests.length===1&&requests[0].url==='/api/v1/demo/expense'&&!requests[0].options.method);
 ok('USD company claim displays realistic dollars with two decimal places',nodes.stage.innerHTML.includes('$348.00')&&!nodes.stage.innerHTML.includes('34,800')&&!nodes.stage.innerHTML.includes(' JPY'));
 ok('global fictional names replace the Japan-specific scenario',nodes.stage.innerHTML.includes('Sam Rivera')&&!nodes.stage.innerHTML.includes('Aya Mori'));
 vm.runInContext('caseIndex=2;render()',ctx);
 ok('missing payment evidence remains unknown in USD',nodes.stage.innerHTML.includes('Not stated')&&nodes.stage.innerHTML.includes('$312.00'));
 vm.runInContext('step=3;render()',ctx);
 ok('first-use cases retain both distinct outcomes',nodes.stage.innerHTML.includes('Casey Lee')&&nodes.stage.innerHTML.includes('Jamie Patel')&&nodes.stage.innerHTML.includes('Return for correction'));
 fs.writeFileSync('verification/usd134_ui.json',JSON.stringify({passed:checks.length,checks,new_model_calls:0,cloud_writes:0,scope:'Actual guided-page JavaScript with a local read-only response double; no live USD claims.'},null,2)+'\n');
 console.log(JSON.stringify({passed:checks.length,checks}));
})().catch(e=>{console.error(e);process.exit(1)});

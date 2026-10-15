// Actual selection/preflight UI functions with explicit DOM and API doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('app/web/app.js','utf8'),checks=[];
const nodes={},node=id=>nodes[id]??={disabled:false,textContent:'',innerHTML:'',querySelectorAll:()=>[]};
const cases=Array.from({length:40},(_,i)=>({case_id:'case'+i,stratum:['normal','transfer','must_hold'][i%3]}));
let requests=[],executions=0;
const ctx={$:node,ws:{workspace_id:'owned',domain:{},status:'READY',version:0,dev_cases:cases},beforeRun:null,afterRun:null,verifiedComparison:null,recorded:false,busy:false,selectedCaseIds:null,capacityPlan:null,capacitySequence:0,escapeText:String,caseSummary:c=>c.case_id,sessionStorage:{setItem(){}},recordPerson:()=>({reviewer_name:'Offline validation'}),tab(){},executeRun:async()=>{executions++;return {status:'completed'};},api:async(path,body)=>{requests.push({path,body});return path==='/runs'?{run_id:'new-run'}:{can_start:true,limited:true,max_cases:6,selected_case_ids:body.case_ids};}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function guidedCases('),source.indexOf('async function executeRun(')),ctx);
function ok(name,value){assert(value,name);checks.push(name);}
(async()=>{
 ok('default UI chooses three representative cases instead of all forty',JSON.stringify(ctx.selectedCases())===JSON.stringify(['case0','case1','case2']));
 ctx.selectedCaseIds=['case1','case5'];let request=ctx.runRequest('A_SOURCE_ONLY');
 ok('baseline sends explicit selected cases and pair preflight',request.plan_comparison===true&&JSON.stringify(request.case_ids)===JSON.stringify(ctx.selectedCaseIds));
 ctx.beforeRun={run:{run_id:'saved-baseline',workspace_id:'owned',case_ids:['case9','case4'],domain:{version:0}},metrics:{complete:true}};ctx.ws.version=1;
 request=ctx.runRequest('C_JT_RULES');
 ok('reopened baseline controls after cases, regardless of current checkboxes',request.baseline_run_id==='saved-baseline'&&JSON.stringify(request.case_ids)===JSON.stringify(['case9','case4']));
 ctx.capacityPlan={can_start:true};ctx.updateRunControls();
 ok('approved newer guidance enables replay for an opened completed baseline',!node('replay').disabled&&node('replay-selection').textContent.includes('same 2 cases'));
 ctx.beforeRun.metrics.complete=false;ctx.updateRunControls();ok('unfinished baseline disables replay',node('replay').disabled);ctx.beforeRun.metrics.complete=true;
 await ctx.refreshRunCapacity();
 ok('capacity feedback reports a practical case limit',node('run-capacity').textContent==='2 cases selected · Up to 6 cases fit this comparison.');
 ok('preflight uses only read-only plan endpoint',requests.every(r=>r.path==='/runs/plan'));
 requests=[];ctx.api=async(path,body)=>{requests.push({path,body});return {can_start:false,message:'Select up to 1 cases for this comparison.'};};
 try{await ctx.run('A_SOURCE_ONLY');throw Error('must fail');}catch(error){ok('known insufficient allowance stops before run creation',error.message.includes('Select up to')&&requests.length===1&&requests[0].path==='/runs/plan'&&executions===0);}
 ctx.api=async(path,body)=>{requests.push({path,body});return path==='/runs'?{run_id:'new-run'}:{can_start:true,limited:false,selected_case_ids:body.case_ids};};requests=[];
 await ctx.run('C_JT_RULES');
 ok('after execution uses identical saved baseline IDs in plan and creation',requests[0].path==='/runs/plan'&&requests[1].path==='/runs'&&requests[1].body.baseline_run_id==='saved-baseline'&&JSON.stringify(requests[1].body.case_ids)===JSON.stringify(['case9','case4'])&&executions===1);
 ctx.beforeRun=null;ctx.updateRunControls();ok('no saved baseline disables replay',node('replay').disabled);
 ctx.selectedCaseIds=[];await ctx.refreshRunCapacity();ok('empty selection disables original test with a clear action',node('baseline').disabled&&node('run-capacity').textContent==='Select at least one case.');
 const html=fs.readFileSync('app/web/index.html','utf8');
 ok('selection and allowance are visible next to the baseline action',html.indexOf('id="case-selection"')<html.indexOf('id="baseline"')&&html.includes('id="run-capacity"'));
 ok('unrequested scope and historical copy removed from entry',!html.includes('other situations remain unverified')&&!html.includes('Earlier tests remain available as historical records'));
 const report={passed:checks.length,checks,new_model_calls:0,scope:'Actual UI functions with DOM/API doubles; no browser or cloud mutation.'};fs.writeFileSync('verification/capacity132_ui.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exit(1)});

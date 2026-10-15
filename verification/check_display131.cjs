// Actual changed UI functions, executed with explicit DOM/API doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),src=fs.readFileSync('app/web/app.js','utf8'),checks=[];
const nodes={};const $=id=>nodes[id]??={hidden:false,value:'',innerHTML:'',textContent:''};
const ctx={$,beforeRun:null,afterRun:null,verifiedComparison:null,recorded:false,currentRun:null,sessionStorage:{setItem(){}},savedRuns:[],ws:{run_ids:[]},escapeText:String,bind(){},tab(){},showRun(v){ctx.shown=v;},api:async()=>{throw Error('unexpected request');}};
vm.createContext(ctx);vm.runInContext(src.slice(src.indexOf('function comparableRuns('),src.indexOf('function taskOutcome(')),ctx);
vm.runInContext(src.slice(src.indexOf('function taskOutcome('),src.indexOf('function taskEvidence(')),ctx);
const a={run:{run_id:'before',workspace_id:'same',mode:'LIVE',split:'dev',dataset_hash:'same',code_hash:'old',repeats:1,case_ids:['a'],model_settings:{model:'m'},domain:{source_hashes:{source:'sha'}}},metrics:{complete:true,stale:false}};
const b=JSON.parse(JSON.stringify(a));b.run.run_id='after';b.run.code_hash='new';b.run.source_hashes={source:'sha'};
function ok(name,value){assert(value,name);checks.push(name);}
ok('a safe baseline hold is displayed as a hold despite the later complete-policy score',ctx.taskOutcome({status:'COMPLETED',receipt_ids:['saved'],score:{labelled:true,correct:false},decision:{outcome:'HOLD',missing_fields:[]}},{}).kind==='held');
ok('different builds cannot compare without server verification',!ctx.comparableRuns(a,b));
ctx.verifiedComparison={comparable:true,before_run_id:'before',after_run_id:'after',code_review:'Reviewed teaching patch'};
ok('server verification applies only to exact selected run ids',ctx.comparableRuns(a,b)&&!ctx.comparableRuns(a,{...b,run:{...b.run,run_id:'other'}}));
vm.runInContext(src.slice(src.indexOf('async function loadSavedTests('),src.indexOf('async function ensureWorkspace(')),ctx);
const before=structuredClone(a),after=structuredClone(b),held=structuredClone(b);before.run.domain.version=0;after.run.domain.version=1;after.run.arm='C_JT_RULES';held.run.run_id='held';held.run.split='holdout';before.run.arm='C_JT_RULES';
ctx.savedRuns=[before,after,held];let calls=[];ctx.api=async path=>{calls.push(path);return {comparable:true,before_run_id:'before',after_run_id:'after',code_review:'Reviewed teaching patch'};};
(async()=>{
 await ctx.openSavedTest('after');ok('saved guided result loads earlier version via GET comparison',calls[0]==='/comparisons/before/after'&&ctx.currentRun==='after'&&ctx.beforeRun.run.run_id==='before');
 calls=[];await ctx.openSavedTest('held');ok('holdout result never shows a development comparison',calls.length===0&&ctx.beforeRun===null&&ctx.verifiedComparison===null);
 const demoCtx={window:{},document:{getElementById:()=>null},location:{hash:''}};
 vm.createContext(demoCtx);vm.runInContext(fs.readFileSync('app/web/demo/evidence.js','utf8'),demoCtx);
 const evidence=demoCtx.window.JT_DEMO_EVIDENCE;
 ok('six recorded cases retain matching result and trace identities',evidence.cases.length===6&&evidence.cases.every(c=>c.trace_id.startsWith('trace_')&&c.run_id=== (c.split==='dev'?evidence.after_run_id:evidence.holdout_run_id)));
 ok('missing employee payment stays null',evidence.cases[2].facts.receipt_employee_paid_amount===null&&evidence.cases[2].after==='hold');
 ok('holdout mismatch is a recorded return',evidence.cases[5].facts.claimed_amount-evidence.cases[5].facts.receipt_employee_paid_amount===16000&&evidence.cases[5].after==='return_for_correction');
 const demo=fs.readFileSync('app/web/demo/demo.js','utf8'),html=fs.readFileSync('app/web/demo/index.html','utf8');
 ok('English-only demo has no legacy request-routing example',!/[\u3040-\u30ff\u4e00-\u9fff]/u.test(demo+html)&&!demo.includes('affected_users'));
 ok('recorded demo never invokes a model or application mutation',!demo.includes('fetch(')&&!demo.includes('/api/'));
 ok('frozen data and distinct package hashes disclosed',evidence.protocol_note.includes('1.0.29')&&evidence.protocol_note.includes('1.0.30'));
 const demoNodes={};let download=null;const listeners={};
 const demoUI={window:{JT_DEMO_EVIDENCE:evidence,addEventListener:(name,fn)=>listeners[name]=fn},document:{getElementById:id=>demoNodes[id]??={innerHTML:'',textContent:'',disabled:false},querySelectorAll:()=>[],createElement:()=>({click(){download=this.download;}})},location:{hash:''},Blob,URL:{createObjectURL:()=> 'blob:offline',revokeObjectURL(){}},setTimeout:fn=>fn()};
 vm.createContext(demoUI);vm.runInContext(demo,demoUI);
 ok('first demo stage explains the actual payment gap',demoNodes.stage.innerHTML.includes('Who paid the hotel bill?'));
 demoNodes.next.onclick();ok('next stage opens the company receipt by default',demoNodes.stage.innerHTML.includes('Aya Mori')&&demoNodes.stage.innerHTML.includes('Precheck complete'));
 for(let i=0;i<4;i++){vm.runInContext('caseIndex='+i+';render();',demoUI);ok('development case '+i+' renders its preserved result',demoNodes.stage.innerHTML.includes(evidence.cases[i].facts.claimant_name));}
 demoNodes.next.onclick();ok('third stage renders both measured holdouts',demoNodes.stage.innerHTML.includes('Nao Ito')&&demoNodes.stage.innerHTML.includes('Yui Ono'));
 demoNodes.checklist.onclick();ok('handover checklist downloads a plain-text artifact',download==='Judgment_Transfer_Expense_Handover_Checklist.txt');
 demoNodes.next.onclick();ok('restart returns to the first stage',demoNodes.stage.innerHTML.includes('Who paid the hotel bill?'));
 demoUI.location.hash='#3';listeners.hashchange();ok('hash navigation renders the requested stage',demoNodes.stage.innerHTML.includes('two new cases'));
 const report={passed:checks.length,checks,new_model_calls:0,scope:'Actual UI functions and recorded demo evidence with DOM/API doubles; rendered acceptance follows deployment.'};fs.writeFileSync('verification/display131_ui.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1)});

// Exercise the actual history handlers with explicit DOM/API doubles.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'app/web/app.js'),'utf8');
const segment=source.slice(source.indexOf('const historyKinds='),source.indexOf("bind('fix-result'"));
const els=new Map(),handlers=new Map(),calls=[],prompts=[],notices=[],checks=[];
function el(id){if(!els.has(id))els.set(id,{value:'',innerHTML:'',textContent:''});return els.get(id);}
let rows=[1,2].map(n=>({record_id:'r'+n,kind:'requirements_review',reviewer_name:'Reviewer '+n,recorded_at:'2026-10-14T13:00:00+00:00',memo:'',snapshot:{checks:[],summary:'Review '+n},source_metadata:[]})),accept=false,failReset=false;
const context=vm.createContext({$:el,ws:{workspace_id:'work'},bind:(id,fn)=>handlers.set(id,fn),escapeText:s=>String(s??''),humanize:s=>s,notify:s=>notices.push(s),window:{confirm:s=>{prompts.push(s);return accept;}},document:{querySelectorAll:()=>[]},api:async(endpoint,body,method)=>{
 calls.push({endpoint,body,method});
 if(endpoint==='/workspaces/work/history')return {records:structuredClone(rows)};
 if(endpoint==='/history/delete'){rows=rows.filter(r=>r.record_id!==body.record_id);return {deleted_count:1};}
 if(endpoint==='/history/reset'){if(failReset)throw Error('History changed');rows=[];return {deleted_count:body.record_ids.length};}
 if(endpoint.startsWith('/history/'))return structuredClone(rows.find(r=>r.record_id===endpoint.slice(9)));
 throw Error('Unexpected endpoint '+endpoint);
}});
function ok(name,condition=true){assert(condition,name);checks.push(name);}
(async()=>{
 vm.runInContext(segment,context);await handlers.get('load-history')();
 ok('history exposes delete and reset actions', /Delete selected record/.test(el('history-list').innerHTML)&&/Reset history/.test(el('history-list').innerHTML));
 ok('opening history makes no mutation',calls.every(c=>c.method==='GET'));
 el('history-current').value='r1';el('history-previous').value='r2';await handlers.get('compare-history')();
 ok('both finalized records can be opened before deletion', /Review 1/.test(el('history-comparison').innerHTML)&&/Review 2/.test(el('history-comparison').innerHTML));
 let count=calls.length;await handlers.get('delete-history')();
 ok('cancel selected deletion makes no request',calls.length===count&&rows.length===2);
 ok('confirmation identifies selected person and time',prompts.at(-1).includes('Reviewer 1')&&prompts.at(-1).includes('2026-10-14')&&prompts.at(-1).includes('cannot be undone'));
 count=calls.length;await handlers.get('reset-history')();
 ok('cancel reset makes no request',calls.length===count&&rows.length===2);
 ok('reset confirmation names scope and count',prompts.at(-1).includes('all 2')&&prompts.at(-1).includes('this workspace')&&prompts.at(-1).includes('test results will remain'));
 accept=true;await handlers.get('delete-history')();
 const deletion=calls.find(c=>c.endpoint==='/history/delete');
 ok('OK deletes only the selected record',deletion.body.record_id==='r1'&&deletion.body.confirmed===true&&deletion.body.workspace_id==='work'&&rows.length===1);
 ok('deleted comparison cleared and history reloaded',el('history-comparison').innerHTML===''&&calls.at(-1).endpoint==='/workspaces/work/history');
 failReset=true;await assert.rejects(()=>handlers.get('reset-history')(),/History changed/);
 ok('failed reset retains remaining history',rows.length===1&&!notices.some(s=>s.includes('was reset')));
 failReset=false;await handlers.get('reset-history')();
 const reset=calls.filter(c=>c.endpoint==='/history/reset').at(-1);
 ok('OK resets only the displayed history identifiers',JSON.stringify(reset.body.record_ids)==='["r2"]'&&reset.body.confirmed===true&&reset.body.workspace_id==='work');
 ok('empty state after reset',el('history-list').textContent==='No finalized records in this workspace.'&&rows.length===0);
 ok('no model, approval, source or run mutations',calls.filter(c=>c.method!=='GET').every(c=>['/history/delete','/history/reset'].includes(c.endpoint)));
 const report={passed:true,checks,test_mode:'actual handlers with explicit DOM/API stubs',real_model_calls:0,cloud_writes:0};
 fs.writeFileSync(path.join(root,'verification/history_delete_ui_123.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:true,checks:checks.length}));
})().catch(error=>{console.error(error);process.exitCode=1;});

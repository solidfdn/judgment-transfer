'use strict';
const $=id=>document.getElementById(id);
let csrf='',admin='',ws=null,currentRun=null,beforeRun=null,afterRun=null,question=null,teaching=null,busy=false,recorded=false;
let operation=null,executingRun=false,stopRequested=false,cancelRequest=null,displayedWorkspace=null;
const escapeText=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function paintNotice(){const n=$('notice');n.textContent=operation.message+(operation.started!==null?' · '+Math.floor((Date.now()-operation.started)/1000)+'s elapsed':'');n.className=operation.error?'error':'';}
function notify(message,error=false){operation={message,error,started:busy?operation?.started??Date.now():null};paintNotice();}
function tab(name){document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==name);document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
async function api(path,data,method='POST',key=null){
 const headers={};if(admin)headers['X-JT-Admin']=admin;
 if(method!=='GET'){headers['X-CSRF-Token']=csrf;headers['Idempotency-Key']=key||crypto.randomUUID();if(!(data instanceof FormData))headers['Content-Type']='application/json';}
 const response=await fetch('/api/v1'+path,{method,headers,body:method==='GET'?undefined:data instanceof FormData?data:JSON.stringify(data||{}),credentials:'same-origin'});
 const result=await response.json();if(!response.ok||result.error){const e=result.error||{};throw new Error((e.code||response.status)+': '+(e.message||'The request stopped.')+(e.request_id?' [ '+e.request_id+' ]':''));}return result;
}
async function action(fn){
 if(busy||cancelRequest)return;busy=true;
 document.getElementById('operation-status')?.remove();
 operation={message:'Processing. Waiting for completion; do not resubmit.',error:false,started:Date.now()};paintNotice();
 const timer=setInterval(paintNotice,1000);
 const buttons=[...document.querySelectorAll('button')],disabled=buttons.map(b=>b.disabled);
 buttons.forEach(b=>b.disabled=true);document.body.setAttribute('aria-busy','true');
 try{const result=await fn();if(operation.message==='Processing. Waiting for completion; do not resubmit.')notify(result?.status&&result.status!=='completed'?'Progress saved. The run is not complete.':'Completed. See the result on this page.');return result;}
 catch(e){notify('Stopped · '+e.message,true);return {status:'failed'};}
 finally{clearInterval(timer);busy=false;operation.started=null;paintNotice();document.body.removeAttribute('aria-busy');buttons.forEach((b,i)=>b.disabled=disabled[i]);}
}
function bind(id,fn){$(id).onclick=()=>action(fn);}
async function sessionInfo(){const s=await api('/session',null,'GET');csrf=s.csrf;$('mode').textContent=s.mode+(s.admin?' · ADMIN':'');$('mode').classList.toggle('mock',s.mode==='MOCK');$('version').textContent='Package '+s.version+' · Evidence before claims';return s;}
function conditions(rule){const show=c=>`${c.field_id} ${c.operator} ${JSON.stringify(c.value)}`;return [rule.when.all.length?'ALL: '+rule.when.all.map(show).join(' · '):'',rule.when.any.length?'ANY: '+rule.when.any.map(show).join(' · '):''].filter(Boolean).join('\n');}
function renderRules(rules){return rules.map(r=>`<article class="rule"><h3>${escapeText(r.statement)}</h3><p>Action: <strong>${escapeText(r.action_id)}</strong> · Priority ${r.priority} · ${r.approved_by?'Approved':'Draft'}</p><pre>${escapeText(conditions(r))}</pre><p class="muted">${r.source_refs.map(s=>escapeText(s.source_id+' / '+s.locator+' — '+s.quote)).join('<br>')}</p></article>`).join('')||'<p>No completion rule is approved yet. Unresolved cases stay on hold.</p>';}
function renderWorkspace(){
 if(displayedWorkspace!==ws.workspace_id){resetWorkspaceView();displayedWorkspace=ws.workspace_id;}
 $('mode').textContent=ws.mode+(admin?' · ADMIN':'');$('mode').classList.toggle('mock',ws.mode==='MOCK');
 $('source-editor').hidden=false;$('workspace-label').textContent=`Workspace ${ws.workspace_id} · ${ws.status} · Version ${ws.version<0?'not approved':ws.version}`;
 $('admin-workspace').textContent=admin?'Workspace ID for the runbook: '+ws.workspace_id:'';$('goal').value=ws.goal;
 $('source-list').innerHTML=ws.sources.map(s=>`<li>${escapeText(s.name)} · ${escapeText(s.mime)} · ${(s.size/1024).toFixed(1)} KiB<br><span class="muted">${escapeText(s.source_id)} · ${escapeText(s.version_hash.slice(0,12))}</span></li>`).join('');
 $('stale').hidden=ws.status!=='STALE';const d=ws.draft&&ws.draft.base_version===ws.version?ws.draft.domain:ws.domain;
 $('approve-workflow').hidden=!(ws.draft&&ws.draft.base_version===ws.version);
 if(d){$('workflow').innerHTML=`<h3>${escapeText(d.title)}</h3><p>${escapeText(d.goal)}</p><p class="muted">${d.input_fields.length} input fields · ${d.actions.length} declared actions · Hold: ${escapeText(d.default_action_id)}</p>`+renderRules(d.rules);$('domain-json').value=JSON.stringify(d,null,2);}else{$('workflow').textContent='Add material and analyse it to propose a workflow.';$('domain-json').value='';}
 $('observations').innerHTML=(ws.draft?.observations||[]).map(o=>`<p class="muted">${escapeText(o.status)} · ${escapeText(o.field_id)} = ${escapeText(JSON.stringify(o.value))} · ${escapeText(o.source_refs.map(r=>r.locator).join(', '))}</p>`).join('');
 $('dev-cases').innerHTML='<p class="muted">'+ws.dev_cases.length+' development cases loaded. Formal holdout cases are reserved for the evaluation runner.</p>';
 question=ws.questions.at(-1)?.question||null;teaching=ws.teachings.at(-1)?.teaching||null;renderTeaching();
 sessionStorage.setItem('jt-workspace',ws.workspace_id);
}
function resetWorkspaceView(){currentRun=beforeRun=afterRun=question=teaching=null;recorded=false;stopRequested=false;displayedWorkspace=null;$('answer').value='';$('cases-json').value='';$('file').value='';$('recorded').value='';$('run-status').textContent='';$('comparison').innerHTML='';$('results-table').innerHTML='';sessionStorage.removeItem('jt-run');renderTeaching();}
function renderTeaching(){ $('question').innerHTML=question?`<h3>${escapeText(question.text)}</h3><p>${escapeText(question.why_needed)}</p><p class="muted">Development cases: ${escapeText(question.affected_dev_case_ids.join(', '))}</p>`:'<p>Run development cases, then request a targeted question.</p>';$('rules').innerHTML=teaching?renderRules(teaching.proposed_rules):'<p>Your proposed rules will appear here for review.</p>';$('approve-teaching').hidden=!teaching||teaching.approval_state!=='DRAFT';}
async function refresh(){if(ws){ws=await api('/workspaces/'+ws.workspace_id,null,'GET');renderWorkspace();}}
async function create(sample){ws=await api('/workspaces',sample?{sample}:{});currentRun=beforeRun=afterRun=null;recorded=false;renderWorkspace();tab('sources');notify(sample?'Review the source workflow before approving it. The example answer is only sent to the model after you submit it.':'Add your own sources and describe the goal.');}
bind('sample-invoice',()=>create('invoice_routing'));bind('sample-support',()=>create('support_triage'));bind('new',()=>create());
bind('upload',async()=>{if(!ws)throw Error('Create a workspace first.');const file=$('file').files[0];if(!file)throw Error('Choose a file.');const data=new FormData();data.append('workspace_id',ws.workspace_id);data.append('file',file);await api('/sources',data);await refresh();notify('Source saved. Analyse and review the workflow.');});
bind('analyse',async()=>{if(!ws)throw Error('Create a workspace first.');notify('Reading the source material…');await api('/sources/extract',{workspace_id:ws.workspace_id});notify('Source reading saved. Drafting the workflow…');await api('/domains/draft',{workspace_id:ws.workspace_id,goal:$('goal').value});await refresh();notify('Draft ready. Check the evidence and action boundaries before approval.');});
bind('save-domain',async()=>{await api('/domains/draft',{workspace_id:ws.workspace_id,domain:JSON.parse($('domain-json').value)});await refresh();notify('Edited workflow saved as a draft. Review before approving.');});
bind('approve-workflow',async()=>{await api('/domains/approve',{draft_id:ws.draft.draft_id,base_version:ws.version});await refresh();notify('Workflow approved. You can run the development cases.');});
bind('import-cases',async()=>{await api('/cases/import',{workspace_id:ws.workspace_id,cases:JSON.parse($('cases-json').value)});await refresh();notify('Cases imported.');});
bind('rollback',async()=>{await api('/domains/rollback',{workspace_id:ws.workspace_id,target_version:Number($('rollback-version').value),base_version:ws.version});await refresh();notify('Earlier rules cloned into a new approved version.');});
async function run(arm){if(!ws||ws.version<0)throw Error('Approve a workflow first.');recorded=false;const r=await api('/runs',{workspace_id:ws.workspace_id,arm,split:'dev',repeats:1,...(admin?{case_ids:guidedCases()}: {})});currentRun=r.run_id;sessionStorage.setItem('jt-run',currentRun);tab('results');return executeRun();}
function guidedCases(){return ['normal','transfer','must_hold'].flatMap(s=>ws.dev_cases.filter(c=>c.stratum===s).slice(0,1).map(c=>c.case_id));}
async function executeRun(){
 stopRequested=false;executingRun=true;$('cancel').disabled=false;
 try{
 for(let i=0;i<40;i++){
  const state=await api('/runs/'+currentRun,null,'GET');showRun(state);
  if(stopRequested){if(cancelRequest)await cancelRequest;return {status:'stopped'};}
  if(state.run.cancelled){notify('Run stopped. Saved results are retained; no new case will start.');return {status:'stopped'};}
  if(state.metrics.complete){const failed=state.metrics.counts.FAILED;notify(failed?'Run ended with failed cases. See the saved results.':'Run complete. Every applied action has a saved receipt.',Boolean(failed));return {status:failed?'failed':'completed'};}
  notify('Processing one case · '+(state.metrics.counts.COMPLETED+state.metrics.counts.FAILED+state.metrics.counts.CANCELLED)+'/'+state.metrics.total+' finished. Waiting for its saved result; you can stop new cases.');
  let step;
  try{step=await api('/runs/'+currentRun+'/step',{});}
  catch(error){try{showRun(await api('/runs/'+currentRun,null,'GET'));}catch(refreshError){error.message+=' Saved status could not be refreshed. Use Resume to retrieve it.';}throw error;}
  if(stopRequested){if(cancelRequest)await cancelRequest;showRun(await api('/runs/'+currentRun,null,'GET'));return {status:'stopped'};}
  if(step.failed){const state=await api('/runs/'+currentRun,null,'GET');showRun(state);notify((step.error?.message||'The case failed.')+' The failed case remains in the results. Use Resume to process any remaining cases.',true);return {status:'failed'};}
  if(step.done===false){notify('A case is already running. Use Resume after it finishes.');return {status:'pending'};}
 }
 notify('Progress saved. Use Resume to continue.');return {status:'pending'};
 }finally{executingRun=false;if(busy)$('cancel').disabled=true;}
}
bind('baseline',()=>run('A_SOURCE_ONLY'));bind('replay',()=>run('C_JT_RULES'));bind('resume',async()=>{if(!currentRun||recorded)throw Error('Select a saved live or mock run first.');return executeRun();});
$('cancel').onclick=async()=>{
 if(cancelRequest||busy&&!executingRun)return;
 if(!currentRun||recorded){notify('No active saved run to stop.',true);return;}
 stopRequested=true;$('cancel').disabled=true;const rid=currentRun;
 notify('Stop requested. This tab will start no further cases. An already running case may finish; waiting for server confirmation.');
 cancelRequest=(async()=>{try{const r=await api('/runs/'+rid+'/cancel',{});notify('Stop confirmed. '+r.in_flight);showRun(await api('/runs/'+rid,null,'GET'));return {status:'stopped'};}
 catch(e){notify('Automatic processing stopped in this tab, but the server stop could not be confirmed. An already running case may finish. '+e.message,true);return {status:'stopped'};}})();
 try{return await cancelRequest;}finally{cancelRequest=null;$('cancel').disabled=busy;}
};
bind('ask',async()=>{if(!currentRun||recorded)throw Error('Complete a development run first.');const q=await api('/questions',{run_id:currentRun});question=q.question;renderTeaching();notify('Answer the question, then review the proposed rules.');});
bind('example',async()=>{if(!ws?.example_answer)throw Error('No example answer is defined for custom material.');$('answer').value=ws.example_answer;notify('Example inserted. Check it before submitting.');});
bind('propose',async()=>{if(!question)throw Error('Request a question first.');notify('Converting your answer into a reviewable rule proposal…');const t=await api('/teachings',{question_id:question.question_id,human_text:$('answer').value});teaching=t.teaching;renderTeaching();notify('The proposal is a draft. It has not changed the active rules.');});
bind('approve-teaching',async()=>{await api('/teachings/'+teaching.teaching_id+'/approve',{base_version:teaching.base_domain_version});await refresh();notify('Rules approved. Replay the development cases from their original state.');});
bind('next-teach',async()=>{if(recorded)throw Error('Recorded evidence is read-only.');tab('teach');});
function percent(v){return v===null?'Unlabelled':(v*100).toFixed(1)+'%';}
function comparableRuns(a,b){
 if(!a||!b)return false;
 const fields=['workspace_id','mode','split','dataset_hash','code_hash','repeats'];
 if(fields.some(k=>a.run[k]===undefined||a.run[k]!==b.run[k]))return false;
 const original=a.run.domain?.source_hashes;
 if(!original||!b.run.source_hashes||Object.entries(original).some(([id,hash])=>b.run.source_hashes[id]!==hash))return false;
 const stable=v=>Array.isArray(v)?v.map(stable):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v;
 return ['case_ids','model_settings'].every(k=>a.run[k]!==undefined&&b.run[k]!==undefined&&JSON.stringify(stable(a.run[k]))===JSON.stringify(stable(b.run[k])))&&a.metrics.complete&&b.metrics.complete&&!a.metrics.stale&&!b.metrics.stale;
}
function taskEvidence(t,value){
 const receipts=(value.receipts||[]).filter(r=>t.receipt_ids.includes(r.receipt_id));
 const traces=(value.traces||[]).filter(r=>t.trace_ids.includes(r.trace_id));
 return '<p>'+escapeText(t.decision?.explanation||t.error?.message||'Pending')+'</p><p>Approved rules: '+escapeText(t.decision?.rule_ids?.join(', ')||'none')+'</p>'+receipts.map(r=>'<div class="receipt"><strong>Committed state change</strong><p>Before: <code>'+escapeText(JSON.stringify(r.before_state))+'</code></p><p>After: <code>'+escapeText(JSON.stringify(r.after_state))+'</code></p><p class="muted">'+escapeText(r.committed_at)+'<br>'+escapeText(r.receipt_id)+'</p></div>').join('')+(!t.receipt_ids.length?'<p>No execution receipt. No action was committed.</p>':'')+'<details><summary>Saved decision and trace details</summary><pre>'+escapeText(JSON.stringify({proposed:t.raw_decision,applied:t.decision,receipts,traces:traces.map(x=>({trace_id:x.trace_id,elapsed_ms:x.elapsed_ms,attempts:x.attempts,error:x.error}))},null,2))+'</pre></details>';
}
function showRun(value){
 const r=value.run,m=value.metrics;if(r.arm==='A_SOURCE_ONLY')beforeRun=value;if(r.arm==='C_JT_RULES')afterRun=value;
 $('run-status').textContent=`${recorded?'RECORDED · ':''}${r.mode} · ${r.arm} · ${r.run_id} · ${m.counts.COMPLETED}/${m.total} completed · ${m.counts.FAILED} failed · ${m.counts.CANCELLED} cancelled${r.cancelled?' · STOPPED (an in-flight case may still finish)':''}${m.stale?' · STALE':''}`;
 $('run-status').textContent+=` · Model ${r.model_settings?.model||'not recorded'} · Rule version ${r.domain?.version??'not recorded'} · Started ${r.created_at||'not recorded'} · Code ${r.code_hash?.slice(0,12)||'not recorded'}`;
 const comparable=comparableRuns(beforeRun,afterRun);
 const cards=[['This run',m],...(comparable?[['Before teaching',beforeRun.metrics],['After teaching',afterRun.metrics]]:[])];
 $('comparison').innerHTML=cards.map(([title,x])=>`<div class="metric">${escapeText(title)}<strong>${percent(x.correct_completion_rate)}</strong><span>Correct autonomous completion · ${x.total} attempts / ${x.unique_cases} unique cases<br>${x.holds} holds · ${x.critical_errors??'unlabelled'} critical errors · ${x.human_inputs} expert inputs</span></div>`).join('');
 if(r.mode==='MOCK')$('comparison').innerHTML+='<p class="warning">MOCK simulation. These values are not measured model performance.</p>';
 if(beforeRun&&afterRun&&!comparable)$('comparison').innerHTML+='<p class="warning">No before/after comparison: both runs must be complete and use the same cases, repeats, model settings and code, with unchanged source evidence.</p>';
 if(comparable&&(beforeRun.metrics.counts.FAILED||afterRun.metrics.counts.FAILED||beforeRun.metrics.counts.CANCELLED||afterRun.metrics.counts.CANCELLED))$('comparison').innerHTML+='<p class="warning">Technical failures remain in these rates. The difference alone does not establish a teaching benefit.</p>';
 $('results-table').innerHTML='<div class="scroll"><table><thead><tr><th>Case</th><th>Result</th><th>Applied state</th><th>Evidence</th></tr></thead><tbody>'+value.tasks.map(t=>`<tr><td>${escapeText(t.case_id)}<br><span class="muted">Repeat ${t.repeat}</span></td><td>${escapeText(t.decision?.outcome||t.status)}<br>${escapeText(t.decision?.action_id||t.error?.code||'')}</td><td><code>${escapeText(JSON.stringify(t.state))}</code></td><td><details data-task="${escapeText(t.task_id)}"><summary>Inspect trace &amp; receipt</summary>${taskEvidence(t,value)}</details></td></tr>`).join('')+'</tbody></table></div>';
 let exported=null;
 if(!value.receipts&&!recorded)$('results-table').querySelectorAll('details[data-task]').forEach(details=>{details.addEventListener('toggle',async()=>{if(!details.open||details.dataset.loaded)return;details.dataset.loaded='loading';try{exported=exported||api('/exports/'+r.run_id,null,'GET');const full=await exported;const task=full.tasks.find(t=>t.task_id===details.dataset.task);details.innerHTML='<summary>Inspect trace &amp; receipt</summary>'+taskEvidence(task,full);details.dataset.loaded='true';}catch(e){details.dataset.loaded='';exported=null;const p=document.createElement('p');p.textContent='Saved receipt could not be loaded: '+e.message;details.append(p);}});});
}
bind('download',async()=>{if(!currentRun||recorded)throw Error('Choose an active saved run.');const value=await api('/exports/'+currentRun,null,'GET');const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=currentRun+'.json';a.click();URL.revokeObjectURL(url);});
$('recorded').onchange=()=>action(async()=>{const file=$('recorded').files[0];if(!file||file.size>20*1024*1024)throw Error('Choose an evidence JSON file under 20 MiB.');const value=JSON.parse(await file.text());if(value.export_version!=='1.0'||!value.run||!value.metrics||!Array.isArray(value.tasks))throw Error('This is not a Judgment Transfer export.');recorded=true;beforeRun=afterRun=null;currentRun=null;$('mode').textContent='RECORDED · '+value.run.mode;showRun(value);notify('Read-only recording opened. No model call was made.');});
bind('admin-login',async()=>{admin=$('admin-token').value;$('admin-token').value='';await sessionInfo();ws=null;resetWorkspaceView();$('source-editor').hidden=true;$('workspace-label').textContent='';$('admin-workspace').textContent='';sessionStorage.removeItem('jt-workspace');notify('Administrator access enabled for this tab. Create or reopen an evaluation workspace.');});
bind('open-workspace',async()=>{const id=$('open-workspace-id').value.trim();if(!/^ws_[a-f0-9]{32}$/.test(id))throw Error('Enter the saved Workspace ID.');ws=await api('/workspaces/'+id,null,'GET');recorded=false;renderWorkspace();currentRun=ws.run_ids.at(-1)||null;if(currentRun){sessionStorage.setItem('jt-run',currentRun);showRun(await api('/runs/'+currentRun,null,'GET'));}tab('sources');notify('Saved workspace opened. Completed actions are preserved.');});
bind('freeze',async()=>{if(!ws||!admin)throw Error('Administrator access and an approved teaching workspace are required.');await api('/workspaces/freeze',{workspace_id:ws.workspace_id});await refresh();notify('Cases, labels and approved rules frozen. Copy this workspace ID into step 07.');});
(async()=>{try{await sessionInfo();const id=sessionStorage.getItem('jt-workspace'),savedRun=sessionStorage.getItem('jt-run');if(id){ws=await api('/workspaces/'+id,null,'GET');renderWorkspace();if(savedRun&&ws.run_ids.includes(savedRun)){currentRun=savedRun;sessionStorage.setItem('jt-run',savedRun);showRun(await api('/runs/'+currentRun,null,'GET'));}}}catch(e){notify(e.message,true);sessionStorage.removeItem('jt-workspace');sessionStorage.removeItem('jt-run');}})();

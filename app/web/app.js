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
async function sessionInfo(){const s=await api('/session',null,'GET');csrf=s.csrf;$('mode').textContent=s.mode+(s.admin?' · ADMIN':'');$('mode').classList.toggle('mock',s.mode==='MOCK');$('version').textContent='Package '+s.version;return s;}
function humanize(value){const text=String(value??'').replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();return /^[A-Z\d ]+$/.test(text)?text.charAt(0)+text.slice(1).toLowerCase():text.charAt(0).toUpperCase()+text.slice(1);}
function fieldLabel(domain,id){return [...(domain?.input_fields||[]),...(domain?.state_fields||[])].find(f=>f.field_id===id)?.label||humanize(id);}
function displayValue(value){if(value===null||value===undefined)return 'Not supplied';if(typeof value==='boolean')return value?'Yes':'No';if(Array.isArray(value))return value.map(displayValue).join(', ');return String(value);}
function stateValue(value){return typeof value==='string'&&/^[A-Z][A-Z0-9_]*$/.test(value)?humanize(value):displayValue(value);}
function actionDescription(domain,id){const action=domain?.actions?.find(a=>a.action_id===id);return action?.effects?.length?action.effects.map(e=>`${humanize(fieldLabel(domain,e.field_id))}: ${stateValue(e.value)}`).join(' · '):humanize(action?.label||id||'No action');}
function stateDescription(state,domain){return Object.entries(state||{}).map(([id,value])=>`${humanize(fieldLabel(domain,id))}: ${stateValue(value)}`).join(' · ')||'No saved state';}
function conditions(rule,domain){
 const operators={eq:'is',ne:'is not',gt:'is more than',gte:'is at least',lt:'is less than',lte:'is at most',in:'is one of'};
 const show=c=>`${humanize(fieldLabel(domain,c.field_id))} ${c.operator==='exists'?'must be supplied':(operators[c.operator]||c.operator)+' '+displayValue(c.value)}`;
 return [rule.when.all.length?'All of these must be true:\n'+rule.when.all.map(c=>'• '+show(c)).join('\n'):'',rule.when.any.length?(rule.when.all.length?'At least one of these must also be true:\n':'At least one of these must be true:\n')+rule.when.any.map(c=>'• '+show(c)).join('\n'):''].filter(Boolean).join('\n\n');
}
function ruleSources(rule){return (rule.source_refs||[]).map(ref=>`<blockquote>${escapeText(ref.quote)}</blockquote>`).join('')||'<p>No supporting quotation was recorded.</p>';}
function renderRules(rules,domain=ws?.domain){return rules.map(r=>`<article class="rule"><div class="rule-heading"><h3>${escapeText(r.statement)}</h3><span class="guide-status">${r.approved_by?'Approved':'Draft — review needed'}</span></div><div class="rule-conditions">${escapeText(conditions(r,domain))}</div><p class="rule-action"><strong>Then:</strong> ${escapeText(actionDescription(domain,r.action_id))}</p><details><summary>Why this guidance is here</summary>${ruleSources(r)}<p class="muted">When more than one rule matches, the recorded priority determines which applies. This rule has priority ${escapeText(r.priority)}.</p><details><summary>Original rule and source references</summary><pre>${escapeText(JSON.stringify(r,null,2))}</pre></details></details></article>`).join('')||'<p>No action rule has been added. Cases without a permitted action wait for review.</p>';}
function workflowGuide(domain,isDraft){
 const explanation=(ws?.teachings||[]).filter(x=>x.teaching.approval_state==='APPROVED'&&domain.source_hashes?.[x.source_id]).map(x=>`<blockquote>${escapeText(x.teaching.human_text)}</blockquote>`).join('');
 return `<div class="guide-heading"><h3>${escapeText(domain.title)}</h3><span class="guide-status">${isDraft?'Draft — not yet in use':'Approved · version '+domain.version}</span></div><h4>The job</h4><p>${escapeText(domain.goal)}</p><h4>Information to check</h4><dl class="guide-fields">${domain.input_fields.map(f=>`<div><dt>${escapeText(humanize(f.label))}</dt><dd>${escapeText(f.description)}${f.type==='boolean'?' <span class="muted">Yes / No / Not supplied</span>':''}</dd></div>`).join('')}</dl>${explanation?'<h4>The task owner’s explanation</h4>'+explanation:''}<h4>What to do in each situation</h4>${renderRules(domain.rules,domain)}<div class="guide-stop"><h4>When to stop and ask</h4><p>If the facts or permission needed for an action are missing, the case waits for review. The recorded fallback is <strong>${escapeText(actionDescription(domain,domain.default_action_id))}</strong>.</p></div>`;
}
function updateNextStep(){
 let message='Start with the worked example, or choose a workflow below.';
 if(ws){
  if(ws.status==='STALE')message='Next: review the changed instructions and approve an updated guide.';
  else if(ws.draft&&ws.draft.base_version===ws.version)message='Next: check the work and its conditions below, then approve the workflow if it reflects the job.';
  else if(!ws.domain)message='Next: add instructions, describe the job, and choose “Organize these instructions”.';
  else if(!ws.dev_cases.length)message='Next: add at least one example case to test what AI can do with these instructions.';
  else if(teaching?.approval_state==='DRAFT')message='Next: read the proposed guidance in step 2, then approve it if it matches your judgment.';
  else if(teaching?.approval_state==='APPROVED')message='Next: try the same cases with the approved guidance, then check each result.';
  else if(question)message='Next: answer the question in step 2 using your own experience.';
  else if(currentRun)message='Next: check the saved results. If the instructions left a gap, explain it in step 2.';
  else message='Next: try the original instructions on the example cases below.';
 }
 if(recorded)message='You are reading a saved result. No new case is being processed.';
 $('next-step').textContent=message;
}
function caseInput(caseId,value){return (value.traces||[]).find(t=>t.payload?.case?.case_id===caseId)?.payload.case||(ws?.workspace_id===value.run.workspace_id?ws.dev_cases.find(c=>c.case_id===caseId):null);}
function caseSummary(c,fallback){if(!c)return fallback;const raw=String(c.raw_text||'').split(/The recorded facts below|\s*\{/)[0].trim();return raw||fallback;}
function caseFacts(c,domain){return '<dl class="case-facts">'+Object.entries(c?.facts||{}).map(([id,value])=>`<div><dt>${escapeText(humanize(fieldLabel(domain,id)))}</dt><dd>${escapeText(displayValue(value))}</dd></div>`).join('')+'</dl>';}
function renderCaseEditor(){
 const holder=$('case-editor');
 if(!ws||ws.sample){holder.innerHTML='';return;}
 if(!ws.domain){holder.innerHTML='<p class="muted">Approve the workflow to add cases using its information fields.</p>';return;}
 if(ws.frozen||ws.run_ids.length){holder.innerHTML='<p class="muted">These cases are fixed so the before-and-after checks use the same inputs. Use a new workspace to test a different set.</p>';return;}
 const control=(field,group,index)=>{const id=`case-${group}-${index}`;return `<div class="case-input"><label for="${id}">${escapeText(humanize(field.label))}</label><p id="${id}-help" class="muted">${escapeText(field.description)}</p>${field.type==='boolean'?`<select id="${id}" aria-describedby="${id}-help"><option value="">Not supplied</option><option value="true">Yes</option><option value="false">No</option></select>`:`<input id="${id}" type="${field.type==='number'?'number':'text'}" ${field.type==='number'?'step="any"':''} aria-describedby="${id}-help" placeholder="Not supplied">`}</div>`;};
 holder.innerHTML=`<h3>Add an example case</h3><p>Describe a situation that you want AI to handle. Enter only facts you know. A blank field means the information is not supplied.</p><label for="case-description">Describe the situation</label><textarea id="case-description" rows="2" maxlength="4000" placeholder="What has happened, and what needs deciding?"></textarea><label for="case-kind">What kind of example is this?</label><select id="case-kind"><option value="normal">A routine case</option><option value="transfer">A case the instructions may not cover</option><option value="must_hold">A case that should wait for more information</option></select><h4>Facts about this case</h4><div class="case-form-grid">${ws.domain.input_fields.map((f,i)=>control(f,'fact',i)).join('')}</div><h4>Before any action</h4><p class="muted">Enter the case’s current state. These values are not chosen for you.</p><div class="case-form-grid">${ws.domain.state_fields.map((f,i)=>control(f,'state',i)).join('')}</div><button id="add-case" class="secondary">Save this example case</button><p class="muted">Add up to 40 cases before the first test. Case type organizes the examples; it does not set a correct-answer label.</p>`;
 bind('add-case',async()=>{
  const description=$('case-description').value.trim();if(!description)throw Error('Describe the situation for this example case.');
  const cases=[...ws.dev_cases];if(cases.length>=40)throw Error('This workspace already has 40 cases.');
  const read=(fields,group)=>Object.fromEntries(fields.map((f,i)=>{const input=$(`case-${group}-${i}`),raw=input.value.trim();let value=raw===''?null:f.type==='boolean'?raw==='true':f.type==='number'?Number(raw):raw;if(input.validity?.badInput||f.type==='number'&&value!==null&&!Number.isFinite(value))throw Error('Enter a number for '+f.label+'.');return [f.field_id,value];}));
  const c={case_id:'case_'+crypto.randomUUID().replaceAll('-',''),domain_id:ws.domain.domain_id,split:'dev',stratum:$('case-kind').value,facts:read(ws.domain.input_fields,'fact'),raw_text:description,initial_state:read(ws.domain.state_fields,'state')};
  await api('/cases/import',{workspace_id:ws.workspace_id,cases:[...cases,c]});await refresh();notify('Example saved. Add another, or try the original instructions.');
 });
}
function renderWorkspace(){
 if(displayedWorkspace!==ws.workspace_id){resetWorkspaceView();displayedWorkspace=ws.workspace_id;}
 $('mode').textContent=ws.mode+(admin?' · ADMIN':'');$('mode').classList.toggle('mock',ws.mode==='MOCK');
 $('source-editor').hidden=false;$('workspace-label').textContent=(ws.sample?'Fictional example':'Your own workflow')+' · '+(ws.status==='STALE'?'Instructions changed':ws.version<0?'Workflow awaiting approval':'Approved workflow, version '+ws.version);
 $('admin-workspace').textContent=admin?'Workspace ID for the runbook: '+ws.workspace_id:'';$('goal').value=ws.goal;
 $('source-list').innerHTML=ws.sources.map(s=>`<li><strong>${escapeText(s.name)}</strong> <span class="muted">${(s.size/1024).toFixed(1)} KiB</span><details><summary>File details</summary><p class="muted">${escapeText(s.mime)}<br>Source: ${escapeText(s.source_id)}<br>Content hash: ${escapeText(s.version_hash)}</p></details></li>`).join('');
 $('stale').hidden=ws.status!=='STALE';const isDraft=Boolean(ws.draft&&ws.draft.base_version===ws.version),d=isDraft?ws.draft.domain:ws.domain;
 $('approve-workflow').hidden=!isDraft;
 if(d){$('workflow').innerHTML=workflowGuide(d,isDraft);$('domain-json').value=JSON.stringify(d,null,2);}else{$('workflow').textContent='Add instructions and organize them to create a guide for review.';$('domain-json').value='';}
 $('observations').innerHTML=ws.draft?.observations?.length?'<details><summary>Information found in the instructions</summary>'+ws.draft.observations.map(o=>`<p>${escapeText(humanize(fieldLabel(d,o.field_id)))}: <strong>${escapeText(displayValue(o.value))}</strong> <span class="muted">(${escapeText(humanize(o.status))})</span></p>`).join('')+'</details>':'';
 $('dev-cases').innerHTML='<p class="muted">'+ws.dev_cases.length+' example cases ready.</p>'+ws.dev_cases.map((c,i)=>`<details><summary>Case ${i+1}: ${escapeText(caseSummary(c,'Example case'))}</summary>${caseFacts(c,d)}<p><strong>Starting state:</strong> ${escapeText(stateDescription(c.initial_state,d))}</p><details><summary>Original case data</summary><pre>${escapeText(JSON.stringify(c,null,2))}</pre></details></details>`).join('');
 question=ws.questions.at(-1)?.question||null;teaching=ws.teachings.at(-1)?.teaching||null;renderTeaching();renderCaseEditor();updateNextStep();
 sessionStorage.setItem('jt-workspace',ws.workspace_id);
}
function resetWorkspaceView(){currentRun=beforeRun=afterRun=question=teaching=null;recorded=false;stopRequested=false;displayedWorkspace=null;$('answer').value='';$('cases-json').value='';$('file').value='';$('recorded').value='';$('run-status').textContent='';$('comparison').innerHTML='';$('results-table').innerHTML='';sessionStorage.removeItem('jt-run');renderTeaching();}
function renderTeaching(){
 $('question').innerHTML=question?`<h3>${escapeText(question.text)}</h3><p>${escapeText(question.why_needed)}</p><details><summary>Cases behind this question</summary>${question.affected_dev_case_ids.map((id,i)=>`<p>${escapeText(caseSummary(ws?.dev_cases.find(c=>c.case_id===id),'Example case '+(i+1)))}</p>`).join('')}</details>`:'<p>First try the original instructions in step 1. Then find a case that needs your explanation.</p>';
 $('rules').innerHTML=teaching?`<h3>Your explanation</h3><blockquote>${escapeText(teaching.human_text)}</blockquote><h3>Guidance to review</h3>${renderRules(teaching.proposed_rules)}`:'<p>Your proposed guidance will appear here. Nothing changes until you approve it.</p>';
 $('approve-teaching').hidden=!teaching||teaching.approval_state!=='DRAFT';updateNextStep();
}
async function refresh(){if(ws){ws=await api('/workspaces/'+ws.workspace_id,null,'GET');renderWorkspace();}}
async function create(sample){ws=await api('/workspaces',sample?{sample}:{});currentRun=beforeRun=afterRun=null;recorded=false;renderWorkspace();tab('sources');notify(sample?'Review the work and its conditions, then approve the workflow if it matches the example instructions.':'Describe the job and add the instructions you use today.');}
bind('sample-invoice',()=>create('invoice_routing'));bind('sample-support',()=>create('support_triage'));bind('new',()=>create());
bind('upload',async()=>{if(!ws)throw Error('Create a workspace first.');const file=$('file').files[0];if(!file)throw Error('Choose a file.');const data=new FormData();data.append('workspace_id',ws.workspace_id);data.append('file',file);await api('/sources',data);await refresh();notify('Source saved. Analyse and review the workflow.');});
bind('analyse',async()=>{if(!ws)throw Error('Create a workspace first.');notify('Reading the source material…');await api('/sources/extract',{workspace_id:ws.workspace_id});notify('Source reading saved. Drafting the workflow…');await api('/domains/draft',{workspace_id:ws.workspace_id,goal:$('goal').value});await refresh();notify('Draft ready. Check the evidence and action boundaries before approval.');});
bind('save-domain',async()=>{await api('/domains/draft',{workspace_id:ws.workspace_id,domain:JSON.parse($('domain-json').value)});await refresh();notify('Edited workflow saved as a draft. Review before approving.');});
bind('approve-workflow',async()=>{await api('/domains/approve',{draft_id:ws.draft.draft_id,base_version:ws.version});await refresh();notify('Workflow approved. Try the original instructions on the example cases.');});
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
  catch(error){try{showRun(await api('/runs/'+currentRun,null,'GET'));}catch(refreshError){error.message+=' Saved status could not be refreshed. Use Continue remaining cases to retrieve it.';}throw error;}
  if(stopRequested){if(cancelRequest)await cancelRequest;showRun(await api('/runs/'+currentRun,null,'GET'));return {status:'stopped'};}
  if(step.failed){const state=await api('/runs/'+currentRun,null,'GET');showRun(state);notify((step.error?.message||'The case failed.')+' The failed case remains in the results. Use Continue remaining cases to process those not yet finished.',true);return {status:'failed'};}
  if(step.done===false){notify('A case is already running. Use Continue remaining cases after it finishes.');return {status:'pending'};}
 }
 notify('Progress saved. Use Continue remaining cases to continue.');return {status:'pending'};
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
function taskOutcome(task,domain){
 const receipts=task.receipt_ids||[];
 if(task.status==='FAILED')return {title:'Could not complete',next:'Review the failure details. This case has no completed result.',kind:'failed'};
 if(task.status==='CANCELLED')return {title:'Stopped',next:'No further step will start for this case.',kind:'pending'};
 if(task.status==='LEASED')return {title:'Still processing',next:'Wait for the saved result. You can stop new cases.',kind:'pending'};
 if(task.status!=='COMPLETED')return {title:'Waiting to finish',next:'Continue the remaining cases to get a result.',kind:'pending'};
 if(!receipts.length)return {title:'Result not verified',next:'No execution receipt is recorded. Inspect the saved details.',kind:'failed'};
 if(task.score?.labelled&&task.score.correct===false)return {title:'Action needs review',next:'The saved action did not match the expected result for this case. Check the explanation before using this guidance.',kind:'review'};
 if(task.decision?.outcome==='HOLD')return {title:'Waiting for review',next:task.decision.missing_fields?.length?'Information needed: '+task.decision.missing_fields.map(id=>humanize(fieldLabel(domain,id))).join(', ')+'.':'Check the explanation: more information or permission is needed before proceeding.',kind:'held'};
 return {title:actionDescription(domain,task.decision?.action_id),next:task.score?.labelled&&task.score.correct?'The saved action matches the expected result for this case.':'The action was saved. No expected-answer check is available; a person must verify it.',kind:'done'};
}
function taskEvidence(t,value){
 const domain=value.run.domain,receipts=(value.receipts||[]).filter(r=>(t.receipt_ids||[]).includes(r.receipt_id));
 const traces=(value.traces||[]).filter(r=>(t.trace_ids||[]).includes(r.trace_id));
 const rules=(t.decision?.rule_ids||[]).map(id=>domain?.rules?.find(rule=>rule.rule_id===id)?.statement||humanize(id));
 const c=caseInput(t.case_id,value);
 return '<p>'+escapeText(t.decision?.explanation||t.error?.message||'A final explanation is not available yet.')+'</p>'+(c?'<h4>Information used</h4>'+caseFacts(c,domain):'')+(rules.length?'<h4>Guidance used</h4>'+rules.map(rule=>'<p>'+escapeText(rule)+'</p>').join(''):'<p>No approved action rule is cited for this result.</p>')+receipts.map(r=>'<div class="receipt"><strong>Saved change in this practice case</strong><p>Before: '+escapeText(stateDescription(r.before_state,domain))+'</p><p>After: '+escapeText(stateDescription(r.after_state,domain))+'</p><p class="muted">'+escapeText(r.committed_at)+'</p></div>').join('')+(!(t.receipt_ids||[]).length?'<p>No execution receipt is recorded. No committed action is verified here.</p>':!receipts.length?'<p>Receipt references are saved. Open this detail while connected to load the full record.</p>':'')+'<details><summary>Original decision, receipts and technical details</summary><pre>'+escapeText(JSON.stringify({case_id:t.case_id,status:t.status,error:t.error||null,proposed:t.raw_decision,applied:t.decision,state:t.state,receipt_ids:t.receipt_ids,receipts,traces:traces.map(x=>({trace_id:x.trace_id,elapsed_ms:x.elapsed_ms,attempts:x.attempts,error:x.error}))},null,2))+'</pre></details>';
}
function showRun(value){
 const r=value.run,m=value.metrics;if(r.arm==='A_SOURCE_ONLY')beforeRun=value;if(r.arm==='C_JT_RULES')afterRun=value;
 const armNames={A_SOURCE_ONLY:'Original instructions',B_TEXT_ADDED:'Instructions and task owner’s explanation',C_JT_RULES:'Instructions and approved guidance'};
 $('run-status').textContent=`${recorded?'Recorded result · ':''}${armNames[r.arm]||humanize(r.arm)} · ${m.counts.COMPLETED} of ${m.total} cases finished${m.counts.FAILED?' · '+m.counts.FAILED+' could not complete':''}${m.counts.CANCELLED?' · '+m.counts.CANCELLED+' stopped':''}${r.cancelled?' · Processing stopped (an in-flight case may still finish)':''}${m.stale?' · Instructions have changed since this test':''}`;
 const comparable=comparableRuns(beforeRun,afterRun);
 const outcomes=value.tasks.map(t=>taskOutcome(t,r.domain));
 const count=kind=>outcomes.filter(x=>x.kind===kind).length;
 $('comparison').innerHTML=[['AI proceeded',count('done'),'An action was saved in the tested case. Review whether it was appropriate.'],['A person must review',count('held')+count('review'),'AI held the case, or its saved action needs correction.'],['Not yet verified',count('pending')+count('failed'),'A technical failure, pending case or missing record is not proof of completion.']].map(([label,n,detail])=>`<div class="metric">${label}<strong>${n}</strong><span>${detail}</span></div>`).join('');
 if(r.mode==='MOCK')$('comparison').innerHTML+='<p class="warning">Simulation mode. These are simulated outcomes, not measured AI performance.</p>';
 const scores=[['This run',m],...(comparable?[['Before teaching',beforeRun.metrics],['After teaching',afterRun.metrics]]:[])];
 const scoreDetails=`<details class="score-details"><summary>Measured scores and test details</summary><p>Completed actions, correct decisions and correct holds measure different things. A case that correctly waits for review is not an autonomous completion.</p><div class="scroll"><table><thead><tr><th>Test</th><th>Correct autonomous completion</th><th>Correct decisions, including hold</th><th>Failed cases</th><th>Critical errors</th></tr></thead><tbody>${scores.map(([title,x])=>`<tr><td>${escapeText(title)}</td><td>${percent(x.correct_completion_rate)}</td><td>${percent(x.correct_decision_rate??null)}</td><td>${x.counts.FAILED}</td><td>${x.critical_errors??'Unlabelled'}</td></tr>`).join('')}</tbody></table></div><p class="muted">${m.total} attempts / ${m.unique_cases} unique cases · ${m.holds} holds · ${m.human_inputs} explanations from the task owner</p>${beforeRun&&afterRun&&!comparable?'<p class="warning">No before/after score comparison: both runs must be complete and use the same cases, repeats, model settings and code, with unchanged source evidence.</p>':''}${comparable&&(beforeRun.metrics.counts.FAILED||afterRun.metrics.counts.FAILED||beforeRun.metrics.counts.CANCELLED||afterRun.metrics.counts.CANCELLED)?'<p class="warning">Technical failures remain in these rates. The difference alone does not establish a teaching benefit.</p>':''}<p class="muted">Mode: ${escapeText(r.mode)} · Model: ${escapeText(r.model_settings?.model||'not recorded')} · Rule version: ${escapeText(r.domain?.version??'not recorded')} · Started: ${escapeText(r.created_at||'not recorded')}</p><details><summary>Original metrics and run identifiers</summary><pre>${escapeText(JSON.stringify({run_id:r.run_id,arm:r.arm,code_hash:r.code_hash,model_settings:r.model_settings,metrics:m},null,2))}</pre></details></details>`;
 $('results-table').innerHTML='<div class="scroll"><table class="case-results"><thead><tr><th>Case</th><th>What happened</th><th>What to do next</th></tr></thead><tbody>'+value.tasks.map((t,i)=>{const outcome=outcomes[i],c=caseInput(t.case_id,value),caseNumber=r.case_ids.indexOf(t.case_id)+1,previous=comparable&&r.arm==='C_JT_RULES'?beforeRun.tasks.find(x=>x.case_id===t.case_id&&x.repeat===t.repeat):null;return `<tr><td><strong>Case ${caseNumber}</strong>${c?'<p>'+escapeText(caseSummary(c,'Example case'))+'</p>':''}${r.repeats>1?'<span class="muted">Repeat '+escapeText(t.repeat)+'</span>':''}</td><td><span class="result-pill ${outcome.kind}">${escapeText(outcome.title)}</span>${previous?'<p class="before-outcome"><strong>Before the explanation:</strong> '+escapeText(taskOutcome(previous,beforeRun.run.domain).title)+'</p>':''}<p class="muted">${(t.receipt_ids||[]).length?'Saved state: ':'Current state: '}${escapeText(stateDescription(t.state,r.domain))}</p></td><td><p>${escapeText(outcome.next)}</p><details data-task="${escapeText(t.task_id)}"><summary>Why this happened and what changed</summary>${taskEvidence(t,value)}</details></td></tr>`;}).join('')+'</tbody></table></div>'+scoreDetails;
 let exported=null;
 if(!value.receipts&&!recorded)$('results-table').querySelectorAll('details[data-task]').forEach(details=>{details.addEventListener('toggle',async()=>{if(!details.open||details.dataset.loaded)return;details.dataset.loaded='loading';try{exported=exported||api('/exports/'+r.run_id,null,'GET');const full=await exported;const task=full.tasks.find(t=>t.task_id===details.dataset.task);details.innerHTML='<summary>Why this happened and what changed</summary>'+taskEvidence(task,full);details.dataset.loaded='true';}catch(e){details.dataset.loaded='';exported=null;const p=document.createElement('p');p.textContent='Saved receipt could not be loaded: '+e.message;details.append(p);}});});
 updateNextStep();
}
bind('download',async()=>{if(!currentRun||recorded)throw Error('Choose an active saved run.');const value=await api('/exports/'+currentRun,null,'GET');const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=currentRun+'.json';a.click();URL.revokeObjectURL(url);});
$('recorded').onchange=()=>action(async()=>{const file=$('recorded').files[0];if(!file||file.size>20*1024*1024)throw Error('Choose an evidence JSON file under 20 MiB.');const value=JSON.parse(await file.text());if(value.export_version!=='1.0'||!value.run||!value.metrics||!Array.isArray(value.tasks))throw Error('This is not a Judgment Transfer export.');recorded=true;beforeRun=afterRun=null;currentRun=null;$('mode').textContent='RECORDED · '+value.run.mode;showRun(value);notify('Read-only recording opened. No model call was made.');});
bind('admin-login',async()=>{admin=$('admin-token').value;$('admin-token').value='';await sessionInfo();ws=null;resetWorkspaceView();$('source-editor').hidden=true;$('workspace-label').textContent='';$('admin-workspace').textContent='';sessionStorage.removeItem('jt-workspace');notify('Administrator access enabled for this tab. Create or reopen an evaluation workspace.');});
bind('open-workspace',async()=>{const id=$('open-workspace-id').value.trim();if(!/^ws_[a-f0-9]{32}$/.test(id))throw Error('Enter the saved Workspace ID.');ws=await api('/workspaces/'+id,null,'GET');recorded=false;renderWorkspace();currentRun=ws.run_ids.at(-1)||null;if(currentRun){sessionStorage.setItem('jt-run',currentRun);showRun(await api('/runs/'+currentRun,null,'GET'));}tab('sources');notify('Saved workspace opened. Completed actions are preserved.');});
bind('freeze',async()=>{if(!ws||!admin)throw Error('Administrator access and an approved teaching workspace are required.');await api('/workspaces/freeze',{workspace_id:ws.workspace_id});await refresh();notify('Cases, labels and approved rules frozen. Copy this workspace ID into step 07.');});
(async()=>{try{await sessionInfo();const id=sessionStorage.getItem('jt-workspace'),savedRun=sessionStorage.getItem('jt-run');if(id){ws=await api('/workspaces/'+id,null,'GET');renderWorkspace();if(savedRun&&ws.run_ids.includes(savedRun)){currentRun=savedRun;sessionStorage.setItem('jt-run',savedRun);showRun(await api('/runs/'+currentRun,null,'GET'));}}}catch(e){notify(e.message,true);sessionStorage.removeItem('jt-workspace');sessionStorage.removeItem('jt-run');}})();

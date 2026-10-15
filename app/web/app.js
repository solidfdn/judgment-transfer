'use strict';
const $=id=>document.getElementById(id);
let csrf='',admin='',ws=null,currentRun=null,beforeRun=null,afterRun=null,question=null,teaching=null,busy=false,recorded=false;
let operation=null,executingRun=false,stopRequested=false,cancelRequest=null,displayedWorkspace=null,savedWork=null,activeTab='sources';
let caseDraft=null,caseEdits=null,savedRuns=[],verifiedComparison=null,activeCodeHash='';
const escapeText=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function paintNotice(){const n=$('notice');n.textContent=operation.message+(operation.started!==null?' · '+Math.floor((Date.now()-operation.started)/1000)+'s elapsed':'');n.className=operation.error?'error':'';$('notice-details').hidden=!operation.details;$('notice-technical').textContent=operation.details?JSON.stringify(operation.details,null,2):'';}
function notify(message,error=false,details=null){operation={message,error,details,started:busy?operation?.started??Date.now():null};$('notice-details').open=false;paintNotice();}
function serviceError(error={},status=null,path=''){
 const messages={
  SESSION_EXPIRED:'This session has ended. Reopen this page to start again. Access to earlier work may require the original administrator.',
  CSRF_REQUIRED:'Refresh this page, then open your saved work before making changes.',
  UNAUTHORIZED:'Administrator access could not be verified. Check the token with the application owner.',
  ADMIN_REQUIRED:'This option is for the evaluation administrator. Continue with the ordinary example cases, or ask the application owner for access.',
  FORBIDDEN:'You do not have access to this saved work. Use work created with your current access.',
  NOT_FOUND:'This saved item is not available with your current access. Check the saved workspace ID or start a new check.',
  SOURCE_REQUIRED:'Add the task owner’s instructions in step 1 before continuing.',
  REVIEWER_REQUIRED:'Enter the responsible person’s name before finalizing a record or starting a test.',
  CONFIRMATION_REQUIRED:'Confirm the history deletion before continuing.',
  HISTORY_CHANGED:'Decision history changed. Choose “Open history” again before deleting or resetting it.',
  LIVE_REQUIRED:'Reading new documents requires the AI-connected application. No simulated reading was substituted.',
  EXTRACTION_REQUIRED:'Choose “Organize the work” in step 1 to read the current files first.',
  WORKFLOW_REQUIRED:'Review and approve the work and its conditions in step 1 before continuing.',
  CASES_REQUIRED:'Add at least one example case in step 1 before testing the instructions.',
  STALE:'The instructions or approved guidance changed. Review the latest version in step 1, then start a new test.',
  VERSION_CONFLICT:'This page is showing an older version. Reopen your saved work and review the latest guidance before approving or continuing.',
  FROZEN:'This set of cases or instructions is locked for comparison. Start a new check to use different material or cases.',
  FROZEN_EXPERIMENT:'This saved evaluation used an earlier application or AI configuration. Read its results; a new formal evaluation needs a separate, unseen set of cases.',
  RUN_PROTOCOL_CHANGED:'This saved test used an earlier application or AI configuration and cannot continue. Read its results; start a new test for the updated application.',
  CANCELLED:'This test was stopped and cannot continue. Read the saved results, or start a new test.',
  BUSY:'A request is still being processed. Wait for it to finish, then reopen the saved result before continuing.',
  REQUEST_INTERRUPTED:'The connection ended before completion was confirmed. Reopen your saved work to check what was saved before trying the action again.',
  IDEMPOTENCY_CONFLICT:'This request conflicts with an earlier request. Reopen your saved work and check its latest state before continuing.',
  IDEMPOTENCY_REQUIRED:'The request could not be identified. Refresh this page and reopen your saved work before continuing.',
  NO_TEACHING_CASE:'A completed test must include a case that waited for review or gave an incorrect result. Try the original instructions, then check the results.',
  TEACHING_LIMIT:'This evaluation already has three approved explanations, its allowed limit. Review their results or start a separate check.',
  HOLDOUT_ISOLATION:'The formal evaluation cases cannot be used to draft guidance. Use the example cases from step 1.',
  RULE_CONFLICT:'The proposed guidance gives different actions for the same conditions. Resolve that conflict before approving it.',
  INVALID_EVIDENCE:'The supporting material could not be verified. Reopen your saved work and review the current instructions before approving guidance.',
  INPUT_TOO_LARGE:'This file or saved record exceeds a size limit, or the file is empty. Check the file limits in step 1 and use a smaller supported file.',
  INVALID_INPUT:'Some information could not be accepted. Check the file, entered values or edited setup; the technical details identify the rejected item.',
  MODEL_FAILED:'AI did not return a usable answer. Review the saved result to see what completed before deciding how to continue.',
  APP_DEADLINE:'Processing took too long to confirm an action. Review the saved result to see what completed.',
  STEP_LIMIT:'This case reached the allowed number of processing steps. Review its saved result and simplify the task before a separate test.',
  LEASE_LOST:'Another request took over processing this case. Reopen the saved result to check its current status.',
  CALL_LIMIT:'The allowed number of AI requests has been reached. You can still read saved results. Further testing needs the application owner’s review.',
  COST_LIMIT:'The allowed AI budget has been reached. You can still read saved results. Further testing needs the application owner’s review.',
  RETRY_LIMIT:'The allowed recovery attempts have been used. Read the saved results and ask the application owner to review the stopped test.',
  CONTROLLED_STUDY:'This saved evaluation is managed through the administrator’s evaluation procedure. Its results remain available to read.',
  MODE_MISMATCH:'This saved work uses a different processing mode. Read its exported results or create work in the current mode.',
  MOCK_CUSTOM_WORKFLOW:'Simulation mode cannot interpret new instructions or explanations. Use a supplied example, or ask the owner for access to the AI-connected application.',
  MOCK_ANSWER:'Simulation mode accepts only the explanation supplied with this example. Use that explanation, or use the AI-connected application for your own.',
  NOT_READY:'Review and approve the work and at least one explanation before locking the evaluation.',
  FREEZE_REQUIRED:'The evaluation administrator must lock the cases, expected answers and guidance before the formal comparison.',
  LABELS_REQUIRED:'The formal comparison needs saved expected answers for every case. Ask the evaluation administrator to complete that setup.',
  INTERNAL_ERROR:'The request did not complete as expected. Reopen your saved work and review what was saved before continuing.',
  CONNECTION_FAILED:'The application could not be reached. Check your connection, then reopen your saved work to see whether the request completed.',
  UNREADABLE_RESPONSE:'The application returned a response that could not be read. Reopen your saved work to check what was saved before continuing.'
 };
 const message=messages[error.code]||'The request could not be completed. Reopen your saved work to check its latest state. Share the technical details with the application owner if the problem continues.';
 const result=new Error(message);result.details={code:error.code||'HTTP_'+status,message:error.message||'',request_id:error.request_id||null,status,path};return result;
}
function notifyError(error,prefix=''){const message=error instanceof SyntaxError?'The file or edited data is not valid JSON. Check its format before trying again.':error.message||'The action could not be completed. Review the information on this page.';notify(prefix+message,true,error.details||null);}
function tab(name){activeTab=name;document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==name);document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));updateNextStep();}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
async function api(path,data,method='POST',key=null){
 const headers={};if(admin)headers['X-JT-Admin']=admin;
 if(method!=='GET'){headers['X-CSRF-Token']=csrf;headers['Idempotency-Key']=key||crypto.randomUUID();if(!(data instanceof FormData))headers['Content-Type']='application/json';}
 let response;try{response=await fetch('/api/v1'+path,{method,headers,body:method==='GET'?undefined:data instanceof FormData?data:JSON.stringify(data||{}),credentials:'same-origin'});}catch(error){throw serviceError({code:'CONNECTION_FAILED',message:error.message},null,path);}
 let result;try{result=await response.json();}catch(error){throw serviceError({code:'UNREADABLE_RESPONSE',message:error.message,request_id:response.headers?.get('X-Request-ID')},response.status,path);}
 if(!response.ok||result.error)throw serviceError({...result.error,request_id:result.error?.request_id||response.headers?.get('X-Request-ID')},response.status,path);return result;
}
async function action(fn){
 if(busy||cancelRequest)return;busy=true;
 document.getElementById('operation-status')?.remove();
 operation={message:'Working on your request. Please wait for the result.',error:false,started:Date.now()};paintNotice();
 const timer=setInterval(paintNotice,1000);
 const buttons=[...document.querySelectorAll('button')],disabled=buttons.map(b=>b.disabled);
 buttons.forEach(b=>b.disabled=true);document.body.setAttribute('aria-busy','true');
 try{const result=await fn();if(operation.message==='Working on your request. Please wait for the result.')notify(result?.status&&result.status!=='completed'?'Progress saved. Some cases are not complete.':'Completed. See the result on this page.');return result;}
 catch(e){notifyError(e);return {status:'failed'};}
 finally{clearInterval(timer);busy=false;operation.started=null;paintNotice();document.body.removeAttribute('aria-busy');buttons.forEach((b,i)=>b.disabled=disabled[i]);}
}
function bind(id,fn){$(id).onclick=()=>action(fn);}
function modeLabel(mode){return mode==='LIVE'?'AI testing':mode==='MOCK'?'Simulation':humanize(mode);}
async function sessionInfo(){const s=await api('/session',null,'GET');csrf=s.csrf;activeCodeHash=s.code_hash||'';$('mode').textContent=modeLabel(s.mode)+(s.admin?' · Administrator':'');$('mode').classList.toggle('mock',s.mode==='MOCK');$('version').textContent='Version '+s.version;return s;}
function humanize(value){return JTUiCopy.humanize(value);}
function fieldLabel(domain,id){return JTUiCopy.field(domain,id).label;}
function displayValue(value){return JTUiCopy.value(value);}
function stateValue(value,domain=null,id=''){return JTUiCopy.state(domain,id,value);}
function actionDescription(domain,id){return JTUiCopy.action(domain,id);}
function stateDescription(state,domain){return Object.entries(state||{}).map(([id,value])=>`${fieldLabel(domain,id)}: ${stateValue(value,domain,id)}`).join(' · ')||'No saved state';}
function conditions(rule,domain){
 const show=c=>JTUiCopy.condition(domain,c);
 return [rule.when.all.length?'All of these must be true:\n'+rule.when.all.map(c=>'• '+show(c)).join('\n'):'',rule.when.any.length?(rule.when.all.length?'At least one of these must also be true:\n':'At least one of these must be true:\n')+rule.when.any.map(c=>'• '+show(c)).join('\n'):''].filter(Boolean).join('\n\n');
}
function ruleSources(rule){return (rule.source_refs||[]).map(ref=>`<blockquote>${escapeText(ref.quote)}</blockquote>`).join('')||'<p>No supporting quotation was recorded.</p>';}
function sourceReferences(refs,sources=[]){
 return (refs||[]).map(ref=>{const source=sources.find(s=>s.source_id===ref.source_id);const location=ref.locator.replace(/^line:/,'Line ').replace(/^page:/,'Page ').replace(/^image:1$/,'Image').replace(/^seconds:/,'Seconds ').replace(/^human:1$/,'Task owner’s explanation');return '<p class="muted">'+escapeText(source?.name||ref.source_id)+' · '+escapeText(location)+'</p>'+(ref.quote?'<blockquote>'+escapeText(ref.quote)+'</blockquote>':'');}).join('')||'<p class="muted">No source passage is linked to this point. Ask the task owner to clarify it.</p>';
}
function observationsGuide(observations,domain,sources){
 const labels={OBSERVED:'Stated in the source',INFERRED:'AI inference — needs confirmation',UNRESOLVED:'Unresolved — needs clarification'};
 return observations?.length?'<details><summary>Source facts, AI inferences and unresolved points</summary>'+observations.map(o=>'<article><h4>'+escapeText(fieldLabel(domain,o.field_id))+'</h4><p><strong>'+escapeText(labels[o.status]||o.status)+'</strong>'+ (o.value===null?'':': '+escapeText(displayValue(o.value)))+'</p>'+sourceReferences(o.source_refs,sources)+'</article>').join('')+'</details>':'';
}
function recordedTokens(value){
 if(!Array.isArray(value.traces))return 'Load the full record';
 const traces=[...new Map(value.traces.map((t,i)=>[t.trace_id||String(i),t])).values()];
 let total=0,missing=0;
 for(const trace of traces)for(const a of trace.attempts||[]){
  const values=[a.input_tokens,a.output_tokens,a.thinking_tokens];
  if(values.every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0))total+=values.reduce((x,y)=>x+y,0);else missing++;
 }
 const expected=[...new Set(value.tasks.flatMap(t=>t.trace_ids||[]))];
 if(expected.some(id=>!traces.some(t=>t.trace_id===id)))return 'Incomplete trace records';
 return total.toLocaleString('en-US')+(missing?' recorded · '+missing+' attempt(s) unreported':'');
}
function measurementRows(rows){
 return rows.map(([title,value])=>{const m=value.metrics;return '<tr><td>'+escapeText(title)+'</td><td>'+percent(m.correct_completion_rate??null)+'</td><td>'+percent(m.correct_decision_rate??null)+'</td><td>'+(m.critical_errors??'Unlabelled')+'</td><td>'+escapeText(m.human_inputs??'Not recorded')+'</td><td>'+escapeText(recordedTokens(value))+'</td><td>'+(typeof m.latency_ms==='number'?(m.latency_ms/1000).toFixed(1)+' s':'Not recorded')+'</td></tr>';}).join('');
}
function renderRules(rules,domain=ws?.domain){return rules.map(r=>`<article class="rule"><div class="rule-heading"><h3>${escapeText(actionDescription(domain,r.action_id))}</h3><span class="guide-status">${r.approved_by?'Approved':'Draft — review needed'}</span></div><div class="rule-conditions">${escapeText(conditions(r,domain))}</div><p class="rule-action"><strong>Then:</strong> ${escapeText(actionDescription(domain,r.action_id))}</p><details><summary>Original wording and supporting instructions</summary><p><strong>Rule as written:</strong> ${escapeText(r.statement)}</p>${ruleSources(r)}<p class="muted">When more than one rule matches, the recorded priority determines which applies. This rule has priority ${escapeText(r.priority)}.</p><details><summary>Original rule and source references</summary><pre>${escapeText(JSON.stringify(r,null,2))}</pre></details></details></article>`).join('')||'<p>No conditions for taking an action have been added. Cases without a permitted action wait for review.</p>';}
function workflowGuide(domain,isDraft){
 const explanation=(ws?.teachings||[]).filter(x=>x.teaching.approval_state==='APPROVED'&&domain.source_hashes?.[x.source_id]).map(x=>`<blockquote>${escapeText(x.teaching.human_text)}</blockquote>`).join('');
 return `<div class="guide-heading"><h3>${escapeText(JTUiCopy.title(domain))}</h3><span class="guide-status">${isDraft?'Draft — not yet in use':'Approved · version '+domain.version}</span></div><h4>The job</h4><p>${escapeText(JTUiCopy.goal(domain))}</p><h4>Information to check</h4><dl class="guide-fields">${domain.input_fields.map(f=>`<div><dt>${escapeText(fieldLabel(domain,f.field_id))}</dt><dd>${escapeText(JTUiCopy.field(domain,f.field_id).description)}${f.type==='boolean'?' <span class="muted">Yes / No / Not supplied</span>':''}</dd></div>`).join('')}</dl>${explanation?'<h4>The task owner’s explanation</h4>'+explanation:''}<h4>What to do in each situation</h4>${renderRules(domain.rules,domain)}<div class="guide-stop"><h4>When to stop and ask</h4><p>If the facts or permission needed for an action are missing, the case waits for review. The instruction for that situation is <strong>${escapeText(actionDescription(domain,domain.default_action_id))}</strong>.</p></div>`;
}
function updateNextStep(){
 let message='Add a file or explanation, then organize the work.';
 if(ws){
  if(ws.status==='STALE')message='Next: review the changed instructions and approve an updated guide.';
  else if(ws.draft?.base_version===ws.version&&ws.draft?.input_review_issues?.length)message='Next: revise the flagged inputs. The previous draft stays saved; nothing is approved.';
  else if(ws.draft&&ws.draft.base_version===ws.version)message='Next: check the work and its conditions below, then approve the conditions if they reflect the job.';
  else if(!ws.domain)message=ws.requirements_review?'Review the questions below. Add an explanation, or prepare a practice test.':'Add a file or explanation, then choose “Organize the work”.';
  else if(!ws.dev_cases.length)message='Next: add at least one example case to test what AI can do with these instructions.';
  else if(teaching?.approval_state==='DRAFT')message='Next: read the proposed guidance in step 2, then approve it if it matches your judgment.';
  else if(teaching?.approval_state==='APPROVED')message='Next: try the same cases with the approved guidance, then check each result.';
  else if(question)message='Next: answer the question in step 2 using your own experience.';
  else if(currentRun)message='Next: check the saved results. If the instructions left a gap, explain it in step 2.';
  else message='Next: try the original instructions on the example cases below.';
 }
 if(recorded)message='You are reading a saved result. No new case is being processed.';
 $('next-step').textContent=message;
 $('next-step').hidden=!ws&&!recorded;$('record-person').hidden=!ws||recorded;$('history-panel').hidden=!ws||recorded;
 $('workflow-card').hidden=!(ws?.domain||ws?.draft&&ws.draft.base_version===ws.version);
 $('cases-card').hidden=!ws?.domain;
 // Visual emphasis only: existing availability, approvals and callbacks are unchanged.
 let primary=null;
 if(activeTab==='sources'){
  if(!ws)primary='analyse';
  else if(ws.frozen)primary=null;
  else if(ws.status==='STALE')primary='analyse';
  else if(ws.draft&&ws.draft.base_version===ws.version)primary=ws.draft.input_review_issues?.length?'revise-workflow':'approve-workflow';
  else if(!ws.domain)primary=ws.requirements_review?'prepare-test':'analyse';
  else if(!ws.dev_cases.length)primary='add-case';
  else if(!currentRun)primary='baseline';
 }else if(activeTab==='teach'&&ws&&!ws.frozen&&!recorded&&currentRun){
  primary=teaching?.approval_state==='DRAFT'?'approve-teaching':teaching?.approval_state==='APPROVED'?'replay':question?'propose':'ask';
 }else if(activeTab==='results'&&ws&&!ws.frozen&&!recorded&&currentRun)primary='next-teach';
 for(const id of ['new','upload','analyse','prepare-test','revise-workflow','approve-workflow','add-case','baseline','ask','propose','approve-teaching','replay','next-teach'])$(id)?.classList.toggle('primary-action',id===primary);
}

function renderRequirements(){
 const review=ws?.requirements_review,holder=$('requirements-review');holder.hidden=!review;
 if(!review){holder.innerHTML='';return;}
 const labels={purpose_scope:'Purpose and scope',required_information:'Required information',steps_operations:'Steps and operations',decision_conditions:'Conditions and reasons',exceptions_human_review:'Exceptions and human review',completion:'Completion'};
 const statuses={documented:'Documented',needs_clarification:'Needs clarification',not_provided:'Not provided'};
 const current=ws.sources.length===Object.keys(review.source_hashes).length&&ws.sources.every(s=>review.source_hashes[s.source_id]===s.version_hash)&&review.goal===ws.goal;
 holder.innerHTML='<h2>What needs clarifying?</h2><p>'+escapeText(review.summary)+'</p>'+(current?'':'<p class="warning">The materials changed. Organize the work again to update this review.</p>')+(review.questions.length?'<ol class="review-questions">'+review.questions.map(q=>'<li><strong>'+escapeText(q.question)+'</strong><p>'+escapeText(q.why_needed)+'</p><details><summary>Supporting material</summary>'+sourceReferences(q.source_refs,ws.sources)+'</details></li>').join('')+'</ol>':'<p>No clarification question was returned. This does not establish that the work can be automated.</p>')+'<details><summary>Review all six perspectives</summary>'+review.checks.map(c=>'<article><h3>'+escapeText(labels[c.aspect])+'</h3><p class="muted">'+escapeText(statuses[c.status])+'</p><p>'+escapeText(c.finding)+'</p>'+sourceReferences(c.source_refs,ws.sources)+'</article>').join('')+'</details>'+observationsGuide(review.observations,ws.domain,ws.sources)+'<button id="fix-review" class="secondary" '+(!current?'disabled':'')+'>Finalize this review</button> <button id="prepare-test" class="secondary" '+(!current||ws.frozen?'disabled':'')+'>Prepare a practice test</button><p class="muted">Draft test conditions for your approval. Findings alone do not prove that AI can complete the work.</p>';
 bind('fix-review',async()=>{await api('/history/fix',{workspace_id:ws.workspace_id,...recordPerson()});clearRecordNote();await refresh();notify('Review finalized. Its evidence, name, note and timestamp are saved in Decision history.');});
 bind('prepare-test',async()=>{notify('Drafting conditions for your review…');await api('/domains/draft',{workspace_id:ws.workspace_id,goal:ws.goal});await refresh();notify('Draft ready. Review the conditions before approving.');});
}

function caseInput(caseId,value){return (value.traces||[]).find(t=>t.payload?.case?.case_id===caseId)?.payload.case||(ws?.workspace_id===value.run.workspace_id?ws.dev_cases.find(c=>c.case_id===caseId):null);}
function caseSummary(c,fallback){return JTUiCopy.summary(c,fallback);}
function caseFacts(c,domain){return '<dl class="case-facts">'+Object.entries(c?.facts||{}).map(([id,value])=>`<div><dt>${escapeText(fieldLabel(domain,id))}</dt><dd>${escapeText(displayValue(value))}</dd></div>`).join('')+'</dl>';}
function renderCaseEditor(){
 const holder=$('case-editor');
 if(!ws||ws.sample){holder.innerHTML='';return;}
 if(!ws.domain){holder.innerHTML='<p class="muted">Approve the work and its conditions to add example cases.</p>';return;}
 if(ws.frozen||ws.run_ids.length){holder.innerHTML='<p class="muted">These cases are fixed so the before-and-after checks use the same inputs. Start a new check to use a different set.</p>';return;}
 const sameDraft=caseDraft?.workspace_id===ws.workspace_id;
 if(!sameDraft)caseDraft=null;
 if(caseEdits?.workspace_id!==ws.workspace_id)caseEdits=null;
 const control=(field,group,index)=>{const id=`case-${group}-${index}`;return `<div class="case-input"><label for="${id}">${escapeText(fieldLabel(ws.domain,field.field_id))}</label><p id="${id}-help" class="muted">${escapeText(JTUiCopy.field(ws.domain,field.field_id).description)}</p>${field.type==='boolean'?`<select id="${id}" aria-describedby="${id}-help"><option value="">Not supplied</option><option value="true">Yes</option><option value="false">No</option></select>`:`<input id="${id}" type="${field.type==='number'?'number':'text'}" ${field.type==='number'?'step="any"':''} aria-describedby="${id}-help" placeholder="Not supplied">`}</div>`;};
 holder.innerHTML=`<input id="case-file" class="native-file-input" tabindex="-1" aria-hidden="true" type="file" accept=".txt,.pdf,.png,.jpg,.jpeg,.mp4"><button id="read-case-file" class="secondary">Read a case file</button><p class="muted">Upload one case and its supporting evidence in a single file. Review the extracted facts before saving.</p>${caseDraft?'<p><strong>Read: '+escapeText(caseDraft.sources[0].name)+'</strong></p>':''}<details id="case-form" ${caseDraft?'open':''}><summary>${caseDraft?'Review the facts and starting state':'Or enter an example manually'}</summary><label for="case-description">Describe the situation</label><textarea id="case-description" rows="2" maxlength="4000" placeholder="What has happened, and what needs deciding?"></textarea><label for="case-kind">What kind of example is this?</label><select id="case-kind"><option value="normal">A routine case</option><option value="transfer">A case the instructions may not cover</option><option value="must_hold">A case that should wait for more information</option></select><h4>Facts about this case</h4><p class="muted">Blank means not supplied. Inferences and unresolved values are left blank.</p><div class="case-form-grid">${ws.domain.input_fields.map((f,i)=>control(f,'fact',i)).join('')}</div>${caseDraft?observationsGuide(caseDraft.observations,ws.domain,caseDraft.sources):''}<h4>Before any action</h4><p class="muted">Enter the case’s current state. These values are not chosen for you.</p><div class="case-form-grid">${ws.domain.state_fields.map((f,i)=>control(f,'state',i)).join('')}</div><button id="add-case" class="secondary">${caseDraft?'Confirm facts and save case':'Save this example case'}</button></details><p class="muted">Add up to 40 cases before the first test. The case kind does not supply a correct answer.</p>`;
 const vals=caseEdits||caseDraft?.case;
 if(vals){$('case-description').value=vals.raw_text||'';$('case-kind').value=vals.stratum||'normal';for(const [group,key,defs] of [['fact','facts',ws.domain.input_fields],['state','initial_state',ws.domain.state_fields]])defs.forEach((f,i)=>{$(`case-${group}-${i}`).value=vals[key]?.[f.field_id]??'';});}
 const read=(fields,group,validate=true)=>Object.fromEntries(fields.map((f,i)=>{const input=$(`case-${group}-${i}`),raw=input.value.trim();let value=raw===''?null:f.type==='boolean'?raw==='true':f.type==='number'?Number(raw):raw;if(validate&&(input.validity?.badInput||f.type==='number'&&value!==null&&!Number.isFinite(value)))throw Error('Enter a number for '+fieldLabel(ws.domain,f.field_id)+'.');return [f.field_id,value];}));
 const remember=()=>{caseEdits={workspace_id:ws.workspace_id,raw_text:$('case-description').value,stratum:$('case-kind').value,facts:read(ws.domain.input_fields,'fact',false),initial_state:read(ws.domain.state_fields,'state',false)};};
 holder.querySelectorAll('input:not([type=file]),select,textarea').forEach(el=>el.addEventListener('input',remember));
 $('read-case-file').onclick=()=>{if(!busy&&!cancelRequest)$('case-file').click();};
 $('case-file').onchange=()=>{const file=$('case-file').files[0];if(!file)return;return action(async()=>{const data=new FormData();data.append('workspace_id',ws.workspace_id);data.append('file',file);data.append('stratum',$('case-kind').value);notify('Reading the case file…');const result=await api('/cases/read',data);caseDraft=result;caseEdits=null;renderCaseEditor();notify('Read complete. Check each fact, its evidence and the starting state, then confirm the case.');});};
 bind('add-case',async()=>{
  const description=$('case-description').value.trim();if(!description)throw Error('Describe the situation for this example case.');
  const c={case_id:caseDraft?.case.case_id||'case_'+crypto.randomUUID().replaceAll('-',''),domain_id:ws.domain.domain_id,split:'dev',stratum:$('case-kind').value,facts:read(ws.domain.input_fields,'fact'),raw_text:description,initial_state:read(ws.domain.state_fields,'state')};
  if(caseDraft)await api('/cases/confirm',{workspace_id:ws.workspace_id,case_draft_id:caseDraft.case_draft_id,case:c,...recordPerson()});
  else await api('/cases/import',{workspace_id:ws.workspace_id,cases:[c],append:true,...recordPerson()});
  caseDraft=null;caseEdits=null;clearRecordNote();await refresh();notify('Case saved. Add another, or try the original instructions.');
 });
}
function renderWorkspace(preserveInputs=false){
 const enteredGoal=$('goal').value;
 if(displayedWorkspace!==ws.workspace_id){resetWorkspaceView(preserveInputs);displayedWorkspace=ws.workspace_id;}
 $('mode').textContent=modeLabel(ws.mode)+(admin?' · Administrator':'');$('mode').classList.toggle('mock',ws.mode==='MOCK');
 $('source-editor').hidden=false;$('workspace-label').textContent=(ws.sample?'Fictional example':'Your own work')+' · '+(ws.status==='STALE'?'Instructions changed':ws.version<0?'Conditions awaiting approval':'Approved conditions, version '+ws.version);
 $('admin-workspace').textContent=admin?'Workspace ID for the runbook: '+ws.workspace_id:'';$('goal').value=preserveInputs?enteredGoal:ws.goal;
 $('source-list').innerHTML=ws.sources.map(s=>`<li><strong>${escapeText(s.name)}</strong> <span class="muted">${(s.size/1024).toFixed(1)} KiB</span><details><summary>File details</summary><p class="muted">${escapeText(s.mime)}<br>Source: ${escapeText(s.source_id)}<br>Content hash: ${escapeText(s.version_hash)}</p></details></li>`).join('');
 $('stale').hidden=ws.status!=='STALE';const isDraft=Boolean(ws.draft&&ws.draft.base_version===ws.version),d=isDraft?ws.draft.domain:ws.domain;
 const inputIssues=isDraft?(ws.draft.input_review_issues||[]):[];
 $('approve-workflow').hidden=!isDraft||inputIssues.length>0;
 $('revise-workflow').hidden=!isDraft||!inputIssues.length;
 if(d){$('workflow').innerHTML=(inputIssues.length?'<div class="guide-stop"><h3>Revise these inputs first</h3>'+inputIssues.map(x=>'<p>'+escapeText(x.message)+'</p>').join('')+'</div>':'')+workflowGuide(d,isDraft);$('domain-json').value=JSON.stringify(d,null,2);}else{$('workflow').textContent='Add instructions and organize them to create a guide for review.';$('domain-json').value='';}
 $('observations').innerHTML=observationsGuide(ws.draft?.observations,d,ws.sources||[]);
 $('dev-cases').innerHTML='<p class="muted">'+ws.dev_cases.length+' example cases ready.</p>'+ws.dev_cases.map((c,i)=>`<details><summary>Case ${i+1}: ${escapeText(caseSummary(c,'Example case'))}</summary>${caseFacts(c,d)}<p><strong>Starting state:</strong> ${escapeText(stateDescription(c.initial_state,d))}</p><details><summary>Original case data</summary><pre>${escapeText(JSON.stringify(c,null,2))}</pre></details></details>`).join('');
 question=ws.questions.at(-1)?.question||null;teaching=ws.teachings.at(-1)?.teaching||null;renderTeaching();renderRequirements();renderCaseEditor();updateNextStep();
 sessionStorage.setItem('jt-workspace',ws.workspace_id);$('saved-work').hidden=true;
}
function resetWorkspaceView(preserveInputs=false){currentRun=beforeRun=afterRun=question=teaching=null;savedRuns=[];verifiedComparison=null;$('saved-tests').hidden=true;recorded=false;stopRequested=false;displayedWorkspace=null;caseDraft=null;caseEdits=null;$('history-list').innerHTML='';$('history-comparison').innerHTML='';$('requirements-review').hidden=true;$('answer').value='';$('cases-json').value='';if(!preserveInputs){$('goal').value='';$('file').value='';$('initial-explanation').value='';syncUploadControl();}$('source-list').innerHTML='';$('dev-cases').innerHTML='';$('stale').hidden=true;$('recorded').value='';$('run-status').textContent='';$('comparison').innerHTML='';$('results-table').innerHTML='';sessionStorage.removeItem('jt-run');renderTeaching();}
function renderTeaching(){
 const hasExample=Boolean(ws?.sample&&ws.example_answer);$('example').hidden=!hasExample;$('example-note').hidden=!hasExample;
 $('question').innerHTML=question?`<h3>${escapeText(question.text)}</h3><p>${escapeText(question.why_needed)}</p><details><summary>Cases behind this question</summary>${question.affected_dev_case_ids.map((id,i)=>`<p>${escapeText(caseSummary(ws?.dev_cases.find(c=>c.case_id===id),'Example case '+(i+1)))}</p>`).join('')}</details>`:'<p>First try the original instructions in step 1. Then find a case that needs your explanation.</p>';
 $('rules').innerHTML=teaching?`<h3>Your explanation</h3><blockquote>${escapeText(teaching.human_text)}</blockquote><h3>Guidance to review</h3>${renderRules(teaching.proposed_rules)}`:'<p>Your proposed guidance will appear here. Nothing changes until you approve it.</p>';
 $('approve-teaching').hidden=!teaching||teaching.approval_state!=='DRAFT';updateNextStep();
}
async function refresh(preserveInputs=false){if(ws){ws=await api('/workspaces/'+ws.workspace_id,null,'GET');renderWorkspace(preserveInputs);await loadSavedTests();}}
async function loadSavedTests(){
 savedRuns=await Promise.all((ws?.run_ids||[]).map(id=>api('/runs/'+id,null,'GET')));
 $('saved-tests').hidden=!savedRuns.length;
 $('saved-test').innerHTML=[...savedRuns].reverse().map(v=>`<option value="${escapeText(v.run.run_id)}">${v.run.split==='holdout'?'New cases':v.run.domain.version===0?'Before the explanation':'After the explanation'} · v${v.run.domain.version} · ${v.metrics.counts.COMPLETED}/${v.metrics.total} complete${v.metrics.counts.FAILED?' · stopped':''}</option>`).join('');
}
async function openSavedTest(id){
 const value=savedRuns.find(v=>v.run.run_id===id)||await api('/runs/'+id,null,'GET');
 beforeRun=afterRun=null;verifiedComparison=null;
 if(value.run.arm==='C_JT_RULES'&&value.run.domain.version>0&&value.run.split==='dev'){
  const candidates=[...savedRuns].reverse().filter(v=>v.run.split==='dev'&&v.run.domain.version<value.run.domain.version&&v.metrics.complete);
  for(const candidate of candidates){
   const check=await api('/comparisons/'+candidate.run.run_id+'/'+id,null,'GET');
   if(check.comparable){beforeRun=candidate;afterRun=value;verifiedComparison=check;break;}
  }
 }
 currentRun=id;recorded=false;sessionStorage.setItem('jt-run',id);$('saved-test').value=id;showRun(value);tab('results');
}
bind('open-saved-test',async()=>{const id=$('saved-test').value;await loadSavedTests();await openSavedTest(id);notify('Saved test opened. No AI request was made.');});
async function ensureWorkspace(){if(!ws){ws=await api('/workspaces',{goal:$('goal').value});renderWorkspace(true);}return ws;}
function syncUploadControl(){const file=$('file').files[0];$('upload').textContent=file?'Retry upload':'Upload file';$('upload-status').textContent=file?'Not saved: '+file.name:'';$('replace-upload').hidden=!file;}
async function saveFile(file){
 try{await ensureWorkspace();const data=new FormData();data.append('workspace_id',ws.workspace_id);data.append('file',file);
 await api('/sources',data);$('file').value='';await refresh(true);}finally{syncUploadControl();}
}
async function saveExplanation(text){
 await ensureWorkspace();const data=new FormData();data.append('workspace_id',ws.workspace_id);data.append('file',new Blob([text],{type:'text/plain'}),'task-owner-explanation.txt');
 await api('/sources',data);if($('initial-explanation').value===text)$('initial-explanation').value='';await refresh(true);
}
async function create(sample){ws=await api('/workspaces',sample?{sample}:{});currentRun=beforeRun=afterRun=null;recorded=false;renderWorkspace();tab('sources');notify(sample?'Review the work and its conditions, then approve the conditions if they match the example instructions.':'Describe the job and add the instructions you use today.');}
bind('sample-invoice',()=>create('invoice_routing'));bind('sample-support',()=>create('support_triage'));bind('new',()=>create());
bind('sample-expense',async()=>{const response=await fetch('/assets/samples/expense_policy.txt');if(!response.ok)throw Error('The sample instructions could not be loaded.');const text=await response.text();await create();$('goal').value='Check business-trip accommodation reimbursement documents before a person gives business approval.';await saveFile(new File([text],'expense_policy.txt',{type:'text/plain'}));notify('Sample instructions added. Download the sample files, then organize the work. No AI result or approval has been created.');});
bind('download-expense',async()=>{const response=await fetch('/assets/samples/expense_files.json');if(!response.ok)throw Error('The sample files could not be loaded.');const data=await response.json(),bytes=Uint8Array.from(atob(data.base64),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:data.mime})),a=document.createElement('a');a.href=url;a.download=data.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Sample files downloaded. Start with the four development cases; keep the other two for a separate check.');});
$('open-recorded').onclick=()=>{if(!busy&&!cancelRequest)$('recorded').click();};

bind('continue-saved',async()=>{
 if(!savedWork)throw Error('There is no saved work linked to this tab. Start a new check above.');
 const {workspaceId,runId}=savedWork;ws=await api('/workspaces/'+workspaceId,null,'GET');recorded=false;renderWorkspace();
 await loadSavedTests();if(runId&&ws.run_ids.includes(runId))await openSavedTest(runId);
 tab('sources');notify('Saved work opened. Review the instructions and results before choosing what to do next. No case has been started.');
});
function uploadSelectedFile(){const file=$('file').files[0];if(!file){syncUploadControl();return;}return action(async()=>{await saveFile(file);notify('File saved. Add more information or organize the work.');});}
$('upload').onclick=()=>{if(busy||cancelRequest)return;return $('file').files[0]?uploadSelectedFile():$('file').click();};
$('replace-upload').onclick=()=>{if(!busy&&!cancelRequest)$('file').click();};
$('file').onchange=uploadSelectedFile;
bind('add-explanation',async()=>{const text=$('initial-explanation').value;if(!text.trim())throw Error('Enter an explanation or comment to add.');await saveExplanation(text);notify('Explanation saved as a text file. It is not approved guidance yet.');});
bind('analyse',async()=>{
 const file=$('file').files[0],text=$('initial-explanation').value,goal=$('goal').value;
 if(!file&&!text.trim()&&!ws?.sources.length)throw Error('Add a file or explanation first.');
 await ensureWorkspace();if(file)await saveFile(file);if(text.trim())await saveExplanation(text);
 notify('Reviewing your materials and explanation…');await api('/requirements/review',{workspace_id:ws.workspace_id,goal});await refresh();notify('Review ready. Read the questions, add any missing explanation, or prepare a practice test.');
});
bind('save-domain',async()=>{await api('/domains/draft',{workspace_id:ws.workspace_id,domain:JSON.parse($('domain-json').value)});await refresh();notify('Edited conditions saved as a draft. Review them before approving.');});
bind('revise-workflow',async()=>{notify('Revising the flagged inputs from your sources…');await api('/domains/draft',{workspace_id:ws.workspace_id,revise_draft_id:ws.draft.draft_id});await refresh();notify(ws.draft.input_review_issues?.length?'The revised draft still needs correction. Review the flagged inputs.':'Revised draft saved. Review all conditions before approving.');});
bind('approve-workflow',async()=>{await api('/domains/approve',{draft_id:ws.draft.draft_id,base_version:ws.version,...recordPerson()});clearRecordNote();await refresh();notify('Conditions approved. Try the original instructions on the example cases.');});
bind('import-cases',async()=>{await api('/cases/import',{workspace_id:ws.workspace_id,cases:JSON.parse($('cases-json').value),...recordPerson()});clearRecordNote();await refresh();notify('Cases imported.');});
bind('rollback',async()=>{await api('/domains/rollback',{workspace_id:ws.workspace_id,target_version:Number($('rollback-version').value),base_version:ws.version,...recordPerson()});clearRecordNote();await refresh();notify('The earlier guidance is now saved as a new approved version.');});
async function run(arm){if(!ws||ws.version<0)throw Error('Review and approve the work and its conditions in step 1 first.');recorded=false;const r=await api('/runs',{workspace_id:ws.workspace_id,arm,split:'dev',repeats:1,...recordPerson(),case_ids:ws.dev_cases.map(c=>c.case_id)});currentRun=r.run_id;sessionStorage.setItem('jt-run',currentRun);tab('results');return executeRun();}
function guidedCases(){return ['normal','transfer','must_hold'].flatMap(s=>ws.dev_cases.filter(c=>c.stratum===s).slice(0,1).map(c=>c.case_id));}
async function executeRun(){
 stopRequested=false;executingRun=true;$('cancel').disabled=false;
 try{
 for(let i=0;i<40;i++){
  const state=await api('/runs/'+currentRun,null,'GET');showRun(state);
  if(stopRequested){if(cancelRequest)await cancelRequest;return {status:'stopped'};}
  if(state.run.cancelled){notify('Testing stopped. Saved results remain available; no new case will start.');return {status:'stopped'};}
  if(state.metrics.complete){const failed=state.metrics.counts.FAILED;notify(failed?'Testing ended, but some cases could not complete. Review their saved results.':'Testing finished. Review each case to see what AI did and what needs a person’s attention.',Boolean(failed));return {status:failed?'failed':'completed'};}
  notify('Processing one case · '+(state.metrics.counts.COMPLETED+state.metrics.counts.FAILED+state.metrics.counts.CANCELLED)+'/'+state.metrics.total+' finished. Waiting for its saved result; you can stop new cases.');
  let step;
  try{step=await api('/runs/'+currentRun+'/step',{});}
  catch(error){try{showRun(await api('/runs/'+currentRun,null,'GET'));}catch(refreshError){error.message+=' The latest saved status could not be loaded. Reopen your saved work before continuing.';}throw error;}
  if(stopRequested){if(cancelRequest)await cancelRequest;showRun(await api('/runs/'+currentRun,null,'GET'));return {status:'stopped'};}
  if(step.failed){const state=await api('/runs/'+currentRun,null,'GET');showRun(state);const error=serviceError(step.error,200,'/runs/'+currentRun+'/step');notify('This case did not complete. Review the saved result. You can continue cases that have not been processed.',true,error.details);return {status:'failed'};}
  if(step.done===false){notify('A case is already running. Use Continue remaining cases after it finishes.');return {status:'pending'};}
 }
 notify('Progress saved. Use Continue remaining cases to continue.');return {status:'pending'};
 }finally{executingRun=false;if(busy)$('cancel').disabled=true;}
}
bind('baseline',()=>run('A_SOURCE_ONLY'));bind('replay',()=>run('C_JT_RULES'));bind('resume',async()=>{if(!currentRun||recorded)throw Error('Open a saved test in this application first. Imported result files can only be read.');return executeRun();});
$('cancel').onclick=async()=>{
 if(cancelRequest||busy&&!executingRun)return;
 if(!currentRun||recorded){notify('There is no active test to stop.',true);return;}
 stopRequested=true;$('cancel').disabled=true;const rid=currentRun;
 notify('Stop requested. This tab will start no further cases. An already running case may finish; waiting for server confirmation.');
 cancelRequest=(async()=>{try{await api('/runs/'+rid+'/cancel',{});notify('Stop confirmed. A case already underway may finish; no new case will start.');showRun(await api('/runs/'+rid,null,'GET'));return {status:'stopped'};}
 catch(e){notifyError(e,'Automatic processing stopped in this tab, but the server stop could not be confirmed. A case already underway may finish. ');return {status:'stopped'};}})();
 try{return await cancelRequest;}finally{cancelRequest=null;$('cancel').disabled=busy;}
};
bind('ask',async()=>{if(!currentRun||recorded)throw Error('Try the original instructions in step 1 first.');const q=await api('/questions',{run_id:currentRun});question=q.question;renderTeaching();notify('Answer the question, then review the guidance drafted from your explanation.');});
bind('example',async()=>{if(!ws?.sample||!ws.example_answer)throw Error('Write an explanation for your own work. Supplied explanations belong only to the fictional examples.');$('answer').value=ws.example_answer;notify('This sample’s explanation is inserted. Check it against the fictional example before submitting.');});
bind('propose',async()=>{if(!question)throw Error('Choose “Find what needs explaining” first.');notify('Drafting guidance from your explanation for you to review…');const t=await api('/teachings',{question_id:question.question_id,human_text:$('answer').value});teaching=t.teaching;renderTeaching();notify('Draft ready. Read the conditions and action, then approve them if they match your judgment.');});
bind('approve-teaching',async()=>{await api('/teachings/'+teaching.teaching_id+'/approve',{base_version:teaching.base_domain_version,...recordPerson()});clearRecordNote();await refresh();notify('Guidance approved. Try the same example cases again from their original starting points.');});
bind('next-teach',async()=>{if(recorded)throw Error('This imported result is read-only. Open or create work in step 1 to add an explanation.');tab('teach');});
function percent(v){return v===null?'Unlabelled':(v*100).toFixed(1)+'%';}
function comparableRuns(a,b){
 if(!a||!b)return false;
 if(verifiedComparison?.comparable&&verifiedComparison.before_run_id===a.run.run_id&&verifiedComparison.after_run_id===b.run.run_id)return true;
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
 if(!receipts.length)return {title:'Result not verified',next:'There is no saved confirmation of an action. Inspect the result details.',kind:'failed'};
 if(task.decision?.outcome==='HOLD')return {title:'Waiting for review',next:task.decision.missing_fields?.length?'Information needed: '+task.decision.missing_fields.map(id=>fieldLabel(domain,id)).join(', ')+'.':'Check the explanation: more information or permission is needed before proceeding.',kind:'held'};
 if(task.score?.labelled&&task.score.correct===false)return {title:'Action needs review',next:'The saved action did not match the expected result for this case. Check the explanation before using this guidance.',kind:'review'};
 return {title:actionDescription(domain,task.decision?.action_id),next:task.score?.labelled&&task.score.correct?'The saved action matches the expected result for this case.':'The action was saved. No expected-answer check is available; a person must verify it.',kind:'done'};
}
function taskEvidence(t,value){
 const domain=value.run.domain,receipts=(value.receipts||[]).filter(r=>(t.receipt_ids||[]).includes(r.receipt_id));
 const traces=(value.traces||[]).filter(r=>(t.trace_ids||[]).includes(r.trace_id));
 const rules=(t.decision?.rule_ids||[]).map(id=>domain?.rules?.find(rule=>rule.rule_id===id)?.statement||humanize(id));
 const c=caseInput(t.case_id,value);
 return '<p>'+escapeText(t.status==='FAILED'&&t.error?(t.error.code==='INTERNAL_ERROR'?'This case did not complete. Review the saved details. Only unprocessed cases can be continued.':serviceError(t.error).message):t.decision?.explanation||'A final explanation is not available yet.')+'</p>'+(t.decision?'<h4>Source evidence</h4>'+sourceReferences(t.decision.source_refs,value.source_metadata||ws?.sources||[]):'')+(c?'<h4>Information used</h4>'+caseFacts(c,domain):'')+(rules.length?'<h4>Guidance used</h4>'+rules.map(rule=>'<p>'+escapeText(rule)+'</p>').join(''):'<p>No approved action rule is cited for this result.</p>')+receipts.map(r=>'<div class="receipt"><strong>Saved change in this practice case</strong><p>Before: '+escapeText(stateDescription(r.before_state,domain))+'</p><p>After: '+escapeText(stateDescription(r.after_state,domain))+'</p><p class="muted">'+escapeText(r.committed_at)+'</p></div>').join('')+(!(t.receipt_ids||[]).length?'<p>There is no saved confirmation of an action. No completed change is verified here.</p>':!receipts.length?'<p>A saved change is referenced. Open these details while connected to load the full record.</p>':'')+'<details><summary>Original decision, receipts and technical details</summary><pre>'+escapeText(JSON.stringify({case_id:t.case_id,status:t.status,error:t.error||null,proposed:t.raw_decision,applied:t.decision,state:t.state,receipt_ids:t.receipt_ids,receipts,traces:traces.map(x=>({trace_id:x.trace_id,elapsed_ms:x.elapsed_ms,attempts:x.attempts,error:x.error}))},null,2))+'</pre></details>';
}
function showRun(value){
 const r=value.run,m=value.metrics;$('resume').hidden=!currentRun||recorded||m.complete||r.code_hash!==activeCodeHash;$('cancel').hidden=!currentRun||recorded||m.complete||r.code_hash!==activeCodeHash;$('next-teach').hidden=Boolean(ws?.frozen)||recorded;$('download').hidden=!currentRun||recorded;$('fix-result').hidden=!currentRun||recorded||!m.complete;if(r.arm==='A_SOURCE_ONLY'||r.arm==='C_JT_RULES'&&r.domain.version===0)beforeRun=value;if(r.arm==='C_JT_RULES'&&r.domain.version>0)afterRun=value;
 const armNames={A_SOURCE_ONLY:'Original instructions',B_TEXT_ADDED:'Instructions and task owner’s explanation',C_JT_RULES:'Instructions and approved guidance'};
 $('run-status').textContent=`${recorded?'Recorded result · ':''}${armNames[r.arm]||humanize(r.arm)} · ${m.counts.COMPLETED} of ${m.total} cases finished${m.counts.FAILED?' · '+m.counts.FAILED+' could not complete':''}${m.counts.CANCELLED?' · '+m.counts.CANCELLED+' stopped':''}${r.cancelled?' · Processing stopped (a case already underway may still finish)':''}${m.stale?' · Instructions have changed since this test':''}`;
 const comparable=comparableRuns(beforeRun,afterRun);
 const outcomes=value.tasks.map(t=>taskOutcome(t,r.domain));
 const count=kind=>outcomes.filter(x=>x.kind===kind).length;
 const missing=value.tasks.filter((t,i)=>outcomes[i].kind==='held'&&t.decision?.missing_fields?.length).length;
 $('comparison').innerHTML=[['AI proceeded',count('done'),'An action was saved in the tested case. Check its result and supporting evidence.'],['Information to clarify',missing,'Supply the listed missing information, then test the case again.'],['Needs a person’s review',count('held')-missing+count('review'),'Check why the case stopped, or why the saved action needs correction.'],['Not verified',count('pending')+count('failed'),'These cases have no verified result. Technical failures are shown separately in each case.']].map(([label,n,detail])=>`<div class="metric"><div class="metric-heading"><span class="metric-label">${label}</span><strong>${n}</strong></div><span>${detail}</span></div>`).join('');
 if(r.mode==='MOCK')$('comparison').innerHTML+='<p class="warning">Simulation mode. These are simulated outcomes, not measured AI performance.</p>';
 const reviewNote=comparable&&verifiedComparison?.code_review?'<p class="muted">'+escapeText(verifiedComparison.code_review)+'</p>':'';
 const scores=[['This test',value],...(comparable?[['Before the explanation',beforeRun],['With the approved guidance',afterRun]]:[])];
 const scoreDetails=`<details id="measured-scores" class="score-details"><summary>Measured scores and test details</summary><p>A correct hold is a correct decision, but not an autonomous completion. Correctness rates require an expected answer for each case.</p><div class="scroll"><table><thead><tr><th>Test</th><th>Correct autonomous completion</th><th>Correct decisions, including hold</th><th>Critical errors</th><th>Task owner’s supplements</th><th>Tokens used</th><th>AI processing time</th></tr></thead><tbody>${measurementRows(scores)}</tbody></table></div><p class="muted">Supplements count approved explanations. Tokens include recorded input, output and thinking tokens, including retries. AI time totals the recorded decision calls. Preparation and time spent by people are separate.</p>${!Array.isArray(value.traces)&&!recorded?'<button id="load-measurements" class="secondary">Load token usage from the saved record</button>':''}<p class="muted">${m.total} case attempts / ${m.unique_cases} unique cases · ${m.holds} holds · ${m.counts.FAILED} technical failures</p>${beforeRun&&afterRun&&!comparable?'<p class="warning">No before/after score comparison: both runs must be complete and use the same cases, repeats, model settings and code, with unchanged source evidence.</p>':''}${comparable&&(beforeRun.metrics.counts.FAILED||afterRun.metrics.counts.FAILED||beforeRun.metrics.counts.CANCELLED||afterRun.metrics.counts.CANCELLED)?'<p class="warning">Technical failures remain in these rates. The difference alone does not establish a teaching benefit.</p>':''}${reviewNote}<p class="muted">Mode: ${escapeText(r.mode)} · Model: ${escapeText(r.model_settings?.model||'not recorded')} · Rule version: ${escapeText(r.domain?.version??'not recorded')} · Started: ${escapeText(r.created_at||'not recorded')}</p><details><summary>Original metrics and run identifiers</summary><pre>${escapeText(JSON.stringify({run_id:r.run_id,arm:r.arm,code_hash:r.code_hash,model_settings:r.model_settings,metrics:m},null,2))}</pre></details></details>`;
 $('results-table').innerHTML='<div class="case-table-wrap"><table class="case-results" role="table"><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Case</th><th scope="col" role="columnheader">What happened</th><th scope="col" role="columnheader">What to do next</th></tr></thead><tbody role="rowgroup">'+value.tasks.map((t,i)=>{const outcome=outcomes[i],c=caseInput(t.case_id,value),caseNumber=r.case_ids.indexOf(t.case_id)+1,previous=comparable&&r.arm==='C_JT_RULES'?beforeRun.tasks.find(x=>x.case_id===t.case_id&&x.repeat===t.repeat):null;return `<tr role="row"><td role="cell" data-label="Case"><strong>Case ${caseNumber}</strong>${c?'<p>'+escapeText(caseSummary(c,'Example case'))+'</p>':''}${r.repeats>1?'<span class="muted">Repeat '+escapeText(t.repeat)+'</span>':''}</td><td role="cell" data-label="What happened"><span class="result-pill ${outcome.kind}">${escapeText(outcome.title)}</span>${previous?'<p class="before-outcome"><strong>Before the explanation:</strong> '+escapeText(taskOutcome(previous,beforeRun.run.domain).title)+'</p>':''}<p class="muted">${(t.receipt_ids||[]).length?'Saved result: ':'Current case status: '}${escapeText(stateDescription(t.state,r.domain))}</p></td><td role="cell" data-label="What to do next"><p>${escapeText(outcome.next)}</p><details data-task="${escapeText(t.task_id)}"><summary>Why this happened and what changed</summary>${taskEvidence(t,value)}</details></td></tr>`;}).join('')+'</tbody></table></div>'+scoreDetails;
 if($('load-measurements'))bind('load-measurements',async()=>{const items=[...new Map(scores.map(([,v])=>[v.run.run_id,v])).values()];const loaded=await Promise.all(items.map(v=>Array.isArray(v.traces)?v:api('/exports/'+v.run.run_id,null,'GET')));for(const full of loaded){if(full.run.arm==='A_SOURCE_ONLY'||full.run.arm==='C_JT_RULES'&&full.run.domain.version===0)beforeRun=full;if(full.run.arm==='C_JT_RULES'&&full.run.domain.version>0)afterRun=full;}showRun(loaded.find(v=>v.run.run_id===r.run_id));$('measured-scores').open=true;notify('Recorded token usage loaded. No AI request was made.');});
 let exported=null;
 if(!value.receipts&&!recorded)$('results-table').querySelectorAll('details[data-task]').forEach(details=>{details.addEventListener('toggle',async()=>{if(!details.open||details.dataset.loaded)return;details.dataset.loaded='loading';try{exported=exported||api('/exports/'+r.run_id,null,'GET');const full=await exported;const task=full.tasks.find(t=>t.task_id===details.dataset.task);details.innerHTML='<summary>Why this happened and what changed</summary>'+taskEvidence(task,full);details.dataset.loaded='true';}catch(e){details.dataset.loaded='';exported=null;const p=document.createElement('p');p.textContent='The saved change could not be loaded. '+e.message;details.append(p);if(e.details){const technical=document.createElement('details');technical.innerHTML='<summary>Technical details for support</summary><pre>'+escapeText(JSON.stringify(e.details,null,2))+'</pre>';details.append(technical);}}});});
 updateNextStep();
}
function recordPerson(){const name=$('reviewer-name').value.trim();if(!name){$('reviewer-name').focus?.();$('reviewer-name').scrollIntoView?.({block:'center'});throw Error('Enter the responsible person’s name before finalizing this record.');}return {reviewer_name:name,memo:$('record-memo').value};}
function clearRecordNote(){$('record-memo').value='';$('history-list').innerHTML='';$('history-comparison').innerHTML='';}
const historyKinds={requirements_review:'Requirements review',workflow_approval:'Conditions approved',workflow_reuse:'Earlier conditions reused',case_confirmation:'Case facts confirmed',manual_case_change:'Case data confirmed',teaching_approval:'Explanation approved',evaluation_lock:'Evaluation locked',test_result:'Test result finalized'};
function fixedRecordView(record){
 const s=record.snapshot,heading='<p class="muted">'+escapeText(historyKinds[record.kind]||humanize(record.kind))+' · '+escapeText(record.reviewer_name)+' · '+escapeText(record.recorded_at)+'</p>'+(record.memo?'<blockquote>'+escapeText(record.memo)+'</blockquote>':'');
 let body='';
 if(s.checks)body='<p>'+escapeText(s.summary)+'</p>'+s.checks.map(c=>'<h4>'+escapeText(humanize(c.aspect))+'</h4><p>'+escapeText(c.finding)+'</p>'+sourceReferences(c.source_refs,record.source_metadata)).join('');
 else if(s.domain)body='<h3>'+escapeText(s.domain.title)+'</h3><p>'+escapeText(s.domain.goal)+'</p>'+renderRules(s.domain.rules,s.domain);
 else if(s.case)body='<p>'+escapeText(s.case.raw_text)+'</p>'+caseFacts(s.case,{input_fields:s.input_fields||[],state_fields:[]});
 else if(s.cases)body=s.cases.map(c=>'<p>'+escapeText(c.raw_text)+'</p>'+caseFacts(c,{input_fields:s.input_fields||[],state_fields:[]})).join('');
 else if(s.metrics)body='<p>'+escapeText(s.metrics.counts.COMPLETED)+' completed · '+escapeText(s.metrics.counts.FAILED)+' technical failures · '+escapeText(s.metrics.holds)+' held for review</p>'+s.tasks.map(t=>'<h4>'+escapeText(t.case_id)+'</h4><p>'+escapeText(t.decision?.explanation||t.status)+'</p>').join('');
 else body='<p>Evaluation settings and evidence versions were finalized.</p>';
 const files=record.source_metadata.map(src=>'<li><button class="text-button" data-history-source="'+escapeText(src.source_id)+'" data-history-record="'+escapeText(record.record_id)+'" data-source-name="'+escapeText(src.name)+'">'+escapeText(src.name)+'</button></li>').join('');
 return heading+body+'<details><summary>Evidence and original record</summary><ul>'+files+'</ul><p>Record hash: '+escapeText(record.record_hash)+'</p><pre>'+escapeText(JSON.stringify(record,null,2))+'</pre></details>';
}
function bindHistorySources(){document.querySelectorAll('[data-history-source]').forEach(button=>{button.onclick=()=>action(async()=>{const path='/api/v1/history/'+encodeURIComponent(button.dataset.historyRecord)+'/sources/'+encodeURIComponent(button.dataset.historySource),response=await fetch(path,{credentials:'same-origin',headers:admin?{'X-JT-Admin':admin}:{}});if(!response.ok)throw Error('The original evidence file could not be opened.');const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=button.dataset.sourceName;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Original evidence downloaded from the finalized record.');});});}
async function loadHistory(){
 if(!ws)throw Error('Open a workspace first.');const {records}=await api('/workspaces/'+ws.workspace_id+'/history',null,'GET');
 $('history-comparison').innerHTML='';
 if(!records.length){$('history-list').textContent='No finalized records in this workspace.';return;}
 const opts=records.map(r=>'<option value="'+escapeText(r.record_id)+'">'+escapeText((historyKinds[r.kind]||r.kind)+' · '+r.reviewer_name+' · '+r.recorded_at)+'</option>').join('');
 $('history-list').innerHTML='<label for="history-current">Record</label><select id="history-current">'+opts+'</select><label for="history-previous">Compare with (optional)</label><select id="history-previous"><option value="">No comparison</option>'+opts+'</select><div class="history-actions"><button id="compare-history" class="secondary">Read selected records</button><button id="delete-history" class="text-button danger">Delete selected record</button><button id="reset-history" class="text-button danger">Reset history</button></div>';
 bind('compare-history',async()=>{const left=await api('/history/'+$('history-current').value,null,'GET');const previous=$('history-previous').value;const right=previous?await api('/history/'+previous,null,'GET'):null;$('history-comparison').innerHTML='<div class="history-compare '+(right?'two-records':'')+'"><article>'+fixedRecordView(left)+'</article>'+(right?'<article>'+fixedRecordView(right)+'</article>':'')+'</div>';bindHistorySources();notify('Finalized records opened. No evidence, decision or AI result has been changed.');});
 bind('delete-history',async()=>{
  const selected=records.find(r=>r.record_id===$('history-current').value);if(!selected)throw Error('Select a record first.');
  if(!window.confirm('Delete this finalized record?\n\n'+(historyKinds[selected.kind]||humanize(selected.kind))+' · '+selected.reviewer_name+'\n'+selected.recorded_at+'\n\nThis cannot be undone. Current materials, approved conditions and test results will remain.'))return;
  await api('/history/delete',{workspace_id:ws.workspace_id,record_id:selected.record_id,confirmed:true});await loadHistory();notify('The selected history record was deleted.');
 });
 bind('reset-history',async()=>{
  if(!window.confirm('Delete all '+records.length+' finalized records in this workspace?\n\nThis cannot be undone. Current materials, approved conditions and test results will remain.'))return;
  await api('/history/reset',{workspace_id:ws.workspace_id,record_ids:records.map(r=>r.record_id),confirmed:true});await loadHistory();notify('Decision history was reset for this workspace.');
 });
}
bind('load-history',loadHistory);
bind('fix-result',async()=>{if(!currentRun||recorded)throw Error('Open a completed test in this application first.');await api('/history/fix',{run_id:currentRun,...recordPerson()});clearRecordNote();await refresh();notify('Result finalized with its responsible person, note, timestamp and original evidence.');});
bind('download',async()=>{if(!currentRun||recorded)throw Error('Open a saved test in this application to download its full result.');const value=await api('/exports/'+currentRun,null,'GET');const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=currentRun+'.json';a.click();URL.revokeObjectURL(url);});
$('recorded').onchange=()=>action(async()=>{const file=$('recorded').files[0];if(!file||file.size>20*1024*1024)throw Error('Choose an exported result file (.json) under 20 MiB.');const value=JSON.parse(await file.text());if(value.export_version!=='1.0'||!value.run||!value.metrics||!Array.isArray(value.tasks))throw Error('This is not a Judgment Transfer export.');recorded=true;beforeRun=afterRun=null;currentRun=null;$('mode').textContent='Saved result · '+modeLabel(value.run.mode);showRun(value);notify('Saved result opened for reading. No AI request was made.');});
bind('admin-login',async()=>{admin=$('admin-token').value;$('admin-token').value='';await sessionInfo();ws=null;resetWorkspaceView();$('source-editor').hidden=false;$('workspace-label').textContent='';$('admin-workspace').textContent='';sessionStorage.removeItem('jt-workspace');notify('Administrator access enabled for this tab. Create or reopen an evaluation workspace.');});
bind('open-workspace',async()=>{const id=$('open-workspace-id').value.trim();if(!/^ws_[a-f0-9]{32}$/.test(id))throw Error('Enter the saved Workspace ID.');ws=await api('/workspaces/'+id,null,'GET');recorded=false;renderWorkspace();await loadSavedTests();const latest=[...savedRuns].reverse().find(v=>v.run.split==='dev'&&v.run.domain.version>0&&v.metrics.complete)||savedRuns.at(-1);if(latest)await openSavedTest(latest.run.run_id);else tab('sources');notify('Saved workspace opened. Completed actions are preserved.');});
bind('freeze',async()=>{if(!ws||!admin)throw Error('Use administrator access and approve the work and an explanation before locking the evaluation.');await api('/workspaces/freeze',{workspace_id:ws.workspace_id,...recordPerson()});clearRecordNote();await refresh();notify('Cases, expected answers and approved guidance are locked for comparison. Use the saved workspace ID in the administrator’s step 07.');});
(async()=>{try{const workspaceId=sessionStorage.getItem('jt-workspace');savedWork=workspaceId?{workspaceId,runId:sessionStorage.getItem('jt-run')}:null;$('saved-work').hidden=!savedWork;updateNextStep();await sessionInfo();}catch(e){notifyError(e);}})();

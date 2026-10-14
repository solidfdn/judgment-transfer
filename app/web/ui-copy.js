'use strict';
// Presentation only. Original definitions, source hashes, rules and results stay unchanged.
globalThis.JTUiCopy=(()=>{
 const samples={
  support_triage:{source:'support_sop',hash:'58b0a4f4d1b8d84a09ca48648e1f03b586fad9ac70f182bd191fe2c68f194a94',title:['Business service request triage','Decide which requests need attention first'],goal:['Route service requests by verified business impact and hold missing evidence.','Choose priority or standard attention for a request. Wait when the information needed to decide is missing.'],fields:{
   verified:['verified','The incident evidence is verified.','Facts checked','Has someone checked that the reported facts are correct?'],
   interrupted:['interrupted','Service interruption exists.','Work stopped','Has a service interruption stopped the work?'],
   affected_users:['affected users','Number of affected users.','People affected','How many people are affected?'],
   time_critical:['time critical','A time-critical business task is blocked.','Work with a deadline blocked','Is the interruption preventing a task with a deadline from being completed?'],
   hours_to_deadline:['hours to deadline','Hours until the business deadline.','Hours until the deadline','How many hours remain until the task must be finished?'],
   workaround:['workaround','A viable workaround exists.','Another way to finish the work','Is there another practical way to complete the task?'],
   status:['status','Current isolated case status.','Case status','What is the current status of this practice case?']
  },actions:{route_high:['route high','HIGH_PRIORITY','Give priority attention'],route_standard:['route standard','STANDARD_PRIORITY','Use the normal order'],hold_case:['hold case','HELD','Wait for clarification']},states:{NEW:'Not yet processed',HIGH_PRIORITY:'Priority attention',STANDARD_PRIORITY:'Normal order',HELD:'Waiting for clarification'}},
  invoice_routing:{source:'invoice_sop',hash:'38fbe3d8a02912e07cc5cfe016ae328826cfa3b932ee332fc4db8224342c4947',title:['Supplier invoice routing','Check invoices before approval'],goal:['Route eligible invoices to an approval queue and hold unresolved cases without executing payment.','Decide which invoices can go to the approval team and which need more information. This does not make a payment.'],fields:{
   supplier_verified:['supplier verified','Supplier identity has been verified.','Supplier checked','Has the identity of the supplier been checked?'],
   delivery_verified:['delivery verified','The referenced delivery evidence has been verified.','Delivery checked','Has the supporting record for this delivery been checked?'],
   number_repeated:['number repeated','Invoice number appears on an earlier invoice.','Invoice number used before','Does an earlier invoice have the same invoice number?'],
   staged_agreement:['staged agreement','An active staged-billing agreement exists.','Agreement to bill in parts','Does a current agreement allow billing in separate parts?'],
   distinct_delivery:['distinct delivery','Delivery reference differs from the earlier invoice.','Different delivery reference','Does the delivery reference differ from the one on the earlier invoice?'],
   status:['status','Current isolated case status.','Case status','What is the current status of this practice case?']
  },actions:{route_approval:['route approval','APPROVAL_QUEUE','Send to the approval team'],hold_case:['hold case','HELD','Wait for clarification']},states:{NEW:'Not yet processed',APPROVAL_QUEUE:'Waiting for the approval team',HELD:'Waiting for clarification'}}
 };
 const humanize=v=>{const s=String(v??'').replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();return /^[A-Z\d ]+$/.test(s)?s.charAt(0)+s.slice(1).toLowerCase():s.charAt(0)+s.slice(1);};
 const value=v=>v===null||v===undefined?'Not supplied':v===true?'Yes':v===false?'No':Array.isArray(v)?v.map(value).join(', '):String(v);
 function sample(domain){const s=samples[domain?.domain_id];return s&&domain.source_hashes?.[s.source]===s.hash?s:null;}
 function definition(domain,id){return [...(domain?.input_fields||[]),...(domain?.state_fields||[])].find(f=>f.field_id===id);}
 function field(domain,id){const f=definition(domain,id),p=sample(domain)?.fields[id];return f&&p&&f.label===p[0]&&f.description===p[1]?{label:p[2],description:p[3]}:{label:f?.label||humanize(id),description:f?.description||''};}
 function title(domain){const p=sample(domain)?.title;return p&&domain.title===p[0]?p[1]:domain?.title||'';}
 function goal(domain){const p=sample(domain)?.goal;return p&&domain.goal===p[0]?p[1]:domain?.goal||'';}
 function state(domain,id,v){const s=sample(domain),f=definition(domain,id),p=s?.fields[id];return id==='status'&&typeof v==='string'&&s?.states[v]&&f&&p&&f.label===p[0]&&f.description===p[1]?s.states[v]:value(v);}
 function action(domain,id){const a=domain?.actions?.find(a=>a.action_id===id),p=sample(domain)?.actions[id];if(a&&p&&a.label===p[0]&&a.effects?.length===1&&a.effects[0].field_id==='status'&&a.effects[0].value===p[1])return p[2];return a?.label||humanize(id||'No action');}
 function condition(domain,c){const label=field(domain,c.field_id).label,op={eq:'is',ne:'is not',gt:'is more than',gte:'is at least',lt:'is less than',lte:'is at most',in:'is one of'};return c.operator==='exists'?label+' must be known':label+' '+(op[c.operator]||c.operator)+' '+value(c.value);}
 function summary(c,fallback){if(!c)return fallback;return String(c.raw_text||'').replace(/\s*Recorded facts are authoritative; null means unknown\.\s*$/,'').split(/The recorded facts below|\s*\{/)[0].trim()||fallback;}
 return Object.freeze({field,title,goal,state,action,condition,summary,value,humanize});
})();

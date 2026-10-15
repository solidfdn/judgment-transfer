// Execute the changed UI functions with a small DOM double; no browser/LIVE claim.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/web/app.js','utf8'),nodes={},checks=[];
const $=id=>nodes[id]??=( {hidden:false,textContent:'',innerHTML:'',classList:{toggle(k,v){this[k]=v;}}} );
const context={$,recorded:false,activeTab:'sources',teaching:null,question:null,currentRun:null,workflowGuide:()=>'<p>Guide</p>',escapeText:x=>String(x).replaceAll('<','&lt;')};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/web/ui-copy.js','utf8'),context);
function ok(name,condition){assert(condition,name);checks.push(name);}
const update=src.slice(src.indexOf('function updateNextStep()'),src.indexOf('function renderRequirements()'));
const render=src.slice(src.indexOf(" $('stale').hidden=ws.status"),src.indexOf(" $('observations').innerHTML"));
const d={title:'Example',goal:'Example',input_fields:[{field_id:'amount',label:'Amount'}],state_fields:[],actions:[],rules:[]};
for(const c of [{name:'flagged',issues:[{message:'<untrusted> needs correction'}],draft:true},{name:'clean',issues:[],draft:true},{name:'approved',issues:[],draft:false}]){
 context.ws={workspace_id:'example',version:c.draft?-1:0,draft:c.draft?{base_version:-1,domain:d,input_review_issues:c.issues}:null,domain:c.draft?null:d,dev_cases:[]};
 vm.runInContext('{'+render+'}',context);vm.runInContext(update+'\nupdateNextStep();',context);
 ok(c.name+' approval visibility',$('approve-workflow').hidden===(!c.draft||Boolean(c.issues.length)));
 ok(c.name+' revise visibility',$('revise-workflow').hidden===(!c.draft||!c.issues.length));
 if(c.issues.length){ok('flagged draft emphasizes revision',$('revise-workflow').classList['primary-action']);ok('untrusted field text is escaped',$('workflow').innerHTML.includes('&lt;untrusted>'));}
}
ok('absence text agrees with evaluator',context.JTUiCopy.condition(d,{field_id:'amount',operator:'exists',value:false})==='Amount is not supplied');
ok('legacy presence wording retained',context.JTUiCopy.condition(d,{field_id:'amount',operator:'exists',value:null})==='Amount must be known');
const html=fs.readFileSync('app/web/index.html','utf8');ok('revision control has one stable ID',(html.match(/id="revise-workflow"/g)||[]).length===1);
fs.writeFileSync('verification/workflow128_ui.json',JSON.stringify({passed:checks.length,checks,scope:'Actual UI functions with DOM doubles; rendered browser validation pending.'},null,2)+'\n');console.log(JSON.stringify({passed:checks.length}));

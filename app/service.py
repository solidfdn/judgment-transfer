import copy
import datetime as dt
import json
import time
import uuid
from pathlib import Path
import config
from adapters.evidence import inspect_file, validate_ref
from core.models import ROOT, JTError, check, digest, execute, score, validate_case, validate_domain

ARMS = ('A_SOURCE_ONLY', 'B_TEXT_ADDED', 'C_JT_RULES')
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def ident(prefix, ctx, suffix=''): return prefix + '_' + digest([ctx['owner'], ctx['operation'], suffix])[:32]
def required(body, name):
    if name not in body: raise JTError('INVALID_INPUT', 'Missing '+name)
    return body[name]

class Service:
    def __init__(self, repo, blobs, adapter): self.repo, self.blobs, self.adapter = repo, blobs, adapter
    def workspace(self, wid, ctx):
        ws = self.repo.get('workspaces', wid)
        if not ws or ws['owner'] != ctx['owner']: raise JTError('NOT_FOUND', 'Workspace not found.', 404)
        return ws
    def owned(self, kind, identifier, ctx):
        doc = self.repo.get(kind, identifier)
        if not doc: raise JTError('NOT_FOUND', 'Item not found.', 404)
        self.workspace(doc['workspace_id'], ctx)
        return doc
    def domain(self, ws, version=None):
        version = ws['version'] if version is None else version
        if version < 0: raise JTError('WORKFLOW_REQUIRED', 'Review and approve a workflow first.', 409)
        return self.repo.get('domains', ws['workspace_id']+'-v'+str(version))['domain']
    def source(self, wid, sid):
        value = self.repo.get('sources', wid+'-'+sid)
        if not value: raise JTError('INVALID_EVIDENCE', 'Evidence refers to an unknown source.')
        return value
    def sources(self, ws, human=False):
        return [self.source(ws['workspace_id'], sid) for sid in ws['source_ids'] + (ws['human_source_ids'] if human else [])]
    def source_check(self, wid, ref): return validate_ref(ref, self.source(wid, ref['source_id']), self.blobs)
    def case(self, wid, cid): return self.repo.get('cases', wid+'-'+cid)

    def create_workspace(self, body, ctx):
        wid = ident('ws',ctx); old = self.repo.get('workspaces',wid)
        if old: return self.summary(wid,ctx)
        pack = body.get('sample',body.get('sample_id'))
        if pack not in (None, 'invoice_routing', 'support_triage'): raise JTError('INVALID_INPUT','Unknown sample.')
        ws = {'workspace_id':wid, 'owner':ctx['owner'], 'created_at':now(), 'mode':self.adapter.mode,
              'goal':str(body.get('goal',''))[:2000], 'version':-1, 'status':'EMPTY', 'source_ids':[], 'human_source_ids':[],
              'case_ids':[], 'run_ids':[], 'teaching_ids':[], 'question_ids':[], 'leases':{}, 'sample':pack,
              'frozen':False, 'approved_count':0, 'shared_trace_ids':[]}
        self.repo.put('workspaces',wid,ws)
        if pack:
            folder=ROOT/'fixtures'/pack
            domain=json.loads((folder/'domain_v0.json').read_text())
            sid=next(iter(domain['source_hashes']))
            self.add_source(wid,'source_sop.txt',(folder/'source_sop.txt').read_bytes(),'text/plain',ctx,source_id=sid)
            for rule in domain['rules']: rule['approved_by']=None
            draft_id=ident('draft',ctx)
            self.repo.put('drafts',draft_id,{'draft_id':draft_id,'workspace_id':wid,'base_version':-1,'domain':domain,'origin':'SOURCE_TEMPLATE','trace_ids':[]})
            cases=json.loads((folder/'cases.json').read_text())
            expected=json.loads((folder/'expected_private_to_scorer.json').read_text())
            for case in cases: self.repo.put('cases',wid+'-'+case['case_id'],case)
            for item in expected: self.repo.put('expected',wid+'-'+item['case_id'],item)
            ws=self.workspace(wid,ctx); ws.update(goal=domain['goal'],case_ids=[c['case_id'] for c in cases],draft_id=draft_id,status='DRAFT')
            self.repo.put('workspaces',wid,ws)
        return self.summary(wid,ctx)

    def add_source(self,wid,name,data,mime,ctx,source_id=None):
        ws=self.workspace(wid,ctx)
        if ws['frozen']: raise JTError('FROZEN','This evaluation workspace is frozen. Create a new workspace to change it.',409)
        metadata,_=inspect_file(name,data,mime)
        sid=source_id or ident('src',ctx)
        if not all(c.isalnum() or c in '_-' for c in sid) or len(sid)>64: raise JTError('INVALID_INPUT','Invalid source ID.')
        current=[s for s in self.sources(ws) if s['source_id']!=sid]
        if len(current)>=5 or sum(s['size'] for s in current)+len(data)>20*1024*1024: raise JTError('INPUT_TOO_LARGE','Maximum five source files and 20 MiB per workspace.',413)
        blob_id=digest([wid,sid,metadata['version_hash']])
        self.blobs.put(blob_id,data,metadata['mime'])
        source={**metadata,'source_id':sid,'workspace_id':wid,'blob_id':blob_id,'human':False}
        wk,sk=('workspaces',wid),('sources',wid+'-'+sid)
        def commit(values):
            w=values[wk]
            if w['frozen']: raise JTError('FROZEN','Workspace is frozen.',409)
            if sid not in w['source_ids']: w['source_ids'].append(sid)
            old=values[sk]
            if w['version']>=0 and (old is None or old['version_hash']!=source['version_hash']): w['status']='STALE'
            values[sk]=source
            return source
        return self.repo.atomic([wk,sk],commit)

    def summary(self,wid,ctx):
        ws=self.workspace(wid,ctx)
        value={k:v for k,v in ws.items() if k not in ('owner','leases')}
        value['sources']=[{k:v for k,v in s.items() if k!='blob_id'} for s in self.sources(ws)]
        value['domain']=self.domain(ws) if ws['version']>=0 else None
        value['draft']=self.repo.get('drafts',ws['draft_id']) if ws.get('draft_id') else None
        value['dev_cases']=[self.case(wid,cid) for cid in ws['case_ids'] if self.case(wid,cid)['split']=='dev']
        value['questions']=[self.repo.get('questions',qid) for qid in ws['question_ids']]
        value['teachings']=[self.repo.get('teachings',tid) for tid in ws['teaching_ids']]
        value['budget']=self.repo.get('budget',digest(ctx['owner'])[:40]) or {'decisions':0,'calls':0}
        if ws['sample']:
            value['example_answer']=(ROOT/'fixtures'/ws['sample']/'expert_teaching_reference.txt').read_text()
        return value

    def draft_domain(self,body,ctx):
        wid=required(body,'workspace_id'); ws=self.workspace(wid,ctx)
        if ws['frozen']: raise JTError('FROZEN','Workspace is frozen.',409)
        sources=self.sources(ws)
        if not sources: raise JTError('SOURCE_REQUIRED','Add source material first.')
        draft_id=ident('draft',ctx); old=self.repo.get('drafts',draft_id)
        if old:return old
        traces=[]; observations=[]
        if body.get('domain') is not None:
            domain=copy.deepcopy(body['domain']); origin='HUMAN_EDIT'
        else:
            extracted=ws.get('extraction')
            if not extracted or extracted['source_hashes']!={s['source_id']:s['version_hash'] for s in sources}:
                raise JTError('EXTRACTION_REQUIRED','Read the current source material before drafting the workflow.',409)
            observations=extracted['observations']
            for observation in observations:
                check('Observation',observation)
                for ref in observation['source_refs']: self.source_check(wid,ref)
            domain_id=self.domain(ws)['domain_id'] if ws['version']>=0 else ws['sample'] or ident('workflow',ctx)
            domain,trace=self.adapter.draft_domain(str(body.get('goal') or ws['goal'])[:2000],domain_id,ws['version']+1,sources,observations,ctx['owner'],ctx['admin'])
            traces.append(trace['trace_id']); origin=self.adapter.mode
        domain['version']=ws['version']+1
        for rule in domain['rules']: rule['approved_by']=None
        validate_domain(domain,lambda ref:self.source_check(wid,ref))
        if domain['source_hashes']!={s['source_id']:s['version_hash'] for s in sources}: raise JTError('INVALID_EVIDENCE','The proposed workflow must identify every current source version.')
        if ws['version']>=0 and domain['domain_id']!=self.domain(ws)['domain_id']:raise JTError('INVALID_INPUT','Workflow ID is immutable.')
        draft={'draft_id':draft_id,'workspace_id':wid,'base_version':ws['version'],'domain':domain,'observations':observations,'origin':origin,'trace_ids':traces}
        wk,dk=('workspaces',wid),('drafts',draft_id)
        def commit(values):
            if values[wk]['version']!=ws['version']:raise JTError('VERSION_CONFLICT','The workflow changed; reopen it.',409)
            values[dk]=draft;values[wk]['draft_id']=draft_id;values[wk]['shared_trace_ids']+=traces
            return draft
        return self.repo.atomic([wk,dk],commit)

    def extract_sources(self,body,ctx):
        wid=required(body,'workspace_id');ws=self.workspace(wid,ctx);sources=self.sources(ws)
        if ws['frozen']:raise JTError('FROZEN','This evaluation is frozen.',409)
        if not sources:raise JTError('SOURCE_REQUIRED','Add source material first.')
        result,trace=self.adapter.extract(sources,ctx['owner'],ctx['admin'])
        for observation in result['observations']:
            check('Observation',observation)
            for ref in observation['source_refs']:self.source_check(wid,ref)
        result.update(source_hashes={s['source_id']:s['version_hash'] for s in sources},trace_id=trace['trace_id'])
        def commit(values):
            values[('workspaces',wid)]['extraction']=result
            values[('workspaces',wid)]['shared_trace_ids'].append(trace['trace_id'])
            return result
        return self.repo.atomic([('workspaces',wid)],commit)

    def approve_domain(self,body,ctx):
        draft=self.owned('drafts',required(body,'draft_id'),ctx);wid=draft['workspace_id'];ws=self.workspace(wid,ctx)
        base=required(body,'base_version');domain=copy.deepcopy(draft['domain'])
        if base!=draft['base_version']:raise JTError('VERSION_CONFLICT','The draft is based on a different version.',409)
        domain['version']=base+1
        for rule in domain['rules']:rule['approved_by']='human:'+digest(ctx['owner'])[:12]
        validate_domain(domain,lambda ref:self.source_check(wid,ref))
        for cid in ws['case_ids']:validate_case(self.case(wid,cid),domain)
        source_keys=[('sources',wid+'-'+sid) for sid in domain['source_hashes']]
        wk,dk=('workspaces',wid),('domains',wid+'-v'+str(base+1))
        from history import prepared
        hk,record,fix=prepared(self,ws,ctx,body,'workflow_approval',{'domain':domain},[self.source(wid,sid) for sid in domain['source_hashes']])
        def commit(values):
            w=values[wk]
            if w['version']!=base:raise JTError('VERSION_CONFLICT','Another approval changed the workflow. Reload before approving.',409)
            if w['frozen']:raise JTError('FROZEN','Workspace is frozen.',409)
            for sid,hashed in domain['source_hashes'].items():
                if not values[('sources',wid+'-'+sid)] or values[('sources',wid+'-'+sid)]['version_hash']!=hashed:raise JTError('STALE','Source changed. Draft and review again.',409)
            fix(values)
            values[dk]={'domain':domain,'approved_at':record['recorded_at'],'origin':draft['origin'],'record_id':record['record_id'],'reviewer_name':record['reviewer_name'],'memo':record['memo']}
            w.update(version=base+1,status='READY',goal=domain['goal'])
            return {'version':base+1,'domain':domain}
        return self.repo.atomic([wk,dk,hk]+source_keys,commit)

    def rollback(self,body,ctx):
        wid=required(body,'workspace_id');ws=self.workspace(wid,ctx)
        if ws['frozen']:raise JTError('FROZEN','Workspace is frozen.',409)
        target=required(body,'target_version');base=required(body,'base_version')
        if type(target) is not int or target<0 or target>ws['version']:raise JTError('INVALID_INPUT','Unknown historical version.')
        domain=copy.deepcopy(self.domain(ws,target));domain['version']=base+1
        validate_domain(domain,lambda ref:self.source_check(wid,ref))
        wk,dk=('workspaces',wid),('domains',wid+'-v'+str(base+1))
        from history import prepared
        hk,record,fix=prepared(self,ws,ctx,body,'workflow_reuse',{'domain':domain,'reused_version':target},[self.source(wid,sid) for sid in domain['source_hashes']])
        def commit(values):
            if values[wk]['version']!=base:raise JTError('VERSION_CONFLICT','Reload the current version.',409)
            if values[wk]['status']=='STALE':raise JTError('STALE','Review changed sources before rollback.',409)
            fix(values)
            values[dk]={'domain':domain,'approved_at':record['recorded_at'],'origin':'HUMAN_ROLLBACK','cloned_from':target,'record_id':record['record_id'],'reviewer_name':record['reviewer_name'],'memo':record['memo']}
            values[wk]['version']=base+1
            return {'domain':domain,'version':base+1}
        return self.repo.atomic([wk,dk,hk],commit)

    def import_cases(self,body,ctx):
        wid=required(body,'workspace_id');ws=self.workspace(wid,ctx);domain=self.domain(ws)
        if ws['frozen'] or ws['run_ids']:raise JTError('FROZEN','Import cases before the first run. Use a new workspace for another dataset.',409)
        cases=required(body,'cases')
        if not isinstance(cases,list) or not 1<=len(cases)<=40:raise JTError('INVALID_INPUT','Import 1–40 cases.')
        if body.get('append') is True:cases=[self.case(wid,cid) for cid in ws['case_ids']]+cases
        if len(cases)>40:raise JTError('INPUT_TOO_LARGE','Maximum 40 cases.',413)
        if len({c['case_id'] for c in cases})!=len(cases):raise JTError('INVALID_INPUT','Duplicate case ID.')
        for case in cases:validate_case(case,domain)
        labels=body.get('expected',[])
        if labels and not ctx['admin']:raise JTError('ADMIN_REQUIRED','Only the evaluation administrator can import expected labels.',403)
        for item in labels:
            check('Expected',item)
            if item['case_id'] not in {c['case_id'] for c in cases}:raise JTError('INVALID_INPUT','Label has no case.')
        wk=('workspaces',wid);keys=[wk]+[('cases',wid+'-'+c['case_id']) for c in cases]+[('expected',wid+'-'+x['case_id']) for x in labels]
        from history import prepared
        hk,record,fix=prepared(self,ws,ctx,body,'manual_case_change',{'cases':body['cases'],'input_fields':domain['input_fields'],'append':body.get('append') is True},[])
        keys.append(hk)
        def commit(values):
            if values[wk]['run_ids'] or values[wk]['frozen']:raise JTError('FROZEN','Dataset already in use.',409)
            if values[wk]['case_ids']!=ws['case_ids'] or values[wk]['version']!=ws['version']:raise JTError('VERSION_CONFLICT','Cases or conditions changed. Reload before importing.',409)
            for case in cases:values[('cases',wid+'-'+case['case_id'])]=case
            for item in labels:values[('expected',wid+'-'+item['case_id'])]=item
            values[wk]['case_ids']=[c['case_id'] for c in cases]
            fix(values)
            return {'count':len(cases),'dataset_hash':digest(cases)}
        return self.repo.atomic(keys,commit)

    def question(self,body,ctx):
        run=self.owned('runs',body.get('run_id') or required(body,'dev_run_id'),ctx);ws=self.workspace(run['workspace_id'],ctx);wid=ws['workspace_id']
        if run['split']!='dev':raise JTError('HOLDOUT_ISOLATION','Teaching uses development cases only.',403)
        failures=[]
        for task_id in run['task_ids']:
            task=self.repo.get('tasks',task_id)
            if task['status']=='COMPLETED' and (task['decision']['outcome']=='HOLD' and task.get('score',{}).get('correct') is not True or task.get('score',{}).get('correct') is False):
                case=self.case(wid,task['case_id']);failures.append({'case_id':case['case_id'],'facts':case['facts'],'decision':task['decision']})
        if not failures:raise JTError('NO_TEACHING_CASE','Complete a development run with held or incorrect cases first.',409)
        groups={}
        for failure in failures:
            key=tuple(sorted(failure['decision']['missing_fields']))
            groups.setdefault(key,[]).append(failure)
        # First resolve the condition shared by the largest number of blocked dev cases.
        # A tie prefers actual missing evidence, then a stable field order.
        failures=sorted(groups.values(),key=lambda group:(-len(group),-bool(group[0]['decision']['missing_fields']),group[0]['case_id']))[0]
        question,trace=self.adapter.propose_question(self.domain(ws),failures,self.sources(ws),ctx['owner'],ctx['admin'])
        question['question_id']=ident('question',ctx);check('Question',question)
        if not set(question['affected_dev_case_ids']).issubset({f['case_id'] for f in failures}):raise JTError('HOLDOUT_ISOLATION','Question refers to a case outside the development set.')
        for ref in question['source_refs']:self.source_check(wid,ref)
        doc={'workspace_id':wid,'question':question,'trace_id':trace['trace_id'],'base_version':ws['version']}
        wk,qk=('workspaces',wid),('questions',question['question_id'])
        def commit(values):
            values[qk]=doc
            if question['question_id'] not in values[wk]['question_ids']:values[wk]['question_ids'].append(question['question_id'])
            values[wk]['shared_trace_ids'].append(trace['trace_id'])
            return doc
        return self.repo.atomic([wk,qk],commit)

    def teach(self,body,ctx):
        q=self.owned('questions',required(body,'question_id'),ctx);wid=q['workspace_id'];ws=self.workspace(wid,ctx)
        if ws['frozen']:raise JTError('FROZEN','Teaching is closed after evaluation freeze.',409)
        if ws['approved_count']>=3:raise JTError('TEACHING_LIMIT','This experiment allows at most three expert corrections.',409)
        text=required(body,'human_text')
        if not isinstance(text,str) or not text.strip() or len(text)>6000:raise JTError('INVALID_INPUT','Use 1–6000 characters.')
        if q['base_version']!=ws['version']:raise JTError('VERSION_CONFLICT','Ask a new question against the current version.',409)
        if body.get('base_version',ws['version'])!=ws['version']:raise JTError('VERSION_CONFLICT','The answer refers to an older workflow.',409)
        tid=ident('teaching',ctx);sid=ident('human',ctx)
        metadata,_=inspect_file('expert_answer.txt',text.encode(),'text/plain')
        source={**metadata,'source_id':sid,'workspace_id':wid,'blob_id':digest([wid,sid]),'human':True}
        self.blobs.put(source['blob_id'],text.encode(),'text/plain');self.repo.put('sources',wid+'-'+sid,source)
        result,trace=self.adapter.draft_rules(self.domain(ws),q['question'],text,source,ctx['owner'],ctx['admin'])
        rules=result['rules']
        for rule in rules:rule['approved_by']=None
        teaching={'teaching_id':tid,'question_id':q['question']['question_id'],'human_text':text,'base_domain_version':ws['version'],'proposed_rules':rules,'approval_state':'DRAFT'}
        check('Teaching',teaching)
        merged=copy.deepcopy(self.domain(ws));merged['source_hashes'][sid]=source['version_hash']
        replaced={r['rule_id'] for r in rules};merged['rules']=[r for r in merged['rules'] if r['rule_id'] not in replaced]+rules
        validate_domain(merged,lambda ref:self.source_check(wid,ref))
        doc={'workspace_id':wid,'teaching':teaching,'source_id':sid,'trace_id':trace['trace_id'],'created_at':now()}
        wk,tk=('workspaces',wid),('teachings',tid)
        def commit(values):
            if values[wk]['version']!=ws['version']:raise JTError('VERSION_CONFLICT','The workflow changed while drafting.',409)
            values[tk]=doc;values[wk]['teaching_ids'].append(tid);values[wk]['shared_trace_ids'].append(trace['trace_id'])
            return doc
        return self.repo.atomic([wk,tk],commit)

    def approve_teaching(self,tid,body,ctx):
        doc=self.owned('teachings',tid,ctx);wid=doc['workspace_id'];ws=self.workspace(wid,ctx);base=required(body,'base_version')
        if base!=doc['teaching']['base_domain_version']:raise JTError('VERSION_CONFLICT','Teaching base version does not match.',409)
        domain=copy.deepcopy(self.domain(ws,base));rules=copy.deepcopy(doc['teaching']['proposed_rules'])
        for rule in rules:rule['approved_by']='human:'+digest(ctx['owner'])[:12]
        replacements={r['rule_id'] for r in rules};domain['rules']=[r for r in domain['rules'] if r['rule_id'] not in replacements]+rules
        human=self.source(wid,doc['source_id']);domain['source_hashes'][human['source_id']]=human['version_hash'];domain['version']=base+1
        validate_domain(domain,lambda ref:self.source_check(wid,ref))
        wk,tk,dk=('workspaces',wid),('teachings',tid),('domains',wid+'-v'+str(base+1))
        from history import prepared
        hk,record,fix=prepared(self,ws,ctx,body,'teaching_approval',{'domain':domain,'explanation':doc['teaching']['human_text'],'question':self.repo.get('questions',doc['teaching']['question_id'])},[self.source(wid,sid) for sid in domain['source_hashes']])
        def commit(values):
            w=values[wk]
            if w['frozen']:raise JTError('FROZEN','Evaluation is frozen.',409)
            if w['version']!=base or values[tk]['teaching']['approval_state']!='DRAFT':raise JTError('VERSION_CONFLICT','This approval is no longer current.',409)
            if w['status']=='STALE':raise JTError('STALE','Re-approve current sources first.',409)
            fix(values)
            values[dk]={'domain':domain,'approved_at':record['recorded_at'],'origin':self.adapter.mode,'teaching_id':tid,'record_id':record['record_id'],'reviewer_name':record['reviewer_name'],'memo':record['memo']}
            values[tk]['record_id']=record['record_id']
            values[tk]['teaching'].update(approval_state='APPROVED',proposed_rules=rules)
            w.update(version=base+1,status='READY',approved_count=w['approved_count']+1);w['human_source_ids'].append(doc['source_id'])
            return {'version':base+1,'domain':domain}
        return self.repo.atomic([wk,tk,dk,hk],commit)

    def freeze(self,body,ctx):
        if not ctx['admin']:raise JTError('ADMIN_REQUIRED','Evaluation freeze requires administrator access.',403)
        wid=required(body,'workspace_id');ws=self.workspace(wid,ctx)
        if ws['status']!='READY' or not ws['approved_count']:raise JTError('NOT_READY','Approve the workflow and at least one expert correction first.',409)
        cases=[self.case(wid,c) for c in ws['case_ids']]
        labels=[self.repo.get('expected',wid+'-'+c['case_id']) for c in cases]
        if any(x is None for x in labels):raise JTError('LABELS_REQUIRED','Expected labels must be frozen before the benchmark.',409)
        frozen={'frozen_at':now(),'dataset_hash':digest(cases),'label_hash':digest(labels),'version':ws['version'],'domain_hash':digest(self.domain(ws)),
                'source_hashes':{s['source_id']:s['version_hash'] for s in self.sources(ws,True)},'model_settings':config.SETTINGS,'code_hash':config.CODE_HASH}
        from history import prepared
        hk,record,fix=prepared(self,ws,ctx,body,'evaluation_lock',frozen,self.sources(ws,True))
        def commit(values):
            current=values[('workspaces',wid)]
            if current['version']!=ws['version'] or current['status']!='READY':raise JTError('VERSION_CONFLICT','Workspace changed.',409)
            if current['frozen']:return current['freeze']
            fix(values)
            current['frozen']=True;current['freeze']=frozen
            frozen.update(record_id=record['record_id'],reviewer_name=record['reviewer_name'],memo=record['memo'])
            return frozen
        return self.repo.atomic([('workspaces',wid),hk],commit)

    def create_run(self,body,ctx):
        wid=required(body,'workspace_id');ws=self.workspace(wid,ctx)
        from history import actor
        person=actor(body)
        if ws.get('recovery_study') and not ctx.get('_recovery111'):
            raise JTError('CONTROLLED_STUDY','This frozen study is advanced through its bounded controller only.',409)
        if ws['status']!='READY':raise JTError('STALE','Review the workflow and source changes before running.',409)
        if body.get('mode',self.adapter.mode)!=self.adapter.mode:raise JTError('MODE_MISMATCH','Requested mode does not match this deployment. Recorded exports are read-only.',409)
        arm=body.get('arm','C_JT_RULES');split=body.get('split','dev');repeats=body.get('repeats',1)
        if arm not in ARMS or split not in ('dev','holdout') or type(repeats) is not int or not 1<=repeats<=3:raise JTError('INVALID_INPUT','Invalid evaluation options.')
        if (split=='holdout' or repeats>1) and not ctx['admin']:raise JTError('ADMIN_REQUIRED','Formal evaluation is reserved for the administrator.',403)
        if split=='holdout' and not ws['frozen']:raise JTError('FREEZE_REQUIRED','Freeze cases, labels, prompts and rules before evaluation.',409)
        if split=='holdout' and (ws['freeze'].get('code_hash')!=config.CODE_HASH or ws['freeze'].get('model_settings')!=config.SETTINGS):
            raise JTError('FROZEN_EXPERIMENT','The frozen experiment uses a different code or model configuration. Saved results remain readable; do not reuse this holdout as a new unseen evaluation.',409)
        domain=self.domain(ws,ws['version'] if arm=='C_JT_RULES' else 0)
        cases=[self.case(wid,c) for c in ws['case_ids'] if self.case(wid,c)['split']==split]
        if body.get('case_ids'):
            chosen=body['case_ids']
            if not set(chosen).issubset({c['case_id'] for c in cases}):raise JTError('INVALID_INPUT','Case selection is outside this split.')
            cases=[c for c in cases if c['case_id'] in chosen]
        elif not ctx['admin']:
            selected=[]
            for stratum in ('normal','transfer','must_hold'):
                selected += [c for c in cases if c['stratum']==stratum][:1]
            cases=selected or cases[:3]
        if not cases:raise JTError('CASES_REQUIRED','Import cases first.')
        for case in cases:validate_case(case,domain)
        run_id=ident('run',ctx);old=self.repo.get('runs',run_id)
        if old:return self.run_view(run_id,ctx)
        texts=[self.repo.get('teachings',tid)['teaching']['human_text'] for tid in ws['teaching_ids'] if self.repo.get('teachings',tid)['teaching']['approval_state']=='APPROVED']
        # B gets exactly the approved expert text, with its real citation metadata.
        # It still uses the v0 domain, never the approved v1 rule structure.
        sources=self.sources(ws,human=arm=='B_TEXT_ADDED')
        task_ids=[];tasks={}
        for repeat in range(1,repeats+1):
            for case in cases:
                task_id='task_'+digest([run_id,arm,case['case_id'],repeat])[:40];task_ids.append(task_id)
                tasks[('tasks',task_id)]={'task_id':task_id,'run_id':run_id,'workspace_id':wid,'case_id':case['case_id'],'arm':arm,'repeat':repeat,
                    'status':'PENDING','lease_token':None,'lease_until':0,'attempts':0,'state':copy.deepcopy(case['initial_state']),'step_index':0,'receipt_ids':[],'trace_ids':[]}
        run={**person,'run_id':run_id,'workspace_id':wid,'domain':domain,'domain_hash':digest(domain),'dataset_hash':digest(cases),'prompt_hash':digest({'settings':config.SETTINGS,'arm':arm}),
             'code_hash':config.CODE_HASH,'mode':self.adapter.mode,'model_settings':config.SETTINGS,'arm':arm,'split':split,'repeats':repeats,'case_ids':[c['case_id'] for c in cases],
             'task_ids':task_ids,'created_at':now(),'cancelled':False,'active_version':ws['version'],'human_text':'\n\n'.join(texts),'source_ids':[s['source_id'] for s in sources],
             'source_hashes':{s['source_id']:s['version_hash'] for s in self.sources(ws,True)},'evidence_sources_snapshot':copy.deepcopy(self.sources(ws,True)),
             'human_inputs':ws['approved_count'],'shared_trace_ids':list(ws['shared_trace_ids'])}
        wk,rk=('workspaces',wid),('runs',run_id)
        def commit(values):
            if values[wk]['version']!=ws['version'] or values[wk]['status']!='READY':raise JTError('VERSION_CONFLICT','Workflow changed before the run began.',409)
            values[rk]=run
            for key,value in tasks.items():values[key]=value
            values[wk]['run_ids'].append(run_id)
            return {'run_id':run_id,'total':len(task_ids),'mode':self.adapter.mode}
        return self.repo.atomic([wk,rk]+list(tasks),commit)

    def step(self,run_id,ctx):
        started=time.monotonic()
        run=self.owned('runs',run_id,ctx);wid=run['workspace_id'];ws=self.workspace(wid,ctx)
        if ws.get('recovery_study') and not ctx.get('_recovery111'):
            raise JTError('CONTROLLED_STUDY','Use the bounded study controller; saved exports remain readable.',409)
        opkey=('step_requests',digest([ctx['owner'],run_id,ctx['operation']]))
        cached=self.repo.get(*opkey)
        if cached and cached.get('receipt_id'):return {'receipt':self.repo.get('receipts',cached['receipt_id']),'duplicate':True}
        if cached and cached.get('done'):return cached['result']
        selected=cached.get('task_id') if cached else None
        if not selected and ws.get('recovery_study') and ctx.get('_recovery111'):
            selected=ctx.get('_recovery_task')
            if selected and selected not in run['task_ids']:
                raise JTError('INVALID_INPUT','Task is outside this run.')
        if not selected:
            for tid in run['task_ids']:
                task=self.repo.get('tasks',tid)
                if task['status']=='PENDING' or task['status']=='LEASED' and task['lease_until']<=time.time():selected=tid;break
        if not selected:return {'done':all(self.repo.get('tasks',tid)['status'] in ('COMPLETED','FAILED','CANCELLED') for tid in run['task_ids'])}
        # A saved run is an immutable experiment, including its implementation.
        # Cached receipts and read-only exports above remain available after upgrades.
        # Do not mark untouched tasks failed or dispatch a call under a new protocol.
        if run['code_hash']!=config.CODE_HASH or run['model_settings']!=config.SETTINGS or run['mode']!=self.adapter.mode:
            raise JTError('RUN_PROTOCOL_CHANGED','This saved run belongs to a different code or model configuration. Its results remain readable. Start a separate development run; do not mix new calls into this experiment.',409)
        wk,rk,tk=('workspaces',wid),('runs',run_id),('tasks',selected)
        lease=uuid.uuid4().hex
        def claim(values):
            w,r,t=values[wk],values[rk],values[tk];request=values[opkey]
            if request and request.get('receipt_id'):return {'cached':request}
            if request and request.get('done'):return {'finished':request['result']}
            if r['cancelled']:raise JTError('CANCELLED','This run was cancelled.',409)
            if w['status']!='READY' or w['version']!=r['active_version']:raise JTError('STALE','The workflow changed. Start a fresh run.',409)
            if t['status'] in ('COMPLETED','FAILED','CANCELLED'):return {'finished':{'done':True,'task_id':selected}}
            if t['status']=='LEASED' and t['lease_until']>time.time():raise JTError('BUSY','This case is still running. Resume after the lease expires.',409,True)
            w['leases']={k:v for k,v in w['leases'].items() if v>time.time() and k!=selected}
            if len(w['leases'])>=2:raise JTError('BUSY','Two cases are running. Wait for one to finish.',429,True)
            if t['attempts']>=2 and t['status']=='LEASED':
                t.update(status='FAILED',error={'code':'INTERRUPTED','message':'Two interrupted leases; preserved as a failed case.'})
                values[opkey]={'done':True,'result':{'task_id':selected,'failed':True}}
                return {'finished':values[opkey]['result']}
            t.update(status='LEASED',lease_token=lease,lease_until=time.time()+180,attempts=t['attempts']+1)
            w['leases'][selected]=t['lease_until'];values[opkey]={'task_id':selected,'step_index':t['step_index']}
            return {'task':copy.deepcopy(t)}
        claimed=self.repo.atomic([wk,rk,tk,opkey],claim)
        if 'cached' in claimed:return {'receipt':self.repo.get('receipts',claimed['cached']['receipt_id']),'duplicate':True}
        if 'finished' in claimed:return claimed['finished']
        task=claimed['task'];case=self.case(wid,task['case_id']);trace=None
        try:
            sources=[self.source(wid,sid) for sid in run['source_ids']]
            raw,trace=self.adapter.decide(run['domain'],case,task['state'],run['arm'],run['human_text'],sources,ctx['owner'],ctx['admin'])
            for ref in raw['source_refs']:self.source_check(wid,ref)
            decision,after,terminal=execute(run['domain'],case,task['state'],raw,run['arm']=='C_JT_RULES')
            if not terminal and task['step_index']>=7:raise JTError('STEP_LIMIT','The case reached the eight-step prototype limit.',422)
            expected=self.repo.get('expected',wid+'-'+case['case_id'])
            result_score=score(case,decision,after,expected,terminal)
            rid='receipt_'+digest([run_id,run['arm'],case['case_id'],task['repeat'],task['step_index']])[:40]
            receipt={'receipt_id':rid,'run_id':run_id,'case_id':case['case_id'],'task_id':selected,'action_id':decision['action_id'],'rule_ids':decision['rule_ids'],
                     'before_state':task['state'],'after_state':after,'domain_hash':run['domain_hash'],'case_hash':digest(case),'committed_at':now()}
            check('Receipt',receipt);receipt_key=('receipts',rid)
            def commit(values):
                t,w=values[tk],values[wk]
                if time.monotonic()-started>135:raise JTError('APP_DEADLINE','The application call window expired. No operation was committed.',503,True)
                if t['lease_token']!=lease or t['lease_until']<=time.time():raise JTError('LEASE_LOST','A later worker owns this case. Refresh the run.',409)
                if w['status']!='READY' or w['version']!=run['active_version']:raise JTError('STALE','Workflow changed during the model call. No operation was committed.',409)
                values[receipt_key]=receipt;t.update(state=after,decision=decision,raw_decision=raw,score=result_score,
                    status='COMPLETED' if terminal else 'CANCELLED' if values[rk]['cancelled'] else 'PENDING',step_index=t['step_index']+1,lease_token=None,lease_until=0,attempts=0)
                t['receipt_ids'].append(rid);t['trace_ids'].append(trace['trace_id']);w['leases'].pop(selected,None)
                values[opkey]={'task_id':selected,'receipt_id':rid,'done':True}
                return {'receipt':receipt,'decision':decision,'score':result_score,'terminal':terminal}
            return self.repo.atomic([wk,rk,tk,receipt_key,opkey],commit)
        except Exception as error:
            if not isinstance(error,JTError):error=JTError('INTERNAL_ERROR','This case could not complete. Use the saved run ID to resume.',500)
            trace=trace or getattr(error,'trace',None)
            # Load expected outside transactions; no model call is made on a failed task replay.
            expected=self.repo.get('expected',wid+'-'+case['case_id'])
            def fail_atomic(values):
                t=values[tk]
                if t['lease_token']!=lease:return
                t.update(status='FAILED',lease_token=None,lease_until=0,error={'code':error.code,'message':error.message},score=score(case,{},t['state'],expected,False))
                if trace:t['trace_ids'].append(trace['trace_id'])
                values[wk]['leases'].pop(selected,None);values[opkey]={'done':True,'result':{'task_id':selected,'failed':True,'error':t['error']}}
            self.repo.atomic([wk,tk,opkey],fail_atomic)
            return {'task_id':selected,'failed':True,'error':{'code':error.code,'message':error.message}}

    def cancel(self,run_id,ctx):
        run=self.owned('runs',run_id,ctx)
        rk=('runs',run_id);keys=[rk]+[('tasks',tid) for tid in run['task_ids']]
        def commit(values):
            values[rk]['cancelled']=True
            for tid in run['task_ids']:
                if values[('tasks',tid)]['status']=='PENDING':values[('tasks',tid)]['status']='CANCELLED'
            return {'cancelled':True,'in_flight':'An already leased case may finish once; no new case will start.'}
        return self.repo.atomic(keys,commit)

    def run_view(self,run_id,ctx,export=False):
        run=self.owned('runs',run_id,ctx);ws=self.workspace(run['workspace_id'],ctx)
        tasks=[self.repo.get('tasks',tid) for tid in run['task_ids']]
        counts={s:sum(t['status']==s for t in tasks) for s in ('PENDING','LEASED','COMPLETED','FAILED','CANCELLED')}
        n=len(tasks);labelled=all(self.repo.get('expected',run['workspace_id']+'-'+t['case_id']) is not None for t in tasks)
        metrics={'total':n,'unique_cases':len(run['case_ids']),'repeats':run['repeats'],'counts':counts,
                 'correct_completion_rate':sum(bool(t.get('score',{}).get('correct_completion')) for t in tasks)/n if labelled else None,
                 'correct_decision_rate':sum(bool(t.get('score',{}).get('correct')) for t in tasks)/n if labelled else None,
                 'critical_errors':sum(bool(t.get('score',{}).get('critical_error')) for t in tasks) if labelled else None,
                 'holds':sum(t.get('decision',{}).get('outcome')=='HOLD' for t in tasks),'human_inputs':run['human_inputs'],
                 'complete':not(counts['PENDING']+counts['LEASED']),'result_kind':'SIMULATION' if run['mode']=='MOCK' else 'MEASURED',
                 'stale':ws['status']=='STALE' or any(self.source(run['workspace_id'],sid)['version_hash']!=value for sid,value in run['source_hashes'].items()),
                 'historical_rule_version':ws['version']!=run['active_version']}
        traces=[self.repo.get('traces',i) for t in tasks for i in t['trace_ids']]
        metrics['cost_usd']=sum(a.get('cost_usd',0) for trace in traces for a in trace.get('attempts',[]))
        metrics['latency_ms']=sum(trace.get('elapsed_ms',0) for trace in traces)
        value={'run':{k:v for k,v in run.items() if k not in ('human_text','task_ids','shared_trace_ids')},'tasks':[{k:v for k,v in t.items() if k not in ('lease_token',)} for t in tasks],'metrics':metrics}
        if export:
            value.update(export_version='1.0',exported_at=now(),receipts=[self.repo.get('receipts',rid) for t in tasks for rid in t['receipt_ids']],
                traces=traces,shared_preparation_traces=[self.repo.get('traces',i) for i in run['shared_trace_ids']],
                frozen_evaluation=ws.get('freeze'),source_metadata=copy.deepcopy(run.get('evidence_sources_snapshot',self.sources(ws,True))),
                caveat='MOCK is synthetic and cannot support performance claims.' if run['mode']=='MOCK' else 'Results apply only to this frozen sample; no award or generalization is guaranteed.')
            from case_intake import case_evidence
            evidence=case_evidence(self,run['workspace_id'],run['case_ids'])
            if evidence:value['case_evidence']=evidence
        return value

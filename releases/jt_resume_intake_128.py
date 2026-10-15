#!/usr/bin/env python3
"""Resume the three unread PDFs after validating explicit absence in saved answers.
Preserve the original failed checkpoint and raw OBSERVED/null response. No new
workflow approval, repeated extraction, case confirmation or case execution.
"""
import argparse,base64,copy,fcntl,hashlib,io,json,os,sys,types,zipfile,zlib
from pathlib import Path
EMBEDDED = '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'
ORIGINAL_SHA = 'f19a6915fc9f742a6a93293f99b8224663a4c4b91be0d8a1b54d89a7d8f49189'
OLD_CHECKPOINT = '.jt/upgrades/1.0.28/pdf-intake.json'
NEW_CHECKPOINT = '.jt/upgrades/1.0.28/pdf-intake-resume.json'
OLD_OUTPUT = 'deliverables/release128/intake'
NEW_OUTPUT = 'deliverables/release128/intake-resume'
TRACES = ['trace_9367aa581b6a428b8c02be699424e163','trace_8e1a6d9b10a5431dbee4f12f54df5ba3','trace_a46182d860834b54a92b30e4c5e54b96']
APPROVED_DRAFT = 'draft_15eb1a11987f17c9a775f6cc813de5ce'
ABSENCE = {'receipt_employee_paid_amount':'Employee card payment (JPY): Not stated',
           'receipt_payment_status':'Employee card payment status: Not stated'}


def controller():
    raw=zlib.decompress(base64.b64decode(EMBEDDED))
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA:raise RuntimeError('Embedded controller integrity failed')
    module=types.ModuleType('intake128_preserved')
    exec(compile(raw,'intake128-preserved','exec'),module.__dict__)
    return module


def validate_absence(answer,doc,domain,pdf,base_review):
    """Adapt only verification semantics; never rewrite a saved model response."""
    from pypdf import PdfReader
    pages=PdfReader(io.BytesIO(pdf)).pages
    validation_copy=copy.deepcopy(answer);notes=[]
    for observation in validation_copy.get('observations',[]):
        fid=observation.get('field_id')
        if (observation.get('status')!='OBSERVED' or observation.get('value') is not None or
            fid not in ABSENCE or doc['transcription'].get(fid) is not None):continue
        line=ABSENCE[fid];valid=False
        for ref in observation.get('source_refs',[]):
            source=next((s for s in answer.get('sources',[]) if s.get('source_id')==ref.get('source_id')),None)
            quote=ref.get('quote','')
            if (source and source.get('version_hash')==doc['sha256']==ref.get('version_hash') and
                ref.get('locator')=='page:2' and len(pages)>=2 and quote and
                quote in (pages[1].extract_text() or '') and line in quote):valid=True
        if valid:
            observation['status']='UNRESOLVED' # Temporary comparison copy only.
            notes.append({'field_id':fid,'original_status':'OBSERVED','original_value':None,
                'interpretation':'The source explicitly states Not stated. The business fact remains unknown/null; the raw observation is preserved.'})
    return base_review(validation_copy,doc,domain),notes


class Redirect:
    def __init__(self,r,root):self.r=r;self.root=root;self.Stop=r.Stop
    def path(self,path):
        path=Path(path)
        if path==self.root/OLD_CHECKPOINT:return self.root/NEW_CHECKPOINT
        try:return self.root/NEW_OUTPUT/path.relative_to(self.root/OLD_OUTPUT)
        except ValueError:return path
    def load(self,path):return self.r.load(self.path(path))
    def save(self,path,value):return self.r.save(self.path(path),value)
    def stamp(self):return self.r.stamp()


class RemainingOnly:
    def __init__(self,api,m,r,pdfs):self.api=api;self.m=m;self.r=r;self.pdfs=pdfs
    def call(self,path,data=None,key=None,files=None):
        if data is not None or files is not None:
            doc=next((d for d in self.m.DOCS[3:] if data and d['case_id']==data.get('case_id')),None)
            if (path!='/cases/read' or not doc or key!='intake128-read-'+doc['case_id'] or
                data!={'workspace_id':self.m.WORKSPACE,'case_id':doc['case_id'],'split':doc['split'],'stratum':doc['stratum']} or
                files!=(Path(doc['path']).name,'application/pdf',self.pdfs[doc['case_id']])):
                raise self.r.Stop('UNEXPECTED_WRITE','再承認・既読PDFの再読取・案件確定・案件実行は許可されていません。')
        return self.api.call(path,data,key=key,files=files)


def run(api,root,r,reviewer):
    root=Path(root);m=controller();old=r.load(root/OLD_CHECKPOINT);saved=r.load(root/NEW_CHECKPOINT)
    old_digest=m.digest(old)
    if (not old or old.get('status')!='FAILED' or
        old.get('error',{}).get('code')!='DOCUMENT_READING_REQUIRES_REVIEW' or
        old.get('code_hash')!=m.CODE_HASH or old.get('workspace_id')!=m.WORKSPACE or
        old.get('reviewer_name')!=reviewer or old.get('approved_draft_id')!=APPROVED_DRAFT or
        [x.get('trace_id') for x in old.get('readings',[])]!=TRACES or
        [x.get('case_id') for x in old.get('readings',[])]!=[d['case_id'] for d in m.DOCS[:3]] or
        old.get('model_calls')!=3 or old.get('judgment_calls')!=0 or old.get('case_confirmation_created') is not False or
        old.get('pending',{}).get('index')!=2 or old.get('after_ledger',{}).get('calls')!=519):
        raise r.Stop('SAVED_RESULT_CHANGED','共有いただいた3件目の停止記録と一致しません。追加実行せず停止します。')
    if saved and saved.get('resume_origin_hash')!=old_digest:
        raise r.Stop('SAVED_RESULT_CHANGED','再開元の停止記録が変わっています。')
    pdfs=m.files(root,r);base_review=m.read_issues;interpretations={}
    def reviewed(answer,doc,domain):
        issues,notes=validate_absence(answer,doc,domain,pdfs[doc['case_id']],base_review)
        if notes:interpretations[doc['case_id']]=notes
        return issues
    m.read_issues=reviewed
    for answer,doc in zip(old['readings'],m.DOCS):
        if reviewed(answer,doc,old['approved_domain']):
            raise r.Stop('SAVED_READING_REQUIRES_REVIEW','保存済みの値または原本の記載なしを確認できません。追加読取はしません。')
    if not saved:
        health=api.call('/health')
        if (health.get('package_version'),health.get('code_hash'),health.get('mode'),health.get('max_cost_usd'))!=(m.VERSION,m.CODE_HASH,'LIVE',100):
            raise r.Stop('DEPLOY_MISMATCH','1.0.28・LIVE・既存上限を確認できません。')
        ws=api.call('/workspaces/'+m.WORKSPACE)
        if m.stable(ws)!=old['approved_workspace'] or ws.get('case_draft_ids',[])!=[x['case_draft_id'] for x in old['readings']]:
            raise r.Stop('WORKSPACE_CHANGED','保存後の条件・案件・履歴が変わっています。')
        current=api.call('/recovery115');m.usage(r,old['after'],current,0)
        saved=copy.deepcopy(old)
        saved.update(status='READING',resume_origin_hash=old_digest,resume_origin=OLD_CHECKPOINT,
            preserved_error=old['error'],resume_before=current,resumed_at=r.stamp(),absence_interpretations=interpretations)
        saved.pop('pending',None);saved.pop('error',None)
        for item in saved['case_previews']:
            item['previous_review_issues']=item['review_issues'];item['review_issues']=[]
        # Original raw answers, their classification, failed checkpoint and outputs remain untouched.
        r.save(root/NEW_OUTPUT/'preserved-failure.json',old);r.save(root/NEW_CHECKPOINT,saved)
        print('原本の「記載なし」を確認しました。保存済み3件・承認・停止記録を保持し、残り3件だけを読み取ります。',flush=True)
    try:
        result=m.run(RemainingOnly(api,m,r,pdfs),root,Redirect(r,root),reviewer,True)
    finally:
        current=r.load(root/NEW_CHECKPOINT)
        if current:
            current['absence_interpretations']=interpretations
            r.save(root/NEW_CHECKPOINT,current)
            r.save(root/NEW_OUTPUT/'verification.json',current)
        if m.digest(r.load(root/OLD_CHECKPOINT))!=old_digest:
            raise r.Stop('ORIGINAL_RECORD_CHANGED','元の停止記録の変更を検知しました。')
    after=api.call('/recovery115');new_calls=m.usage(r,saved['resume_before'],after,6)
    result.update(resumed_model_calls=new_calls,absence_interpretations=interpretations)
    r.save(root/NEW_CHECKPOINT,result);r.save(root/NEW_OUTPUT/'verification.json',result)
    print(json.dumps({'status':result['status'],'resumed_model_calls':new_calls,
        'previous_readings_reused':3,'new_approvals':0,'judgment_calls':0,
        'absence_interpretations':interpretations},ensure_ascii=False,indent=2),flush=True)
    return result


def main():
    sys.dont_write_bytecode=True
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reviewer',required=True);args=parser.parse_args()
    root=Path.cwd().resolve();m=controller()
    conf=json.loads((root/'.jt/config.json').read_text());manifest=json.loads((root/'package-manifest.json').read_text())
    if conf.get('project_id')!=m.PROJECT or (manifest.get('version'),manifest.get('code_hash'))!=(m.VERSION,m.CODE_HASH):
        raise RuntimeError('Expected the existing Judgment Transfer 1.0.28 project/package')
    if Path(sys.prefix).resolve()!=(root/'.venv').resolve():
        executable=root/'.venv/bin/python'
        if not executable.is_file():raise RuntimeError('Existing .venv missing')
        os.execv(str(executable),[str(executable),str(Path(__file__).resolve()),*sys.argv[1:]])
    sys.path[:0]=[str(root),str(root/'app')]
    from steps import runbook as r
    r.integrity()
    with (root/'.jt/runbook.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise r.Stop('RUNBOOK_BUSY','別の処理が実行中です。')
        run(r.API(),root,r,args.reviewer.strip())


if __name__=='__main__':
    try:main()
    except Exception as error:
        code=getattr(error,'code','INTAKE_RESUME_STOPPED')
        message=str(error) if hasattr(error,'code') or isinstance(error,RuntimeError) else type(error).__name__
        sys.exit('STOP '+str(code)+' / '+message)

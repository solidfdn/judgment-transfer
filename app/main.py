import datetime as dt
import hmac
import io
import json
import os
import secrets
import time
from functools import wraps
from flask import Flask, Response, g, jsonify, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
import config
from core.models import JTError, digest
from service import Service
from storage.repository import Blobs, FirestoreRepository, LocalRepository

def create_app(repo=None, adapter=None, blobs=None, testing=False):
    app=Flask(__name__,static_folder='web',static_url_path='/assets')
    if config.MODE=='LIVE':app.wsgi_app=ProxyFix(app.wsgi_app,x_proto=1)
    app.config.update(SECRET_KEY=config.secret(),MAX_CONTENT_LENGTH=21*1024*1024,
        SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SECURE=config.MODE=='LIVE' and not testing,
        SESSION_COOKIE_SAMESITE='Lax',PERMANENT_SESSION_LIFETIME=dt.timedelta(minutes=60),TESTING=testing)
    repo=repo or (FirestoreRepository(config.PROJECT) if config.STORE=='firestore' else LocalRepository(config.DATA))
    blobs=blobs or Blobs(config.DATA,config.BUCKET or None,config.PROJECT or None)
    if adapter is None:
        if config.MODE=='LIVE':
            from adapters.model import LiveAdapter
            adapter=LiveAdapter(repo,blobs)
        elif config.MODE=='MOCK':
            from adapters.mock import MockAdapter
            adapter=MockAdapter(repo,blobs)
        else:raise RuntimeError('JT_MODE must be MOCK or LIVE. RECORDED is a read-only export viewer.')
    service=Service(repo,blobs,adapter);app.extensions['jt']=service
    from recovery111 import Recovery
    recovery=Recovery(service)
    from recovery112 import Recovery as Recovery112
    recovery112=Recovery112(service)
    from recovery113 import Recovery as Recovery113
    recovery113=Recovery113(service)
    from recovery114 import Recovery as Recovery114
    recovery114=Recovery114(service)
    from recovery115 import Recovery as Recovery115
    recovery115=Recovery115(service)

    @app.before_request
    def security():
        g.request_id='req_'+secrets.token_hex(12)
        if request.path=='/api/v1/health' or request.path=='/' or request.path.startswith('/assets/'):return
        supplied=request.headers.get('X-JT-Admin','');actual=os.getenv('JT_ADMIN_SECRET','')
        admin=bool(actual and supplied and hmac.compare_digest(supplied,actual))
        if supplied and not admin:raise JTError('UNAUTHORIZED','Administrator token is not valid.',401)
        expired=session.get('expires',0)<=time.time()
        if expired:
            session.clear();session.update(sid=secrets.token_hex(24),csrf=secrets.token_hex(24),expires=time.time()+3600)
        owner='admin:'+digest(actual)[:24] if admin else session['sid']
        if request.method not in ('GET','HEAD','OPTIONS'):
            if not admin and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
                raise JTError('SESSION_EXPIRED' if expired else 'CSRF_REQUIRED','Reopen this page to start a new session.' if expired else 'A session token is required.',403)
            origin=request.headers.get('Origin')
            if origin and origin.rstrip('/')!=request.host_url.rstrip('/'):raise JTError('CSRF_REQUIRED','Cross-origin writes are not allowed.',403)
            key=request.headers.get('Idempotency-Key','')
            if not 8<=len(key)<=128 or not all(c.isalnum() or c in '-_' for c in key):raise JTError('IDEMPOTENCY_REQUIRED','Provide a short unique Idempotency-Key.')
        else:key=g.request_id
        g.ctx={'owner':owner,'admin':admin,'operation':key}

    @app.after_request
    def headers(response):
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Cache-Control':'no-store' if request.path.startswith('/api/') else 'public, max-age=300',
            'X-Request-ID':getattr(g,'request_id','')})
        return response

    def error_body(error):
        detail = {'code':error.code,'message':error.message,'retryable':error.retryable,'request_id':getattr(g,'request_id','req_unknown')}
        trace = getattr(error, 'trace', None)
        if trace and getattr(g, 'ctx', {}).get('admin'):
            # This request's bounded diagnostics only; no prompt, source text,
            # model output, credentials or arbitrary trace lookup is exposed.
            detail['diagnostic'] = {'trace_id':trace['trace_id'], 'attempts':[
                {k:a[k] for k in ('attempt','stage','status','provider_code','error_type','validation_errors',
                    'elapsed_ms','failed_stage_elapsed_ms','generation_timeout_ms','count_elapsed_ms',
                    'transport','chunk_count','first_chunk_ms','first_text_ms','last_chunk_ms','last_text_ms',
                    'received_text_chars','complete_stream','finish_reason','local_first_text_deadline_reached',
                    'local_total_deadline_reached') if k in a}
                for a in trace.get('attempts', [])[:2]]}
            detail['diagnostic']['elapsed_ms'] = trace.get('elapsed_ms')
            detail['diagnostic']['settings'] = {k:trace.get('settings',{})[k] for k in
                ('transport','schema_location','model_window_seconds','call_limit_seconds','first_text_timeout_seconds','attempts')
                if k in trace.get('settings',{})}
            if getattr(error, 'validation', None):
                detail['diagnostic']['validation'] = error.validation
        return {'error': detail}

    @app.errorhandler(JTError)
    def named_error(error):
        return jsonify(error_body(error)),error.status
    @app.errorhandler(HTTPException)
    def http_error(error):return named_error(JTError('HTTP_'+str(error.code),error.description,error.code))
    @app.errorhandler(Exception)
    def unexpected(error):
        # Do not log evidence, provider responses, cookies or tokens.
        app.logger.error('request=%s error_type=%s',getattr(g,'request_id','unknown'),type(error).__name__)
        return named_error(JTError('INTERNAL_ERROR','The operation stopped. Keep the request ID and refresh the saved workspace.',500))

    def mutation(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            hashed=digest([g.ctx['owner'],request.path,g.ctx['operation']]);key=('requests',hashed)
            bodyhash=digest(request.get_data(cache=True))
            def claim(values):
                prior=values[key]
                if prior:
                    if prior['body_hash']!=bodyhash:raise JTError('IDEMPOTENCY_CONFLICT','This request key was used for different content.',409)
                    if prior.get('result') is not None:return prior['result']
                    if prior['until']>time.time():raise JTError('BUSY','This request is still running.',409,True)
                    # The caller can inspect saved entities before explicitly retrying a new operation.
                    raise JTError('REQUEST_INTERRUPTED','The request was interrupted. Reopen the workspace to inspect saved state before retrying.',409)
                window=180 if request.path in ('/api/v1/teachings','/api/v1/domains/draft') or request.path.endswith('/step') else 90
                values[key]={'body_hash':bodyhash,'until':time.time()+window,'result':None};return None
            cached=repo.atomic([key],claim)
            if cached is not None:return jsonify(cached)
            try:value=fn(*args,**kwargs)
            except JTError as error:
                def fail(values):values[key]['result']=error_body(error)
                repo.atomic([key],fail);raise
            def save(values):values[key]['result']=value
            repo.atomic([key],save);return jsonify(value)
        return wrapper
    def body():
        data=request.get_json(silent=True)
        if not isinstance(data,dict):raise JTError('INVALID_INPUT','A JSON object is required.')
        return data

    @app.get('/')
    def home():return app.send_static_file('index.html')
    @app.get('/api/v1/health')
    def health():return jsonify({'status':'ok','package_version':config.VERSION,'mode':adapter.mode,'model':config.MODEL if adapter.mode=='LIVE' else 'MOCK','code_hash':config.CODE_HASH,'request_tier':config.REQUEST_TIER,'max_cost_usd':config.MAX_COST})
    @app.get('/api/v1/recovery111')
    def recovery_status():return jsonify(recovery.status(g.ctx))
    @app.post('/api/v1/recovery111/prepare')
    def recovery_prepare():return jsonify(recovery.prepare(body(),g.ctx))
    @app.post('/api/v1/recovery111/advance')
    def recovery_advance():return jsonify(recovery.advance(g.ctx, request_key=g.ctx['operation']))
    @app.get('/api/v1/recovery112')
    def recovery112_status():return jsonify(recovery112.status(g.ctx))
    @app.post('/api/v1/recovery112/prepare')
    def recovery112_prepare():return jsonify(recovery112.prepare(body(),g.ctx))
    @app.post('/api/v1/recovery112/advance')
    def recovery112_advance():return jsonify(recovery112.advance(g.ctx, request_key=g.ctx['operation']))
    @app.get('/api/v1/recovery113')
    def recovery113_status():return jsonify(recovery113.status(g.ctx))
    @app.post('/api/v1/recovery113/prepare')
    def recovery113_prepare():return jsonify(recovery113.prepare(body(),g.ctx))
    @app.post('/api/v1/recovery113/advance')
    def recovery113_advance():return jsonify(recovery113.advance(g.ctx, request_key=g.ctx['operation']))
    @app.get('/api/v1/recovery115')
    def recovery115_status():return jsonify(recovery115.status(g.ctx))
    @app.post('/api/v1/recovery115/prepare')
    def recovery115_prepare():return jsonify(recovery115.prepare(body(),g.ctx))
    @app.post('/api/v1/recovery115/advance')
    def recovery115_advance():return jsonify(recovery115.advance(g.ctx, request_key=g.ctx['operation']))
    @app.get('/api/v1/recovery114')
    def recovery114_status():return jsonify(recovery114.status(g.ctx))
    @app.post('/api/v1/recovery114/prepare')
    def recovery114_prepare():return jsonify(recovery114.prepare(body(),g.ctx))
    @app.post('/api/v1/recovery114/advance')
    def recovery114_advance():return jsonify(recovery114.advance(g.ctx, request_key=g.ctx['operation']))

    @app.get('/api/v1/session')
    def who():return jsonify({'csrf':session['csrf'],'mode':adapter.mode,'admin':g.ctx['admin'],'expires':session['expires'],'version':config.VERSION,'code_hash':config.CODE_HASH})
    @app.post('/api/v1/workspaces')
    @mutation
    def workspace_create():return service.create_workspace(body(),g.ctx)
    @app.get('/api/v1/workspaces/<wid>')
    def workspace_get(wid):return jsonify(service.summary(wid,g.ctx))
    @app.post('/api/v1/sources')
    @mutation
    def source_upload():
        file=request.files.get('file')
        if file is None:raise JTError('INVALID_INPUT','Choose a source file.')
        return service.add_source(request.form.get('workspace_id',''),file.filename,file.read(),file.mimetype,g.ctx,request.form.get('source_id') or None)
    @app.get('/api/v1/workspaces/<wid>/sources/<sid>')
    def source_download(wid,sid):
        service.workspace(wid,g.ctx);source=service.source(wid,sid)
        return send_file(io.BytesIO(blobs.get(source['blob_id'])),mimetype=source['mime'],download_name=source['name'],as_attachment=True)
    @app.post('/api/v1/domains/draft')
    @mutation
    def domain_draft():return service.draft_domain(body(),g.ctx)
    @app.post('/api/v1/sources/extract')
    @mutation
    def source_extract():return service.extract_sources(body(),g.ctx)
    @app.post('/api/v1/requirements/review')
    @mutation
    def requirements_review():
        from requirements_review import review_requirements
        return review_requirements(service,body(),g.ctx)
    @app.post('/api/v1/cases/read')
    @mutation
    def case_read():
        from case_intake import read_case
        file=request.files.get('file')
        if file is None:raise JTError('INVALID_INPUT','Choose a case file.')
        return read_case(service,request.form,file.filename,file.read(),file.mimetype,g.ctx)
    @app.post('/api/v1/cases/confirm')
    @mutation
    def case_confirm():
        from case_intake import confirm_case
        return confirm_case(service,body(),g.ctx)
    @app.post('/api/v1/history/fix')
    @mutation
    def history_fix():
        from history import fix_review,fix_result
        data=body()
        return fix_result(service,data,g.ctx) if data.get('run_id') else fix_review(service,data,g.ctx)
    @app.post('/api/v1/history/delete')
    @mutation
    def history_delete():
        from history import remove
        return remove(service,body(),g.ctx)
    @app.post('/api/v1/history/reset')
    @mutation
    def history_reset():
        from history import remove
        return remove(service,body(),g.ctx,reset=True)
    @app.get('/api/v1/workspaces/<wid>/history')
    def history_list(wid):
        from history import records
        return jsonify({'records':records(service,wid,g.ctx)})
    @app.get('/api/v1/history/<rid>')
    def history_get(rid):return jsonify(service.owned('history',rid,g.ctx))
    @app.get('/api/v1/history/<rid>/sources/<sid>')
    def history_source(rid,sid):
        record=service.owned('history',rid,g.ctx)
        source=next((s for s in record['source_metadata'] if s['source_id']==sid),None)
        if not source:raise JTError('NOT_FOUND','Source is not part of this finalized record.',404)
        return send_file(io.BytesIO(blobs.get(source['blob_id'])),mimetype=source['mime'],download_name=source['name'],as_attachment=True)
    @app.post('/api/v1/validation123/authorize')
    @mutation
    def validation_authorize():
        from validation123 import authorize
        return authorize(service,body(),g.ctx)
    @app.post('/api/v1/domains/approve')
    @mutation
    def domain_approve():return service.approve_domain(body(),g.ctx)
    @app.post('/api/v1/domains/rollback')
    @mutation
    def domain_rollback():return service.rollback(body(),g.ctx)
    @app.post('/api/v1/cases/import')
    @mutation
    def cases_import():return service.import_cases(body(),g.ctx)
    @app.post('/api/v1/workspaces/freeze')
    @mutation
    def freeze():return service.freeze(body(),g.ctx)
    @app.post('/api/v1/runs')
    @mutation
    def run_create():return service.create_run(body(),g.ctx)
    @app.get('/api/v1/runs/<rid>')
    def run_get(rid):return jsonify(service.run_view(rid,g.ctx))
    @app.post('/api/v1/runs/<rid>/step')
    def run_step(rid):return jsonify(service.step(rid,g.ctx))
    @app.post('/api/v1/runs/<rid>/cancel')
    @mutation
    def run_cancel(rid):return service.cancel(rid,g.ctx)
    @app.post('/api/v1/questions')
    @mutation
    def question():return service.question(body(),g.ctx)
    @app.post('/api/v1/teachings')
    @mutation
    def teaching():return service.teach(body(),g.ctx)
    @app.post('/api/v1/teachings/recover')
    @mutation
    def teaching_recover():
        from teaching_evidence import recover_teaching
        return recover_teaching(service,body(),g.ctx)
    @app.post('/api/v1/teachings/<tid>/approve')
    @mutation
    def teaching_approve(tid):return service.approve_teaching(tid,body(),g.ctx)
    @app.get('/api/v1/comparisons/<before_id>/<after_id>')
    def comparison(before_id,after_id):
        from comparison import compare
        return jsonify(compare(service,before_id,after_id,g.ctx))
    @app.get('/api/v1/exports/<rid>')
    def export(rid):
        value=service.run_view(rid,g.ctx,True)
        return Response(json.dumps(value,ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':f'attachment; filename="{rid}.json"'})
    return app

app=create_app()
if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT','8080')),debug=False)

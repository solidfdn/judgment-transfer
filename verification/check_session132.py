"""Actual Flask signed-cookie expiry regression, with no model or cloud calls."""
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from core.models import digest
from main import create_app
from storage.repository import LocalRepository, Blobs

checks=[]
def ok(name,value=True):assert value,name;checks.append(name)

with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'JT_SESSION_SECRET':'offline-session-check-only'}):
    repo=LocalRepository(temporary)
    app=create_app(repo=repo,adapter=SimpleNamespace(mode='MOCK'),blobs=Blobs(temporary),testing=True)
    client=app.test_client();initial=client.get('/api/v1/session')
    ok('new browser receives a protected non-permanent cookie',initial.status_code==200 and 'HttpOnly' in initial.headers['Set-Cookie'] and 'SameSite=Lax' in initial.headers['Set-Cookie'] and 'Expires=' not in initial.headers['Set-Cookie'])
    with client.session_transaction() as session:original=dict(session)
    owner=original['sid'];token=initial.json['csrf']
    ok('initial browser owner is a fresh 48-character random value',len(owner)==48 and len(token)==48)
    response=client.post('/api/v1/workspaces',json={'goal':'Session continuity check'},headers={'X-CSRF-Token':token,'Idempotency-Key':'session-check-create'})
    ok('ordinary browser creates its owned workspace',response.status_code==200)
    wid=response.json['workspace_id']
    saved=copy.deepcopy(repo.get('workspaces',wid))
    budget={'calls':11,'decisions':4};global_budget={'day':'2026-10-15','calls':538,'decisions':14,'spent_usd':17.925672};grant={'owner':owner,'authorized':True,'additional_calls':40}
    repo.put('budget',digest(owner)[:40],budget);repo.put('budget','global',global_budget);repo.put('budget','validation123',grant)
    serializer=app.session_interface.get_signing_serializer(app)
    def aged_cookie(age):
        # Sign with an old timestamp: testing only expires in the payload misses
        # Flask's separate max-age rejection before before_request runs.
        payload={**original,'expires':time.time()-1}
        with patch('itsdangerous.timed.time.time',return_value=time.time()-age):
            return serializer.dumps(payload)
    old_cookie=aged_cookie(3700);client.set_cookie(app.config['SESSION_COOKIE_NAME'],old_cookie)
    response=client.get('/api/v1/workspaces/'+wid)
    ok('cookie signed over an hour ago retains workspace access',response.status_code==200 and response.json['workspace_id']==wid)
    with client.session_transaction() as session:renewed=dict(session)
    ok('expiry renews csrf and one-hour window without replacing owner',renewed['sid']==owner and renewed['csrf']!=token and 3500<renewed['expires']-time.time()<=3600)
    ok('workspace facts and ownership stay unchanged',repo.get('workspaces',wid)==saved)
    ok('owner allowance global spend and authorization are unchanged',repo.get('budget',digest(owner)[:40])==budget and repo.get('budget','global')==global_budget and repo.get('budget','validation123')==grant)
    client.set_cookie(app.config['SESSION_COOKIE_NAME'],aged_cookie(3700))
    count_before=json.loads(repo.path.read_text())
    denied=client.post('/api/v1/workspaces',json={'goal':'Must not be created'},headers={'X-CSRF-Token':token,'Idempotency-Key':'expired-write-check'})
    ok('expired POST rejects its old csrf token',denied.status_code==403 and denied.json['error']['code']=='SESSION_EXPIRED')
    ok('rejected expired POST writes no application record',json.loads(repo.path.read_text())==count_before)
    refreshed=client.get('/api/v1/session').json
    with client.session_transaction() as session:ok('refresh after rejected POST preserves the owner',session['sid']==owner)
    accepted=client.post('/api/v1/workspaces',json={'goal':'Renewed session check'},headers={'X-CSRF-Token':refreshed['csrf'],'Idempotency-Key':'renewed-write-check'})
    ok('new csrf token authorizes a subsequent normal write',accepted.status_code==200 and repo.get('workspaces',accepted.json['workspace_id'])['owner']==owner)
    ok('renewed write does not reset any budget or grant',repo.get('budget',digest(owner)[:40])==budget and repo.get('budget','global')==global_budget and repo.get('budget','validation123')==grant)
    other=app.test_client();other.get('/api/v1/session')
    with other.session_transaction() as session:ok('another browser gets a different owner',session['sid']!=owner)
    ok('another browser cannot open original workspace',other.get('/api/v1/workspaces/'+wid).status_code==404)
    other.set_cookie(app.config['SESSION_COOKIE_NAME'],old_cookie[:-1]+('a' if old_cookie[-1]!='a' else 'b'))
    ok('tampered signed cookie cannot restore ownership',other.get('/api/v1/workspaces/'+wid).status_code==404)
    client.set_cookie(app.config['SESSION_COOKIE_NAME'],aged_cookie(32*86400))
    ok('identity validity remains bounded at 31 days',client.get('/api/v1/workspaces/'+wid).status_code==404)
    ok('session policy leaves cookie security and one-hour csrf window explicit',app.config['PERMANENT_SESSION_LIFETIME'].days==31 and app.config['SESSION_COOKIE_HTTPONLY'] and app.config['SESSION_COOKIE_SAMESITE']=='Lax')

report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,
        'runtime':{'Flask':importlib.metadata.version('Flask'),'Werkzeug':importlib.metadata.version('Werkzeug')},
        'scope':'Actual Flask test client, timestamp-aged signed cookies, and isolated local repository. Browser-owner validity is 31 days; CSRF renews after one hour. Cookies remain non-permanent.'}
(ROOT/'verification/session132_offline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

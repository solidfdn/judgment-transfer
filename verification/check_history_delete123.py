"""Offline checks of real history deletion and both storage transaction paths."""
import ast
import copy
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from core.models import JTError
from history import fix_review, records, remove
from service import Service
from storage.repository import Blobs, DELETE, FirestoreRepository, LocalRepository

checks = []
def ok(name, value=True):
    assert value, name
    checks.append(name)
def reject(name, function, code):
    try: function()
    except JTError as error: ok(name, error.code == code)
    else: raise AssertionError(name)

with tempfile.TemporaryDirectory() as directory:
    repo = LocalRepository(directory)
    svc = Service(repo, Blobs(directory), types.SimpleNamespace(mode='MOCK'))
    sequence = 0
    def ctx():
        global sequence
        sequence += 1
        return {'owner':'offline-history-owner', 'admin':True, 'operation':str(sequence)}
    ws = svc.create_workspace({'goal':'Check equipment return'}, ctx())
    wid = ws['workspace_id']
    source = svc.add_source(wid, 'return.txt', b'Return the equipment.\n', 'text/plain', ctx(), 'return_instructions')
    ws = svc.workspace(wid, ctx())
    ws['requirements_review'] = {'goal':ws['goal'], 'source_hashes':{source['source_id']:source['version_hash']}, 'summary':'Confirm receipt.', 'checks':[]}
    repo.put('workspaces', wid, ws)
    def fix(): return fix_review(svc, {'workspace_id':wid, 'reviewer_name':'Offline reviewer'}, ctx())
    first, second = fix(), fix()
    body = {'workspace_id':wid, 'record_id':first['record_id']}
    reject('deletion requires explicit confirmation', lambda:remove(svc, body, ctx()), 'CONFIRMATION_REQUIRED')
    ok('unconfirmed deletion leaves both records', len(records(svc, wid, ctx())) == 2)
    reject('foreign owner cannot delete', lambda:remove(svc, {**body,'confirmed':True}, {'owner':'someone-else'}), 'NOT_FOUND')
    other = svc.create_workspace({'goal':'Other work'}, ctx())
    reject('record cannot be deleted through another workspace', lambda:remove(svc, {**body,'workspace_id':other['workspace_id'],'confirmed':True}, ctx()), 'NOT_FOUND')
    result = remove(svc, {**body,'confirmed':True}, ctx())
    ok('selected record physically removed', result['deleted_count'] == 1 and repo.get('history', first['record_id']) is None)
    reject('deleted record unavailable by identifier', lambda:svc.owned('history', first['record_id'], ctx()), 'NOT_FOUND')
    ok('remaining snapshot unchanged including prior linkage', repo.get('history', second['record_id']) == second)
    ok('history listing excludes deleted record', [r['record_id'] for r in records(svc,wid,ctx())] == [second['record_id']])
    ok('current evidence retained', svc.blobs.get(source['blob_id']) == b'Return the equipment.\n' and svc.source(wid,source['source_id']) == source)
    third = fix()
    stale = {'workspace_id':wid,'record_ids':[second['record_id']],'confirmed':True}
    reject('stale reset preserves newly finalized record', lambda:remove(svc,stale,ctx(),reset=True), 'HISTORY_CHANGED')
    ok('stale reset changed no records', len(records(svc,wid,ctx())) == 2)
    all_ids = [second['record_id'],third['record_id']]
    reset = {'workspace_id':wid,'record_ids':all_ids,'confirmed':True}
    reject('duplicate reset identifiers rejected', lambda:remove(svc,{**reset,'record_ids':[second['record_id']]*2},ctx(),reset=True), 'INVALID_INPUT')
    # Inject a concurrent append between the initial read and the deletion transaction.
    original_atomic = repo.atomic
    def racing_atomic(keys, callback):
        if ('history',second['record_id']) in keys:
            repo.atomic = original_atomic
            fix()
        return original_atomic(keys, callback)
    repo.atomic = racing_atomic
    reject('transaction rejects concurrent history append', lambda:remove(svc,reset,ctx(),reset=True), 'HISTORY_CHANGED')
    repo.atomic = original_atomic
    ws_before = svc.workspace(wid,ctx())
    repo.put('budget','global',{'spent_usd':9.25,'calls':509})
    repo.put('runs','preserved-test',{'workspace_id':wid,'status':'COMPLETED'})
    repo.put('domains','preserved-approval',{'workspace_id':wid,'approved_by':'Earlier reviewer'})
    ids = ws_before['history_ids']
    result = remove(svc,{**reset,'record_ids':ids},ctx(),reset=True)
    ok('reset removes all selected snapshots', result['deleted_count'] == 3 and all(repo.get('history',rid) is None for rid in ids))
    ok('empty history listed after reset', records(svc,wid,ctx()) == [])
    ws_after = svc.workspace(wid,ctx())
    ok('reset retains all other workspace state', {k:v for k,v in ws_before.items() if k!='history_ids'} == {k:v for k,v in ws_after.items() if k!='history_ids'})
    ok('reset retains usage counters', repo.get('budget','global') == {'spent_usd':9.25,'calls':509})
    ok('reset retains test results and approvals', repo.get('runs','preserved-test')['status']=='COMPLETED' and repo.get('domains','preserved-approval')['approved_by']=='Earlier reviewer')
    new = fix()
    ok('new history starts after reset', new['previous_record_id'] is None and len(records(svc,wid,ctx())) == 1)

# Use the actual FirestoreRepository.atomic method with a minimal SDK transaction double.
database = {'jt_history/old':{'snapshot':'old'}, 'jt_workspaces/work':{'history_ids':['old']}}
operations = []
class Ref:
    def __init__(self, path): self.path=path
    def get(self, transaction=None):
        exists=self.path in database
        return types.SimpleNamespace(exists=exists, to_dict=lambda:{'payload':json.dumps(database[self.path])})
class Transaction:
    def set(self, ref, data): operations.append(('set',ref.path));database[ref.path]=json.loads(data['payload'])
    def delete(self, ref): operations.append(('delete',ref.path));database.pop(ref.path,None)
firestore = FirestoreRepository.__new__(FirestoreRepository)
firestore.client = types.SimpleNamespace(transaction=lambda **kwargs:Transaction(), collection=lambda name:types.SimpleNamespace(document=lambda key:Ref(name+'/'+key)))
firestore.firestore = types.SimpleNamespace(transactional=lambda function:function)
wk, hk = ('workspaces','work'), ('history','old')
def deletion(values): values[wk]['history_ids']=[];values[hk]=DELETE;return {'deleted':1}
firestore.atomic([wk,hk],deletion)
ok('Firestore transaction physically deletes snapshot', 'jt_history/old' not in database and ('delete','jt_history/old') in operations)
ok('Firestore transaction updates workspace index', database['jt_workspaces/work']['history_ids'] == [])
tree = ast.parse((ROOT/'app/main.py').read_text())
for name in ('history_delete','history_reset'):
    route=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    ok(name+' uses existing mutation guard', any(isinstance(n,ast.Name) and n.id=='mutation' for n in route.decorator_list))
report={'passed':True,'checks':checks,'real_model_calls':0,'cloud_writes':0,'runtime':'Actual history/service and local storage; actual Firestore transaction method with explicit SDK double.'}
(ROOT/'verification/history_delete_123.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks)}))

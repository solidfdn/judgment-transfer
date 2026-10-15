"""Offline checks for the separately recorded retry and its unchanged total ceiling."""
import ast,copy,hashlib,importlib.util,json,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('resume',ROOT/'releases/jt_resume_usd134.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def ok(name,value=True):assert value,name;checks.append(name)
class Stop(Exception):
    def __init__(self,code,message):self.code=code;super().__init__(message)
def reject(name,call,kind=RuntimeError):
    try:call()
    except kind:ok(name)
    else:raise AssertionError(name)
raw=(ROOT/'reference/steps/usd_demo134.py').read_bytes();source=m.revised_source(raw);compile(source,'modified-controller','exec')
ok('exact original controller hash is pinned',hashlib.sha256(raw).hexdigest()==m.CONTROLLER_HASH)
reject('changed installed controller refused',lambda:m.revised_source(raw+b'\n'))
ok('original checkpoint path is not used for new writes',"path=root/'.jt/upgrades/1.0.34/usd-demo-resume1.json'" in source and "path=root/'.jt/upgrades/1.0.34/usd-demo.json'" not in source)
ok('new requests use a separate idempotency namespace',"key='usd134resume1-'+name" in source)
restored=source.replace("usd-resume1';path=root/'.jt/upgrades/1.0.34/usd-demo-resume1.json'","usd';path=root/'.jt/upgrades/1.0.34/usd-demo.json'").replace("key='usd134resume1-'+name","key='usd134-'+name")
ok('business logic and existing four-plus-four-plus-two gates are unchanged',restored==raw.decode())
tree=ast.parse(source);run_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
scope={'Path':Path,'json':json};exec(compile(ast.Module(body=[run_node],type_ignores=[]),'actual-controller-run','exec'),scope)
with tempfile.TemporaryDirectory() as td:
    root=Path(td);old=root/m.OLD;new=root/m.NEW;old.parent.mkdir(parents=True);old.write_text(json.dumps({'status':'FAILED'}))
    fake=types.SimpleNamespace(load=lambda p:json.loads(p.read_text()) if p.exists() else {},Stop=Stop)
    new.write_text(json.dumps({'status':'PASSED','reviewer_name':'Test reviewer','report':{'status':'PASSED'}}))
    result=scope['run'](root,None,fake,'Test reviewer')
    ok('completed replacement is reopened without API/model calls',result['status']=='PASSED')
    new.write_text(json.dumps({'status':'FAILED','reviewer_name':'Test reviewer'}))
    reject('failed replacement never triggers another fresh run',lambda:scope['run'](root,None,fake,'Test reviewer'),Stop)
    ok('original failed checkpoint remains unchanged',json.loads(old.read_text())=={'status':'FAILED'})
class API:
    used=0
    def __init__(self):self.requests=[]
    def call(self,path,data=None,key=None,files=None):
        if path=='/recovery115':return {'session':{'calls':100+self.used}}
        self.requests.append((path,data,key,files));return {'ok':True}
api=API();bound=m.BoundedAPI(api,types.SimpleNamespace(Stop=Stop),100)
api.used=22;bound.call('/runs/a/step',{},key='same-key');ok('two attempts fit only when original plus replacement remain within 24',len(api.requests)==1)
api.used=23;reject('no extra case attempt can exceed the original total ceiling',lambda:bound.call('/runs/a/step',{},key='new-key'),Stop)
ok('refused case never reaches execution endpoint',len(api.requests)==1)
bound.call('/teachings',{},key='teaching');ok('single-attempt guidance can use the last available attempt',len(api.requests)==2)
api.used=24;reject('guidance stops at the same total ceiling',lambda:bound.call('/teachings',{}),Stop)
bound.call('/exports/a');ok('saved result reads remain available after allowance exhaustion',len(api.requests)==3)
view={'run':{'run_id':m.FAILED_RUN,'code_hash':m.CODE_HASH},'tasks':[
    {'status':'COMPLETED'},{'status':'COMPLETED'},{'status':'COMPLETED'},
    {'status':'FAILED','case_id':'expense_review_usd_dev_04','receipt_ids':[],'trace_ids':[m.FAILED_TRACE],'error':{'code':'MODEL_FAILED'}}],
    'traces':[{'trace_id':m.FAILED_TRACE,'attempts':[{'status':'FAILED','error_type':'ReadTimeout','chunk_count':0,'generation_timeout_ms':60000}]*2}]}
m.verify_stopped(view);ok('exact inspected no-response failure is eligible')
changed=copy.deepcopy(view);changed['tasks'][3]['receipt_ids']=['already-executed'];reject('a previously executed fourth case cannot enter this retry',lambda:m.verify_stopped(changed))
changed=copy.deepcopy(view);changed['traces'][0]['attempts'][0]['chunk_count']=1;reject('a different answer/validation failure is not treated as this timeout',lambda:m.verify_stopped(changed))
report={'passed':len(checks),'checks':checks,'new_model_calls':0,'cloud_writes':0,'scope':'Actual pinned source transformation, early resume/stop, attempt ceiling and eligibility checks using explicit local/API doubles. No live retry is claimed.'}
(ROOT/'verification/resume_usd134_offline.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

"""Synthetic-only CPU compatibility test; no biological values are loaded."""
from pathlib import Path
import os
ENVROOT=Path('D:/von-dosepilot-data/tabpfn_environment_20261007')
for k in ('TABPFN_DISABLE_TELEMETRY','DO_NOT_TRACK','HF_HUB_DISABLE_TELEMETRY','HF_HUB_OFFLINE','TABPFN_NO_BROWSER'):os.environ[k]='1'
os.environ['TABPFN_MODEL_CACHE_DIR']=str(ENVROOT/'models');os.environ['HF_HOME']=str(ENVROOT/'hf_cache')
os.environ['TMP']=str(ENVROOT/'tmp');os.environ['TEMP']=str(ENVROOT/'tmp')
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='2'
import numpy as np,torch,importlib.metadata,json,socket,hashlib,sys,time,datetime
from threadpoolctl import threadpool_limits
from core import predict_target
checkpoint=ENVROOT/'models/tabpfn-v2-regressor.ckpt'
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()=='2ab5a07d5c41dfe6db9aa7ae106fc6de898326c2765be66505a07e2868c10736'
attempts=[]
def deny(*a,**kw):attempts.append('blocked');raise RuntimeError('network forbidden during synthetic test')
socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
rng=np.random.default_rng(777);n=48
p=np.array([f'patient{i//2}' for i in range(n)]);samples=np.array([f's{i}' for i in range(n)])
a=rng.normal(size=(n,64));b=a+rng.normal(scale=.1,size=a.shape)
y=np.tile((a[:,0]+.2*a[:,1]**2)[:,None],(1,24))
owner=np.r_[np.repeat(np.arange(16),3),np.repeat(np.arange(16,24),2)]
tr=np.arange(40);te=np.arange(40,48)
torch.set_num_threads(2);torch.set_num_interop_threads(1)
start=time.perf_counter()
with threadpool_limits(limits=2):
    pr,members,context=predict_target(a,b,y,p,samples,tr,te,owner,0,0,checkpoint,contexts=[tr],return_context_arrays=True)
    altered=y.copy();altered[te]+=1000
    repeat,_,_=predict_target(a,b,altered,p,samples,tr,te,owner,0,0,checkpoint,contexts=[tr])
    aq=a.copy();bq=b.copy();aq[te[1:]]+=20;bq[te[1:]]-=10
    other,_,_=predict_target(aq,bq,y,p,samples,tr,te,owner,0,0,checkpoint,contexts=[tr])
labeldiff=float(np.max(abs(pr-repeat)));querydiff=float(np.max(abs(pr[:,0]-other[:,0])))
assert labeldiff<=1e-6 and querydiff<=1e-6,(labeldiff,querydiff)
assert not attempts and np.isfinite(pr).all()
receipt={'status':'PASS_SYNTHETIC_CPU_OFFLINE_PREFLIGHT','biological_inputs_read':False,'prediction_shape':list(pr.shape),
  'outer_label_mutation_maxdiff':labeldiff,'other_query_mutation_first_query_maxdiff':querydiff,
  'network_attempts':len(attempts),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
  'runtime_versions':{n:importlib.metadata.version(n) for n in ('tabpfn','torch','numpy','scipy','scikit-learn','joblib','einops','pydantic')},
  'seconds_for_three_two_estimator_predictions':time.perf_counter()-start,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out=Path(__file__).resolve().parent/'PREFLIGHT.json'
with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2),flush=True)

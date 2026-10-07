from pathlib import Path
import os
E=Path('D:/von-dosepilot-data/tabpfn_environment_20261007')
for k in ('TABPFN_DISABLE_TELEMETRY','DO_NOT_TRACK','HF_HUB_DISABLE_TELEMETRY','HF_HUB_OFFLINE','TABPFN_NO_BROWSER'):os.environ[k]='1'
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
os.environ['TABPFN_MODEL_CACHE_DIR']=str(E/'models');os.environ['HF_HOME']=str(E/'hf_cache');os.environ['TMP']=str(E/'tmp');os.environ['TEMP']=str(E/'tmp')
import json,time,socket,datetime,hashlib
import numpy as np,torch
from threadpoolctl import threadpool_limits
from anchor import known_contribution,predict_target
checkpoint=E/'models/tabpfn-v2-regressor.ckpt';assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()=='2ab5a07d5c41dfe6db9aa7ae106fc6de898326c2765be66505a07e2868c10736'
attempts=[]
def deny(*a,**kw):attempts.append('blocked');raise RuntimeError('offline-only synthetic test')
socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
torch.set_num_threads(1);torch.set_num_interop_threads(1)
rng=np.random.default_rng(991);a=rng.normal(size=(48,64));b=a+rng.normal(scale=.1,size=a.shape)
owner=np.r_[np.repeat(np.arange(16),3),np.repeat(np.arange(16,24),2)];weights=np.zeros((64,24))
for i,t in enumerate(owner):weights[i,t]=1/6
ka=known_contribution(a,weights);kb=known_contribution(b,weights)
y=ka+.2*np.tanh(a[:,:24]);patients=np.array([f'p{i//2}' for i in range(48)]);tr=np.arange(40);te=np.arange(40,48)
start=time.perf_counter()
with threadpool_limits(limits=1):
    first,missing=predict_target(a,b,ka,kb,y,patients,tr,te,owner,0,0,checkpoint)
    changed=y.copy();changed[te]+=137
    second,_=predict_target(a,b,ka,kb,changed,patients,tr,te,owner,0,0,checkpoint)
diff=float(np.max(np.abs(first-second)));identity=float(np.max(np.abs(first-missing-np.stack([ka[te,0],kb[te,0]]))))
assert diff<=1e-6 and identity<1e-14 and not attempts
r={'status':'PASS_SYNTHETIC_ANCHORED_CPU_PREFLIGHT','biological_inputs_read':False,'network_attempts':len(attempts),
 'prediction_shape':list(first.shape),'heldout_label_mutation_maxdiff':diff,'known_plus_missing_identity_maxdiff':identity,
 'seconds_for_two_predictions':time.perf_counter()-start,'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
 'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (Path(__file__).resolve().parent/'PREFLIGHT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(r,indent=2),flush=True)

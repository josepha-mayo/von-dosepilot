"""One source-only compression run. No organoid inputs are read."""
from pathlib import Path
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,hashlib,json,time,datetime,importlib.metadata
import numpy as np
from threadpoolctl import threadpool_limits
from model import compress_external
EXPECTED='53aae154d310256d77ddbc9c9d6ddab461235496e12009a23105620c0181b66c'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def prepare(source,destination):
    source=Path(source);destination=Path(destination);audit=destination.with_name('PROTOTYPE_BANK_AUDIT.json')
    if destination.exists() or audit.exists():raise ValueError('existing bank must not be overwritten')
    if sha(source)!=EXPECTED:raise ValueError('prepared external source hash mismatch')
    with np.load(source,allow_pickle=False) as z:
        values=z['values'];weights=z['weights'];cells=z['cell_keys'];compounds=z['nsc']
    if values.shape!=(84702,5) or len(np.unique(cells))!=60 or len(np.unique(compounds))!=1135:raise ValueError('source identity counts changed')
    began=time.perf_counter()
    with threadpool_limits(limits=1):bank=compress_external(values,weights,256)
    bank['source_cell_count']=np.asarray(len(np.unique(cells)))
    bank['source_compound_count']=np.asarray(len(np.unique(compounds)))
    np.savez_compressed(destination,**bank)
    mean_difference=float(np.max(np.abs(bank['weights']@bank['centres5']-weights@values)))
    record={'schema':'dosepilot.external_prototype_bank.v1','status':'SOURCE_ONLY_COMPRESSION_COMPLETE',
      'prepared_source_sha256':EXPECTED,'prototype_bank_sha256':sha(destination),'source_curves':84702,
      'source_cell_identifiers':60,'source_compounds':1135,'requested_prototypes':256,
      'nonempty_prototypes':len(bank['weights']),'minibatch_steps':int(bank['steps']),
      'weighted_mean_maxdiff':mean_difference,'quantization_covariance_min_eigenvalue':float(np.linalg.eigvalsh(bank['quantization_covariance5']).min()),
      'source_covariance_trace':float(np.trace(bank['covariance5'])),
      'quantization_covariance_trace':float(np.trace(bank['quantization_covariance5'])),
      'parameter_search':False,'random_state':20261008,'organoid_data_read':False,
      'raw_data_or_prototype_arrays_published':False,'new_independent_patients_claimed':False,
      'runtime_versions':{name:importlib.metadata.version(name) for name in ('numpy','scipy','scikit-learn','threadpoolctl')},
      'seconds':time.perf_counter()-began,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with audit.open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps(record,indent=2),flush=True);return record

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(a.source,a.out)

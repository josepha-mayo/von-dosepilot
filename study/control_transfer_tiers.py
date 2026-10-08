"""Fitting-only standard-control calibration of explicitly costed research tiers."""
from __future__ import annotations
import numpy as np
import pandas as pd
import local_response_tiers as local
QUALITY_COLUMNS=('p1_logrange','p2_logrange','p1_neg_logmed','p2_neg_logmed','p1_pos_logmed','p2_pos_logmed','p1_neg_cv','p2_neg_cv','p1_pos_cv','p2_pos_cv')
ARMS=('uncalibrated','asymmetric','balanced','full_common')
PRIMARY='full_common'

def load_quality(path,sample_ids):
    frame=pd.read_csv(path,dtype={'sample_id':str})
    ids=np.asarray(sample_ids).astype(str)
    if len(frame)!=len(ids) or frame['sample_id'].duplicated().any() or set(frame['sample_id'])!=set(ids):raise ValueError('exact TRAIN control identities required')
    out=frame.set_index('sample_id').loc[ids,list(QUALITY_COLUMNS)].to_numpy(float)
    if out.shape!=(len(ids),10) or not np.isfinite(out).all():raise ValueError('quality feature payload')
    return out

def features(Q,o):
    Q=np.asarray(Q,float)
    if Q.ndim!=2 or Q.shape[1]!=10 or not np.isfinite(Q).all() or o not in ('A','B'):raise ValueError('ten standard-control summaries and known layout required')
    pairs=[np.c_[Q[:,k:k+2].mean(1),(Q[:,k]-Q[:,k+1])/2] for k in (0,2,4,6,8)]
    base=np.c_[pairs[0],pairs[0][:,0]**2,pairs[1],pairs[2]]
    return base if o=='A' else np.c_[base,pairs[3],pairs[4]]

def fit(Q,residual,patients,o):
    F=features(Q,o);R=np.asarray(residual,float)
    if R.shape!=(len(F),24) or not np.isfinite(R).all():raise ValueError('fitting-only 24-target residuals required')
    w=local.tiers.patient_weights(np.asarray(patients,str));mu=w@F;Z=F-mu
    gram=Z.T@(w[:,None]*Z);lam=.125*float(np.trace(gram))/F.shape[1]
    gram=gram+max(lam,1e-12)*np.eye(F.shape[1])
    common=R.mean(1);cm=float(w@common)
    cb=np.linalg.solve(gram,Z.T@(w*(common-cm)))
    dev=R-common[:,None];dm=w@dev
    beta=np.linalg.solve(gram,Z.T@(w[:,None]*(dev-dm)))
    u,s,vt=np.linalg.svd(beta,full_matrices=False);rb=(u[:,:1]*s[:1])@vt[:1]
    return {'feature_mean':mu,'common_mean':np.asarray(cm),'common_beta':cb,'deviation_mean':dm,'rank1_beta':rb,'lambda':np.asarray(max(lam,1e-12)),'singular_values':s}

def predict(state,Q,o,arm):
    if arm not in ARMS:raise ValueError('unknown calibrated arm')
    F=features(Q,o);Z=F-state['feature_mean']
    common=state['common_mean']+Z@state['common_beta'];dev=state['deviation_mean']+Z@state['rank1_beta']
    if arm=='uncalibrated':return np.zeros((len(Q),24))
    rho=1/9 if o=='A' else 1/3
    if arm=='asymmetric':return rho*(common[:,None]+dev)
    if arm=='balanced':return (common[:,None]+dev)/3
    return common[:,None]+rho*dev

def pack(base,calibration):
    out=dict(base)
    for o,s in calibration.items():
        for k,v in s.items():out[f'calibration_{o}_{k}']=v
    return out

def unpack(state,o):
    prefix=f'calibration_{o}_'
    return {k[len(prefix):]:state[k] for k in state if k.startswith(prefix)}

def replay(state,paid,Q,o,arm,base_index):
    if len(paid)!=len(Q):raise ValueError('query/control row alignment')
    return local.replay(state,paid,base_index)+predict(unpack(state,o),Q,o,arm)

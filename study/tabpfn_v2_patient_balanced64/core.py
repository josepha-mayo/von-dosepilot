"""Local TabPFN-v2 research adapter. Built with PriorLabs-TabPFN."""
from __future__ import annotations
import hashlib
import numpy as np
SALT='von-dosepilot-tabpfn-balanced64-20261007'
SEED=202610071519


def balanced_contexts(patients,sample_ids,train_indices):
    patients=np.asarray(patients,str);sample_ids=np.asarray(sample_ids,str);ix=np.asarray(train_indices,int)
    if patients.shape!=sample_ids.shape or ix.ndim!=1 or len(ix)==0 or len(np.unique(ix))!=len(ix):
        raise ValueError('unique aligned training rows required')
    if ix.min()<0 or ix.max()>=len(patients) or len(np.unique(sample_ids))!=len(sample_ids):
        raise ValueError('invalid sample identities')
    groups=np.unique(patients[ix]);ordered=[]
    for group in groups:
        rows=ix[patients[ix]==group]
        order=sorted(rows,key=lambda i:(hashlib.sha256((SALT+'|'+sample_ids[i]).encode()).hexdigest(),sample_ids[i]))
        ordered.append(order)
    contexts=[np.array([rows[k%len(rows)] for rows in ordered],int) for k in (0,1)]
    for context in contexts:
        if len(context)!=len(groups) or len(np.unique(patients[context]))!=len(groups):raise ValueError('patient balance failed')
    return contexts


def feature_order(owner,target):
    owner=np.asarray(owner,int)
    if owner.shape!=(64,) or set(owner)!=set(range(24)) or not 0<=target<24:raise ValueError('physical target ownership required')
    return np.r_[np.flatnonzero(owner==target),np.flatnonzero(owner!=target)]


def from_paid(paid,orientation,order):
    x=np.asarray(paid,float);order=np.asarray(order,int)
    if x.ndim!=2 or x.shape[1]!=64 or not np.isfinite(x).all():raise ValueError('64 finite purchased measurements required; no imputation')
    if orientation not in ('A','B') or order.shape!=(64,) or set(order)!=set(range(64)):
        raise ValueError('invalid layout or column mapping')
    return np.column_stack((x[:,order],np.full(len(x),0. if orientation=='A' else 1.)))


def predict_target(paid_A,paid_B,y,patients,sample_ids,train_indices,test_indices,owner,target,fold,checkpoint,contexts=None,return_context_arrays=False):
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion
    tr=np.asarray(train_indices,int);te=np.asarray(test_indices,int);p=np.asarray(patients,str)
    if set(p[tr])&set(p[te]):raise ValueError('whole-patient training/test overlap')
    if not np.isfinite(np.asarray(y)[tr,target]).all():raise ValueError('nonfinite training targets')
    contexts=balanced_contexts(p,sample_ids,tr) if contexts is None else contexts
    order=feature_order(owner,target)
    qa=from_paid(np.asarray(paid_A)[te],'A',order);qb=from_paid(np.asarray(paid_B)[te],'B',order)
    query=np.concatenate((qa,qb));all_predictions=[];context_arrays=[]
    for context_index,rows in enumerate(contexts):
        if not set(rows).issubset(set(tr)):raise ValueError('context escaped fitting rows')
        xa=from_paid(np.asarray(paid_A)[rows],'A',order);xb=from_paid(np.asarray(paid_B)[rows],'B',order)
        context_x=np.concatenate((xa,xb));context_y=np.tile(np.asarray(y)[rows,target],2)
        seed=SEED+1000*fold+10*target+context_index
        reg=TabPFNRegressor.create_default_for_version(ModelVersion.V2,n_estimators=2,auto_scale_n_estimators=False,
             model_path=str(checkpoint),device='cpu',random_state=seed,n_preprocessing_jobs=1,
             fit_mode='fit_preprocessors',show_progress_bar=False)
        reg.fit(context_x,context_y)
        prediction=np.asarray(reg.predict(query),float)
        if prediction.shape!=(len(query),) or not np.isfinite(prediction).all():raise ValueError('invalid model prediction')
        all_predictions.append(prediction.reshape(2,len(te)))
        if return_context_arrays:context_arrays.append({'x':context_x,'y':context_y,'query':query,'seed':seed,'row_indices':rows})
        del reg
    answer=np.mean(all_predictions,axis=0)
    return answer,np.asarray(all_predictions),context_arrays

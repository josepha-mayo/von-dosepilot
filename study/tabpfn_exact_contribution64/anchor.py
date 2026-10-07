"""TabPFN residual prediction around the EXACT purchased contribution to an AUC.
Built with PriorLabs-TabPFN. Only missing contribution is modelled.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent
spec=importlib.util.spec_from_file_location('frozen_direct_feature_contract',STUDY/'tabpfn_v2_patient_balanced64/core.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def observed_weights(plan,full_quadrature,query_to_full,orientation):
    if orientation not in ('A','B'):raise ValueError('unknown physical layout')
    native=np.asarray(plan['selected_native_indices'],int);plates=np.asarray(plan[f'orientation_{orientation}_plate_indices'],int)
    mapping=np.asarray(query_to_full,int);q=np.asarray(full_quadrature,float)
    if native.shape!=(64,) or len(set(native))!=64 or plates.shape!=(64,) or not np.isin(plates,(0,1)).all():
        raise ValueError('64 distinct eligible native doses required')
    if np.bincount(plates,minlength=2).tolist()!=[32,32]:raise ValueError('32/32 physical budget required')
    if native.min()<0 or native.max()>=len(mapping) or q.ndim!=2 or q.shape[1]!=24 or not np.isfinite(q).all():
        raise ValueError('endpoint mapping mismatch')
    indices=2*mapping[native]+plates
    if indices.max()>=len(q) or indices.min()<0 or len(set(indices))!=64:raise ValueError('physical query mapping invalid')
    weights=q[indices].copy()
    if weights.min()<-1e-12 or np.any(weights.sum(axis=0)>1+1e-12):raise ValueError('invalid quadrature coefficients')
    return weights


def known_contribution(paid,weights):
    x=np.asarray(paid,float);w=np.asarray(weights,float)
    if x.ndim!=2 or x.shape[1]!=64 or w.shape!=(64,24) or not np.isfinite(x).all() or not np.isfinite(w).all():
        raise ValueError('complete finite paid inputs and fixed weights required')
    return x@w


def predict_target(paid_A,paid_B,known_A,known_B,y,patients,tr,te,owner,target,fold,checkpoint):
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion
    tr=np.asarray(tr,int);te=np.asarray(te,int);p=np.asarray(patients,str);y=np.asarray(y,float)
    if set(p[tr])&set(p[te]):raise ValueError('whole-patient overlap')
    if not np.isfinite(y[tr,target]).all():raise ValueError('invalid fitting labels')
    order=base.feature_order(owner,target)
    xa=base.from_paid(np.asarray(paid_A)[tr],'A',order);xb=base.from_paid(np.asarray(paid_B)[tr],'B',order)
    qa=base.from_paid(np.asarray(paid_A)[te],'A',order);qb=base.from_paid(np.asarray(paid_B)[te],'B',order)
    observed_train=np.r_[known_A[tr,target],known_B[tr,target]]
    labels=np.tile(y[tr,target],2)-observed_train
    observed_query=np.r_[known_A[te,target],known_B[te,target]]
    if not np.isfinite(labels).all() or not np.isfinite(observed_query).all():raise ValueError('invalid exact contribution')
    reg=TabPFNRegressor.create_default_for_version(ModelVersion.V2,n_estimators=2,auto_scale_n_estimators=False,
        model_path=str(checkpoint),device='cpu',random_state=base.SEED+1000*fold+10*target,
        n_preprocessing_jobs=1,fit_mode='fit_preprocessors',show_progress_bar=False)
    reg.fit(np.r_[xa,xb],labels)
    missing=np.asarray(reg.predict(np.r_[qa,qb]),float)
    if missing.shape!=observed_query.shape or not np.isfinite(missing).all():raise ValueError('bad residual prediction')
    prediction=(observed_query+missing).reshape(2,len(te))
    return prediction,missing.reshape(2,len(te))

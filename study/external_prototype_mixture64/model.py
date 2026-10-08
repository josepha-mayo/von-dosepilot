"""Nonlinear mixture retaining the same first two moments as the prior trial.
Source profiles are compressed to weighted centroids without private outcomes.
Component covariance is adjusted algebraically, not fitted on evaluation loss.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util
import numpy as np
SPEC=importlib.util.spec_from_file_location('frozen_external_shrink_model',Path(__file__).resolve().parent.parent/'external_shape_shrink64/model.py')
original=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(original)
external_covariance=original.external_covariance
relative_correlation=original.relative_correlation
fit_target=original.fit_target
condition=original.condition
COMPONENT_DISPERSION=.5
SOURCE_MASS=.5


def compress_external(values,weights,n_clusters=256):
    from sklearn.cluster import MiniBatchKMeans
    x=np.asarray(values,float);w=np.asarray(weights,float)
    covariance=external_covariance(x,w)
    if n_clusters<2 or len(x)<n_clusters:raise ValueError('invalid prototype count')
    estimator=MiniBatchKMeans(n_clusters=n_clusters,random_state=20261008,n_init=1,batch_size=4096,
       max_iter=100,max_no_improvement=20,reassignment_ratio=.01,tol=0.)
    estimator.fit(x,sample_weight=w*len(w))
    labels=estimator.predict(x);mass=np.bincount(labels,weights=w,minlength=n_clusters)
    sums=np.zeros((n_clusters,5));np.add.at(sums,labels,w[:,None]*x)
    active=mass>0;centres=sums[active]/mass[active,None];mass=mass[active]
    mean=w@x;centered=centres-mean;between=centered.T@(mass[:,None]*centered)
    remainder=(covariance-between+covariance.T-between.T)/2
    if np.linalg.eigvalsh(remainder).min()<-1e-10:raise ValueError('prototype compression moment decomposition failed')
    if np.max(np.abs(mass@centres-mean))>1e-12:raise ValueError('prototype mean not preserved')
    return {'centres5':centres,'weights':mass,'mean5':mean,'covariance5':covariance,
       'quantization_covariance5':remainder,'source_curve_count':np.asarray(len(x)),
       'steps':np.asarray(estimator.n_steps_),'prototype_count':np.asarray(len(mass))}


def mixture_population(target,curves,patients,positions,bank):
    x=np.asarray(curves,float);w=original.patient_weights(patients)
    if x.ndim!=3 or x.shape[2]!=2 or len(x)!=len(w):raise ValueError('paired fitting curves required')
    t=np.asarray(positions,float);d=x.shape[1]
    if t.shape!=(d,) or np.any(np.diff(t)<=0) or t.min()<0 or t.max()>1:raise ValueError('relative dose positions')
    grid=np.linspace(0,1,5);eye=np.eye(5)
    transform=np.stack([np.interp(t,grid,eye[:,j]) for j in range(5)],axis=1)
    mu=x.mean(2);mean=w@mu;centered=mu-mean;local_sd=np.sqrt(np.maximum(np.diag(centered.T@(w[:,None]*centered)),0))
    source_cov=transform@bank['covariance5']@transform.T
    source_sd=np.sqrt(np.maximum(np.diag(source_cov),1e-14))
    transformed=mean+((bank['centres5']-bank['mean5'])@transform.T)*(local_sd/source_sd)[None,:]
    points=np.concatenate((mu,transformed));mass=np.concatenate(((1-SOURCE_MASS)*w,SOURCE_MASS*bank['weights']))
    if abs(mass.sum()-1)>1e-12 or not np.isfinite(points).all():raise ValueError('mixed component population')
    deviations=points-mean;bias=mass@deviations
    if np.max(np.abs(bias))>1e-10:raise ValueError('external mean alignment failed')
    deviations-=bias
    full_deviation=np.repeat(deviations,2,axis=1)*np.sqrt(COMPONENT_DISPERSION)
    full_means=target['mean'][None,:]+full_deviation
    between=full_deviation.T@(mass[:,None]*full_deviation)
    common=target['covariance']-between;common=(common+common.T)/2
    np.linalg.cholesky(common)
    recovered_mean=mass@full_means;rec_cov=common+(full_means-recovered_mean).T@(mass[:,None]*(full_means-recovered_mean))
    error=max(float(np.max(np.abs(recovered_mean-target['mean']))),float(np.max(np.abs(rec_cov-target['covariance']))))
    if error>1e-10:raise ValueError('mixture does not match declared Gaussian moments')
    return {'means':full_means,'common_covariance':common,'weights':mass,'moment_maxdiff':error}


def condition_mixture(population,physical_indices,quadrature):
    means=np.asarray(population['means'],float);cov=np.asarray(population['common_covariance'],float)
    weights=np.asarray(population['weights'],float);indices=np.asarray(physical_indices,int);q=np.asarray(quadrature,float)
    if means.ndim!=2 or q.shape!=(means.shape[1],) or cov.shape!=(means.shape[1],means.shape[1]):raise ValueError('mixture dimensions')
    if indices.ndim!=1 or len(indices)==0 or len(np.unique(indices))!=len(indices) or indices.min()<0 or indices.max()>=len(q):raise ValueError('distinct physical coordinates')
    if weights.shape!=(len(means),) or np.any(weights<=0) or abs(weights.sum()-1)>1e-12:raise ValueError('mixture masses')
    css=cov[np.ix_(indices,indices)];precision=np.linalg.solve(css,np.eye(len(indices)))
    beta=np.linalg.solve(css,cov[indices]@q);observed=means[:,indices]
    return {'observed_means':observed,'precision':precision,'beta':beta,
            'offsets':means@q-observed@beta,'weights':weights}


def predict_mixture(state,paid):
    x=np.asarray(paid,float)
    if x.ndim!=2 or x.shape[1]!=len(state['beta']) or not np.isfinite(x).all():raise ValueError('complete finite paid target measurements required')
    difference=x[:,None,:]-state['observed_means'][None,:,:]
    distance=np.einsum('bni,ij,bnj->bn',difference,state['precision'],difference)
    log_mass=np.log(state['weights'])[None,:]-.5*distance
    log_mass-=log_mass.max(axis=1,keepdims=True);posterior=np.exp(log_mass);posterior/=posterior.sum(axis=1,keepdims=True)
    prediction=x@state['beta']+posterior@state['offsets']
    if not np.isfinite(prediction).all():raise ValueError('nonfinite conditional mixture')
    return prediction

"""Transfer external relative-dose correlation, not external potency or endpoints.
The assay mean, variance scale and paired-plate disagreement are estimated only
from the current fitting organoid patients. Inference accepts paid cells only.
"""
from __future__ import annotations
import numpy as np
EXTERNAL_STRENGTH=.5
DIAGONAL_SHRINKAGE=.1
VARIANCE_FLOOR=1e-6


def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or len(p)==0:raise ValueError('nonempty patient vector required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1./(len(ids)*count[inv])


def external_covariance(values,weights):
    v=np.asarray(values,float);w=np.asarray(weights,float)
    if v.ndim!=2 or v.shape[1]!=5 or w.shape!=(len(v),):raise ValueError('five-point source curves required')
    if not np.isfinite(v).all() or not np.isfinite(w).all() or np.any(w<=0) or abs(w.sum()-1)>1e-12:raise ValueError('invalid external source')
    centered=v-w@v
    cov=centered.T@(w[:,None]*centered)
    return (cov+cov.T)/2


def relative_correlation(covariance5,positions):
    c=np.asarray(covariance5,float);t=np.asarray(positions,float)
    if c.shape!=(5,5) or t.ndim!=1 or len(t)<2 or not np.isfinite(c).all() or not np.isfinite(t).all():raise ValueError('invalid source covariance or positions')
    if t.min()<0 or t.max()>1 or np.any(np.diff(t)<=0):raise ValueError('strictly ordered relative dose positions required')
    if np.linalg.eigvalsh((c+c.T)/2).min()<-1e-10:raise ValueError('non-PSD source covariance')
    eye=np.eye(5);grid=np.linspace(0,1,5)
    mapping=np.stack([np.interp(t,grid,eye[:,j]) for j in range(5)],axis=1)
    cov=mapping@c@mapping.T;diag=np.diag(cov)
    if diag.min()<=1e-14:return np.eye(len(t))
    sd=np.sqrt(diag);cor=cov/(sd[:,None]*sd[None,:]);cor=(cor+cor.T)/2
    if np.linalg.eigvalsh(cor).min()<-1e-9:raise ValueError('source interpolation covariance invalid')
    return cor


def fit_target(curves,patients,source_correlation,strength):
    x=np.asarray(curves,float);corr=np.asarray(source_correlation,float)
    if x.ndim!=3 or x.shape[2]!=2 or len(x)!=len(patients) or not np.isfinite(x).all():raise ValueError('finite paired fitting curves required')
    d=x.shape[1]
    if corr.shape!=(d,d) or not np.isfinite(corr).all() or strength not in (0.,.5):raise ValueError('outside frozen transfer family')
    if np.linalg.eigvalsh((corr+corr.T)/2).min()<-1e-9:raise ValueError('invalid source correlation')
    w=patient_weights(patients);mean_curve=x.mean(axis=2);contrast=(x[:,:,0]-x[:,:,1])/2
    mean_mu=w@mean_curve;mean_delta=w@contrast
    mu=mean_curve-mean_mu;delta=contrast-mean_delta
    cmu=mu.T@(w[:,None]*mu);cdelta=delta.T@(w[:,None]*delta)
    sd=np.sqrt(np.maximum(np.diag(cmu),0.))
    external=sd[:,None]*corr*sd[None,:]
    cmu=(1-strength)*cmu+strength*external
    cmu=(1-DIAGONAL_SHRINKAGE)*cmu+DIAGONAL_SHRINKAGE*np.diag(np.diag(cmu))+VARIANCE_FLOOR*np.eye(d)
    cdelta=(1-DIAGONAL_SHRINKAGE)*cdelta+DIAGONAL_SHRINKAGE*np.diag(np.diag(cdelta))+VARIANCE_FLOOR*np.eye(d)
    dose=np.repeat(np.arange(d),2);sign=np.tile([1.,-1.],d)
    cov=cmu[np.ix_(dose,dose)]+sign[:,None]*sign[None,:]*cdelta[np.ix_(dose,dose)]
    cov=(cov+cov.T)/2;np.linalg.cholesky(cov)
    mean=(mean_mu[:,None]+mean_delta[:,None]*np.array([1.,-1.])[None,:]).reshape(-1)
    return {'mean':mean,'covariance':cov,'mean_covariance':cmu,'contrast_covariance':cdelta,
            'external_strength':float(strength)}


def condition(target,physical_indices,quadrature):
    mean=np.asarray(target['mean'],float);cov=np.asarray(target['covariance'],float)
    ix=np.asarray(physical_indices,int);q=np.asarray(quadrature,float)
    if cov.shape!=(len(mean),len(mean)) or q.shape!=mean.shape or ix.ndim!=1 or len(ix)==0 or len(set(ix))!=len(ix):raise ValueError('conditional shape/index mismatch')
    if ix.min()<0 or ix.max()>=len(mean) or not all(np.isfinite(a).all() for a in (mean,cov,q)):raise ValueError('invalid conditional inputs')
    css=cov[np.ix_(ix,ix)];cross=cov[ix]@q
    beta=np.linalg.solve(css,cross)
    if np.max(np.abs(css@beta-cross))>1e-10:raise ValueError('conditional normal equations')
    return {'mean_x':mean[ix],'mean_y':float(mean@q),'beta':beta}


def predict(state,paid):
    x=np.asarray(paid,float)
    if x.ndim!=2 or x.shape[1]!=len(state['mean_x']) or not np.isfinite(x).all():raise ValueError('complete purchased values required')
    return state['mean_y']+(x-state['mean_x'])@state['beta']

"""Empirical smooth-curve mixture, conditioned on purchased physical values.
All population estimation consumes FITTING patients only. Query APIs accept
only the selected observations, never a complete historical curve.
"""
from __future__ import annotations
import numpy as np
CENTERS=np.linspace(-.25,1.25,25)
SLOPES=(2.,4.,8.,16.)
AMPLITUDE_RIDGE=.001
COVARIANCE_SHRINKAGE=.5
RESIDUAL_VARIANCE_FLOOR=.0001


def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or not len(p):raise ValueError('nonempty patient vector required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1./(len(ids)*count[inv])


def smooth_templates(curves,log_positions):
    x=np.asarray(curves,float);t=np.asarray(log_positions,float)
    if x.ndim!=3 or x.shape[2]!=2 or t.shape!=(x.shape[1],) or len(t)<3:
        raise ValueError('sample/dose/two-plate curves and dose coordinates required')
    if not np.isfinite(x).all() or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('finite curves with increasing coordinates required')
    if t[0]!=0 or abs(t[-1]-1)>1e-12:raise ValueError('normalized full log-dose interval required')
    y=x.mean(axis=2);n,d=y.shape
    best=np.repeat(y.mean(1)[:,None],d,axis=1)
    best_loss=np.mean((y-best)**2,axis=1)
    parameter=np.column_stack([y.mean(1),np.zeros((n,3))])
    identity=np.eye(2);identity[0,0]=0
    for slope in SLOPES:
        for center in CENTERS:
            sigmoid=1./(1.+np.exp(np.clip(-slope*(t-center),-60.,60.)))
            design=np.column_stack([np.ones(d),sigmoid])
            gram=design.T@design/d+AMPLITUDE_RIDGE*identity
            beta=np.linalg.solve(gram,design.T@y.T/d).T
            estimate=beta@design.T
            loss=np.mean((y-estimate)**2,axis=1)+AMPLITUDE_RIDGE*beta[:,1]**2
            improve=loss<best_loss-1e-15
            best[improve]=estimate[improve];best_loss[improve]=loss[improve]
            parameter[improve]=np.column_stack([beta[improve],np.full(np.sum(improve),center),np.full(np.sum(improve),slope)])
    return np.repeat(best[:,:,None],2,axis=2).reshape(n,-1),parameter


def fit_population(curves,log_positions,patients):
    x=np.asarray(curves,float)
    if len(x)!=len(patients):raise ValueError('patient/curve alignment mismatch')
    smooth,parameter=smooth_templates(x,log_positions)
    raw=x.reshape(len(x),-1);w=patient_weights(patients)
    residual=raw-smooth;systematic=w@residual;centered=residual-systematic
    dimension=raw.shape[1];df_multiplier=dimension/max(dimension-4,1)
    empirical=(centered.T@(w[:,None]*centered))*df_multiplier
    cov=(1-COVARIANCE_SHRINKAGE)*empirical+COVARIANCE_SHRINKAGE*np.diag(np.diag(empirical))
    cov+=RESIDUAL_VARIANCE_FLOOR*np.eye(dimension);cov=(cov+cov.T)/2
    np.linalg.cholesky(cov)
    return {'means':smooth+systematic,'covariance':cov,'weights':w,
            'shape_parameters':parameter,'df_multiplier':np.asarray(df_multiplier)}


def condition(population,indices,quadrature,mode='mixture'):
    means=np.asarray(population['means'],float);cov=np.asarray(population['covariance'],float)
    weights=np.asarray(population['weights'],float);ix=np.asarray(indices,int);q=np.asarray(quadrature,float)
    if means.ndim!=2 or cov.shape!=(means.shape[1],means.shape[1]) or q.shape!=(means.shape[1],):
        raise ValueError('full-curve population and scalar endpoint required')
    if ix.ndim!=1 or len(ix)==0 or len(np.unique(ix))!=len(ix) or ix.min()<0 or ix.max()>=len(q):
        raise ValueError('distinct valid physical indices required')
    if weights.shape!=(len(means),) or (weights<=0).any() or abs(weights.sum()-1)>1e-12:
        raise ValueError('positive normalized mixture weights required')
    if not all(np.isfinite(a).all() for a in (means,cov,weights,q)):
        raise ValueError('nonfinite population')
    if mode not in ('mixture','gaussian_control'):raise ValueError('unknown fixed arm')
    if mode=='gaussian_control':
        mean=weights@means;deviation=means-mean
        total=cov+deviation.T@(weights[:,None]*deviation)
        slope=np.linalg.solve(total[np.ix_(ix,ix)],total[ix]@q)
        return {'mode':np.asarray(1),'mean_x':mean[ix],'mean_y':np.asarray(mean@q),'slope':slope}
    observed_cov=cov[np.ix_(ix,ix)]
    inverse=np.linalg.solve(observed_cov,np.eye(len(ix)))
    slope=np.linalg.solve(observed_cov,cov[ix]@q)
    observed_means=means[:,ix]
    offsets=means@q-observed_means@slope
    return {'mode':np.asarray(0),'observed_means':observed_means,'inverse_covariance':inverse,
            'slope':slope,'component_offsets':offsets,'weights':weights.copy()}


def predict(state,paid):
    x=np.asarray(paid,float)
    if x.ndim!=2 or x.shape[1]!=len(state['slope']) or not np.isfinite(x).all():
        raise ValueError('complete finite purchased values required')
    if int(state['mode'])==1:
        return state['mean_y']+(x-state['mean_x'])@state['slope']
    difference=x[:,None,:]-state['observed_means'][None,:,:]
    distance=np.einsum('bni,ij,bnj->bn',difference,state['inverse_covariance'],difference)
    logw=np.log(state['weights'])[None,:]-.5*distance
    logw-=np.max(logw,axis=1,keepdims=True)
    posterior=np.exp(logw);posterior/=posterior.sum(axis=1,keepdims=True)
    prediction=x@state['slope']+posterior@state['component_offsets']
    if not np.isfinite(prediction).all():raise ValueError('invalid posterior prediction')
    return prediction

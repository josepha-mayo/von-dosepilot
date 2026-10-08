"""Finite-grid AUC conditioning, with exact purchased-cell contribution.
Inference consumes one 64-well layout only. Training may use full Lib1 curves.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import nnls

POOLING=(0.0,0.5,1.0)

def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or not len(p):raise ValueError('patients must be nonempty')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*count[inv])

def covariance_basis(doses):
    """Eleven PSD covariance components over interleaved two-plate cells."""
    doses=np.asarray(doses,float)
    if doses.ndim!=1 or len(doses)<2 or not np.isfinite(doses).all() or (doses<=0).any() or (np.diff(doses)<=0).any():
        raise ValueError('increasing finite positive concentrations required')
    t=np.log(doses);t=(t-t[0])/(t[-1]-t[0]);z=2*t-1
    kernels=[np.ones((len(t),len(t))),z[:,None]*z[None,:]]
    for length in (.25,.5,1.0):
        kernels.append(np.exp(-((t[:,None]-t[None,:])/length)**2/2))
    # Shared between source plates, correlated within plate, independent per well.
    basis=[np.kron(k,np.ones((2,2))) for k in kernels]
    basis+=[np.kron(k,np.eye(2)) for k in kernels]
    basis.append(np.eye(2*len(t)))
    return np.stack(basis)

def fit_population(full,patients):
    values=np.asarray(full['values'],float);owner=np.asarray(full['owner'],int)
    doses=np.asarray(full['doses'],float);w=patient_weights(patients)
    if values.ndim!=3 or values.shape[2]!=2 or len(values)!=len(w) or not np.isfinite(values).all():
        raise ValueError('complete fitting-only two-plate curves required')
    if owner.shape!=(values.shape[1],) or doses.shape!=owner.shape or set(owner)!=set(range(24)):
        raise ValueError('24 target full-grid alignment')
    stats=[];designs=[];targets=[]
    for j in range(24):
        native=np.flatnonzero(owner==j);a=values[:,native,:]
        xx=np.r_[a.reshape(len(a),-1),a[:,:,::-1].reshape(len(a),-1)]
        ww=np.tile(w,2)/2;mu=ww@xx;center=xx-mu
        empirical=(center.T*ww)@center
        scale=max(float(np.trace(empirical)/len(mu)),.05**2)
        basis=covariance_basis(doses[native]);design=basis.reshape(11,-1).T/len(mu)
        response=(empirical/scale).ravel()/len(mu)
        coef,_=nnls(design,response,maxiter=1000)
        stats.append({'native':native,'mean':mu,'scale':scale,'basis':basis,'local_coef':coef})
        designs.append(design);targets.append(response)
    pooled,_=nnls(np.concatenate(designs),np.concatenate(targets),maxiter=1000)
    for s in stats:s['pooled_coef']=pooled
    return stats

def known_plus_missing(covariance,mean,quadrature,observed):
    """y = observed @ q_observed + conditional expectation of missing terms.
This preserves exact measured quadrature contributions even with a model prior.
The full-observation limit is exactly the known endpoint, not a smoothed label.
"""
    C=np.asarray(covariance,float);mu=np.asarray(mean,float);Q=np.asarray(quadrature,float)
    observed=np.asarray(observed,int)
    if C.shape!=(len(mu),len(mu)) or Q.ndim!=2 or Q.shape[0]!=len(mu):raise ValueError('prior shape')
    if not np.isfinite(C).all() or not np.isfinite(mu).all() or not np.isfinite(Q).all():raise ValueError('nonfinite prior')
    if observed.ndim!=1 or len(set(observed.tolist()))!=len(observed) or np.any(observed<0) or np.any(observed>=len(mu)):
        raise ValueError('physical observation identity')
    missing=np.setdiff1d(np.arange(len(mu)),observed)
    known=Q[observed].copy()
    if len(missing):
        K=C[np.ix_(observed,observed)]
        cross=C[np.ix_(observed,missing)]@Q[missing]
        extra=np.linalg.solve(K,cross)
        if np.max(abs(K@extra-cross))>1e-9:raise ValueError('conditioning solve')
        beta=known+extra
    else:beta=known
    intercept=mu@Q-mu[observed]@beta
    return beta,intercept,known

def condition(populations,plan,full,pooling):
    if pooling not in POOLING:raise ValueError('not a frozen pooling rule')
    q=np.asarray(full['q'],float);query_to_full=np.asarray(full['query_to_full'],int)
    selected=np.asarray(plan['selected_native_indices'],int)
    target=np.asarray(plan['coordinate_target_indices'],int)
    if q.shape[1]!=24 or selected.shape!=(64,) or target.shape!=(64,):raise ValueError('64 well 24 endpoint requirement')
    states={}
    for orientation in ('A','B'):
        plates=np.asarray(plan[f'orientation_{orientation}_plate_indices'],int)
        beta=np.zeros((64,24));known=np.zeros_like(beta);intercept=np.zeros(24)
        for j,s in enumerate(populations):
            native=s['native'];positions=np.flatnonzero(target==j)
            lookup={int(v):k for k,v in enumerate(native)}
            observed=np.asarray([2*lookup[int(query_to_full[selected[pos]])]+int(plates[pos]) for pos in positions])
            cells=np.column_stack((2*native,2*native+1)).ravel()
            Q=q[cells][:,[j]]
            coefs=(1-pooling)*s['local_coef']+pooling*s['pooled_coef']
            covariance=s['scale']*(np.einsum('k,kij->ij',coefs,s['basis'])+1e-6*np.eye(len(cells)))
            b,i,k=known_plus_missing(covariance,s['mean'],Q,observed)
            beta[positions,j]=b[:,0];known[positions,j]=k[:,0];intercept[j]=i[0]
        states[orientation]={'beta_raw':beta,'intercept':intercept,'known_weights':known}
    return states

def predict(state,paid,orientation):
    paid=np.asarray(paid,float)
    if orientation not in ('A','B') or paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():
        raise ValueError('exactly 64 finite paid values of one layout required')
    return state[orientation]['intercept']+paid@state[orientation]['beta_raw']

def exact_paid_weights(plan,full,orientation):
    sel=np.asarray(plan['selected_native_indices'],int)
    plate=np.asarray(plan[f'orientation_{orientation}_plate_indices'],int)
    return np.asarray(full['q'])[2*np.asarray(full['query_to_full'])[sel]+plate]

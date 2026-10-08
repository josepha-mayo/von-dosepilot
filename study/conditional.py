"""Full-curve Gaussian conditioning with shared factors and drug-local residuals.
Training can read complete historical TRAIN curves. Inference accepts only the
64 purchased values of ONE alternative plate layout.
"""
from __future__ import annotations
import numpy as np


def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or len(p)==0: raise ValueError('nonempty patient vector required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*count[inv])


def quadrature_weights(doses, bounds):
    d=np.asarray(doses,float);lo,hi=map(float,bounds)
    if d.ndim!=1 or len(d)<2 or not np.isfinite(d).all() or (d<=0).any() or np.any(np.diff(d)<=0):
        raise ValueError('strictly increasing positive finite doses required')
    if not np.isfinite([lo,hi]).all() or not d[0]<=lo<hi<=d[-1]:
        raise ValueError('target interval must be bracketed')
    x=np.log(d);a,b=np.log([lo,hi]);nodes=np.r_[a,x[(x>a)&(x<b)],b]
    eye=np.eye(len(d));interp=np.stack([np.interp(nodes,x,eye[:,j]) for j in range(len(d))],axis=1)
    q=np.sum(np.diff(nodes)[:,None]*(interp[:-1]+interp[1:])/2,axis=0)/(b-a)
    if abs(q.sum()-1)>1e-12 or (q<-1e-12).any():raise ValueError('invalid quadrature')
    return q


def exact_auc_map(catalog,bounds):
    m=len(catalog.native_ids);t=len(catalog.target_ids)
    output=np.zeros((m*2,t))
    for j,target in enumerate(catalog.target_ids):
        cols=np.flatnonzero(catalog.native_target_indices==j)
        order=np.argsort([float(catalog.concentrations[c]) for c in cols]);cols=cols[order]
        q=quadrature_weights([float(catalog.concentrations[c]) for c in cols],bounds[str(target)])
        for c,v in zip(cols,q):output[2*c:2*c+2,j]=v/2
    return output


def fit_population(replicates,patients,owner,rank,shrinkage=.1):
    x=np.asarray(replicates,float);owner=np.asarray(owner,int)
    if x.ndim!=3 or x.shape[2]!=2 or len(x)!=len(patients):raise ValueError('aligned full TRAIN curves required')
    if owner.shape!=(x.shape[1],) or not np.isfinite(x).all():raise ValueError('malformed curves/ownership')
    if rank not in (0,4,12) or shrinkage!=.1:raise ValueError('outside frozen population family')
    v=x.reshape(len(x),-1);w=patient_weights(patients);mean=w@v
    scale=np.maximum(np.sqrt(w@((v-mean)**2)),.05)
    z=(v-mean)/scale;weighted=np.sqrt(w)[:,None]*z
    empirical=weighted.T@weighted
    if rank:
        _,s,vt=np.linalg.svd(weighted,full_matrices=False)
        r=min(rank,len(s));factor=vt[:r].T*s[:r]
        low=factor@factor.T
    else:low=np.zeros_like(empirical)
    covariance=low.copy();owners=np.repeat(owner,2)
    max_negative=0.
    for j in np.unique(owners):
        block=np.flatnonzero(owners==j)
        residual=empirical[np.ix_(block,block)]-low[np.ix_(block,block)]
        residual=(residual+residual.T)/2
        e,u=np.linalg.eigh(residual);max_negative=min(max_negative,float(e.min()))
        if e.min()<-1e-8:raise ValueError('factor residual is not PSD')
        residual=(u*np.maximum(e,0))@u.T
        diagonal=np.maximum(np.diag(residual),1e-8)
        covariance[np.ix_(block,block)]+=(1-shrinkage)*residual+shrinkage*np.diag(diagonal)
    covariance=(covariance+covariance.T)/2
    return {'mean':mean,'scale':scale,'covariance':covariance,'rank':rank,
            'residual_negative_eigenvalue':max_negative,'native_count':x.shape[1]}


def condition(population,plan,auc_map,query_to_full=None):
    mean=population['mean'];scale=population['scale'];cov=population['covariance']
    q=np.asarray(auc_map,float)
    if q.shape[0]!=len(mean) or not np.isfinite(q).all():raise ValueError('quadrature map mismatch')
    native=np.asarray(plan['selected_native_indices'],int)
    if query_to_full is not None:native=np.asarray(query_to_full,int)[native]
    result={'mean_y':mean@q,'orientations':{},'quadrature':q}
    for orientation in ('A','B'):
        plate=np.asarray(plan[f'orientation_{orientation}_plate_indices'],int)
        if native.shape!=plate.shape or not np.isin(plate,(0,1)).all():raise ValueError('layout mismatch')
        indices=2*native+plate
        if len(np.unique(indices))!=len(indices):raise ValueError('duplicate physical observation')
        css=cov[np.ix_(indices,indices)]
        cross=cov[indices]@(scale[:,None]*q)
        beta=np.linalg.solve(css,cross)
        residual=float(np.max(np.abs(css@beta-cross)))
        if residual>1e-9 or not np.isfinite(beta).all():raise ValueError('conditional solve failed')
        result['orientations'][orientation]={'mean_x':mean[indices],'scale_x':scale[indices],
             'beta':beta,'indices':indices,'normal_equation_error':residual}
    return result


def predict(state,paid,orientation):
    if orientation not in ('A','B'):raise ValueError('unknown layout')
    s=state['orientations'][orientation];x=np.asarray(paid,float)
    if x.ndim!=2 or x.shape[1]!=len(s['mean_x']) or not np.isfinite(x).all():
        raise ValueError('only complete purchased query values are permitted')
    return state['mean_y']+((x-s['mean_x'])/s['scale_x'])@s['beta']

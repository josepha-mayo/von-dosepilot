"""Fitting-only mean/contrast covariance; inference sees one purchased layout."""
from __future__ import annotations
import numpy as np

CONFIGS=((0,0,0.),(4,0,0.),(0,2,0.),(4,2,0.),(12,2,0.),(4,2,.25))

def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or len(p)==0:raise ValueError('nonempty patient vector required')
    ids,inv,n=np.unique(p,return_inverse=True,return_counts=True)
    return 1./(len(ids)*n[inv])

def structured_covariance(z,w,owner,rank,shrink=.1):
    z=np.asarray(z,float);w=np.asarray(w,float);owner=np.asarray(owner,int)
    if z.ndim!=2 or w.shape!=(len(z),) or owner.shape!=(z.shape[1],):raise ValueError('covariance alignment')
    if not np.isfinite(z).all() or abs(w.sum()-1)>1e-12 or (w<=0).any():raise ValueError('covariance values')
    weighted=np.sqrt(w)[:,None]*z
    empirical=weighted.T@weighted
    if rank:
        _,s,vt=np.linalg.svd(weighted,full_matrices=False)
        factor=vt[:rank].T*s[:rank]
        low=factor@factor.T
    else:low=np.zeros_like(empirical)
    out=low.copy()
    for j in np.unique(owner):
        ix=np.flatnonzero(owner==j)
        residual=empirical[np.ix_(ix,ix)]-low[np.ix_(ix,ix)]
        residual=(residual+residual.T)/2
        e,u=np.linalg.eigh(residual)
        if e.min()<-1e-8:raise ValueError('non-PSD block residual')
        residual=(u*np.maximum(e,0.))@u.T
        diag=np.maximum(np.diag(residual),1e-8)
        out[np.ix_(ix,ix)]+=(1-shrink)*residual+shrink*np.diag(diag)
    return (out+out.T)/2,empirical

def fit_populations(full_values,patients,owner):
    x=np.asarray(full_values,float)
    if x.ndim!=3 or x.shape[2]!=2 or len(x)!=len(patients) or not np.isfinite(x).all():
        raise ValueError('complete fitting-only two-plate curves required')
    w=patient_weights(patients)
    m=x.mean(2);d=(x[:,:,0]-x[:,:,1])/2
    mu=w@m;du=w@d
    scale=np.maximum(np.sqrt(w@((m-mu)**2+(d-du)**2)),.05)
    zm=(m-mu)/scale;zd=(d-du)/scale
    means={r:structured_covariance(zm,w,owner,r) for r in (0,4,12)}
    diffs={r:structured_covariance(zd,w,owner,r) for r in (0,2)}
    empirical_cross=(zm.T*w)@zd
    output=[]
    for mr,dr,gamma in CONFIGS:
        cm,em=means[mr];cd,ed=diffs[dr]
        output.append({'mean_m':mu,'mean_d':du,'scale':scale,
            'cm':(1-gamma)*cm+gamma*em,'cd':(1-gamma)*cd+gamma*ed,
            'cmd':gamma*empirical_cross,'config':(mr,dr,gamma)})
    return output

def conditional_coefficients(cm,cd,cmd,indices,sign,target_map,relative_ridge=.01):
    """Condition [M,D] on M[indices]+sign*D[indices] and predict target_map^T M."""
    idx=np.asarray(indices,int);s=np.asarray(sign,float);q=np.asarray(target_map,float)
    m=np.asarray(cm,float);d=np.asarray(cd,float);cross=np.asarray(cmd,float)
    n=len(m)
    if m.shape!=(n,n) or d.shape!=m.shape or cross.shape!=m.shape or q.shape[0]!=n:
        raise ValueError('conditional covariance dimensions')
    if idx.ndim!=1 or s.shape!=idx.shape or np.any(idx<0) or np.any(idx>=n) or not np.isin(s,(-1,1)).all():
        raise ValueError('purchased observation index/sign')
    if len(set(zip(idx.tolist(),s.tolist())))!=len(idx):raise ValueError('duplicate physical observations')
    ix=np.ix_(idx,idx)
    cov=m[ix]+s[:,None]*d[ix]*s[None,:]+cross[ix]*s[None,:]+s[:,None]*cross.T[ix]
    cov=(cov+cov.T)/2
    cov=cov+float(relative_ridge)*np.diag(np.maximum(np.diag(cov),1e-8))
    cy=(m[idx]+s[:,None]*cross.T[idx])@q
    beta=np.linalg.solve(cov,cy)
    if not np.isfinite(beta).all() or np.max(np.abs(cov@beta-cy))>1e-9:
        raise ValueError('conditional solve failed')
    return beta

def condition_population(pop,plan,quadrature,query_to_full):
    native=np.asarray(query_to_full,int)[np.asarray(plan['selected_native_indices'],int)]
    q=np.asarray(quadrature,float)
    q_m=q[0::2]+q[1::2]
    if q_m.shape!=(len(pop['mean_m']),24):raise ValueError('24-target quadrature mapping')
    mean_y=pop['mean_m']@q_m
    target_map=pop['scale'][:,None]*q_m
    out={'mean_y':mean_y,'config':pop['config'],'orientations':{}}
    for o in ('A','B'):
        plate=np.asarray(plan[f'orientation_{o}_plate_indices'],int)
        sign=1-2*plate
        beta=conditional_coefficients(pop['cm'],pop['cd'],pop['cmd'],native,sign,target_map,.01)
        out['orientations'][o]={'mean_x':pop['mean_m'][native]+sign*pop['mean_d'][native],
            'scale_x':pop['scale'][native],'beta':beta}
    return out

def predict(state,paid,orientation):
    if orientation not in ('A','B'):raise ValueError('unknown alternative layout')
    p=np.asarray(paid,float);s=state['orientations'][orientation]
    if p.ndim!=2 or p.shape[1]!=64 or not np.isfinite(p).all():raise ValueError('exactly 64 finite purchased values required')
    return state['mean_y']+((p-s['mean_x'])/s['scale_x'])@s['beta']

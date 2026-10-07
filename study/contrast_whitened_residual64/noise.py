"""Output-space transforms estimated strictly from fitting-patient plate contrasts."""
from __future__ import annotations
import numpy as np


def contrast_transforms(target_replicates, patients):
    reps=np.asarray(target_replicates,float);p=np.asarray(patients,str)
    if reps.ndim!=3 or reps.shape[2]!=2 or len(reps)!=len(p) or len(reps)==0:
        raise ValueError('aligned sample/target/two-plate arrays required')
    if not np.isfinite(reps).all(): raise ValueError('nonfinite plate targets')
    n,t,_=reps.shape
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    w=1./(len(ids)*count[inv])
    d=(reps[:,:,0]-reps[:,:,1])/2
    d-=w@d
    cov=d.T@(w[:,None]*d);cov=(cov+cov.T)/2
    mu=float(np.trace(cov)/t);eye=np.eye(t)
    matrices=[eye,eye,eye] if mu<=1e-12 else [eye,(.5*np.diag(np.diag(cov))+.5*mu*eye)/mu,(.5*cov+.5*mu*eye)/mu]
    transforms=[]
    for name,a in zip(('identity','diagonal_contrast','full_contrast'),matrices):
        if name=='identity' or mu<=1e-12:
            white=eye.copy();color=eye.copy();e=np.ones(t)
        else:
            e,u=np.linalg.eigh(a)
            if e.min()<=0: raise ValueError('nonpositive covariance proxy')
            white=(u*(1/np.sqrt(e)))@u.T
            color=(u*np.sqrt(e))@u.T
        if np.max(np.abs(white@color-eye))>1e-10: raise ValueError('whitening inverse failed')
        transforms.append({'name':name,'white':white,'color':color,'min_eigenvalue':float(e.min()),'max_eigenvalue':float(e.max()),'mean_contrast_variance':mu})
    return transforms

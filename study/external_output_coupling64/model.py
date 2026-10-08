"""Matrix-valued ridge kernel with an externally fixed output covariance.
Established separable multi-task kernel, not a new method claim. The exact
Kronecker solve is evaluated through two small eigendecompositions.
"""
from __future__ import annotations
import numpy as np
PENALTIES=(.1,1.,10.)

def coefficients(eigenvalues,eigenvectors,weights,residuals,output_covariance,penalty):
    e,u,w,y,c=[np.asarray(x,float) for x in (eigenvalues,eigenvectors,weights,residuals,output_covariance)]
    if y.ndim!=2 or e.shape!=(len(y),) or u.shape!=(len(y),len(y)) or w.shape!=(len(y),) or c.shape!=(y.shape[1],y.shape[1]):raise ValueError('aligned weighted eigensystem and outputs required')
    if not all(np.isfinite(v).all() for v in (e,u,w,y,c)) or (w<=0).any() or abs(w.sum()-1)>1e-12:raise ValueError('invalid finite numerical inputs')
    if np.max(np.abs(c-c.T))>1e-10 or e.min()<-1e-10 or penalty<=0:raise ValueError('PSD kernel and positive penalty required')
    ce,cv=np.linalg.eigh((c+c.T)/2)
    if ce.min()<=0:raise ValueError('output covariance must be positive definite')
    sw=np.sqrt(w);rotated=u.T@(sw[:,None]*y)@cv
    solution=rotated/(np.maximum(e,0)[:,None]+penalty/ce[None,:])
    result=sw[:,None]*(u@solution)@cv.T
    if not np.isfinite(result).all():raise ValueError('nonfinite multitask solution')
    return result

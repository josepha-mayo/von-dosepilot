"""Smooth the singular spectrum of a design-whitened residual correction.

For H=Z'WZ+lambda*I and L L'=H, write T=L'B and G=L^{-1}Z'WR.
Minimizing ||G-T||_F^2+2*tau*||T||_* gives soft singular-value
thresholding. This is a transformed penalty, not ||B||_* itself.
"""
from __future__ import annotations
import numpy as np
from scipy.linalg import solve_triangular
from residual_rank import ResidualRank


def soft_reduced_ridge(gram, cross, penalty, fraction):
    if penalty<=0 or not np.isfinite(penalty) or fraction not in (0.,.1,.3,.6,1.):
        raise ValueError('Unregistered spectrum shrinkage')
    gram,cross=np.asarray(gram,float),np.asarray(cross,float)
    if not np.isfinite(gram).all() or not np.isfinite(cross).all():raise ValueError('Nonfinite system')
    lower=np.linalg.cholesky(gram+penalty*np.eye(len(gram)))
    transformed=solve_triangular(lower,cross,lower=True)
    u,s,vt=np.linalg.svd(transformed,full_matrices=False)
    shrunk=np.maximum(s-fraction*s[0],0.)
    b=solve_triangular(lower.T,(u*shrunk)@vt,lower=False)
    return b,s,shrunk


def fit_soft(context, base, penalty, fraction):
    cross=context.cxy-context.cxx@base.beta
    b,s,sv=soft_reduced_ridge(context.cxx,cross,penalty,fraction)
    return ResidualRank(base,b,s,int(np.count_nonzero(sv)),float(penalty))

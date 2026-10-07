"""Joint penalized own-target linear effects and a shared input kernel.
No file access. Each output uses only its own coordinates in its linear term.
"""
from __future__ import annotations
import numpy as np


def solve_joint(z, centered_y, weights, owner, eigenvalues, eigenvectors,
                kernel_penalty, linear_penalty=0.01):
    z, y, w = (np.asarray(v, float) for v in (z, centered_y, weights))
    owner = np.asarray(owner, int)
    e, u = np.asarray(eigenvalues, float), np.asarray(eigenvectors, float)
    if z.ndim != 2 or y.ndim != 2 or len(z) != len(y):
        raise ValueError('aligned matrices required')
    n, m = z.shape
    if w.shape != (n,) or owner.shape != (m,) or e.shape != (n,) or u.shape != (n,n):
        raise ValueError('shape mismatch')
    if not all(np.isfinite(v).all() for v in (z,y,w,e,u)):
        raise ValueError('nonfinite input')
    if (w <= 0).any() or abs(w.sum()-1)>1e-12 or (e < -1e-10).any():
        raise ValueError('invalid weights/eigenvalues')
    if set(owner) != set(range(y.shape[1])):
        raise ValueError('each target needs an owned coordinate')
    if kernel_penalty <= 0 or linear_penalty <= 0:
        raise ValueError('positive penalties required')
    sw = np.sqrt(w)
    b = u.T @ (sw[:,None] * z)
    c = u.T @ (sw[:,None] * y)
    inv = 1.0 / (np.maximum(e,0.0) + kernel_penalty)
    beta = np.zeros((m,y.shape[1]))
    alpha_eigen = np.empty_like(y)
    max_stationarity = 0.0
    for target in range(y.shape[1]):
        cols = np.flatnonzero(owner == target)
        bj = b[:,cols]
        system = kernel_penalty * (bj.T @ (inv[:,None]*bj)) + linear_penalty*np.eye(len(cols))
        rhs = kernel_penalty * bj.T @ (inv*c[:,target])
        beta[cols,target] = np.linalg.solve(system,rhs)
        alpha_eigen[:,target] = inv*(c[:,target]-bj@beta[cols,target])
        discrepancy = bj.T@(kernel_penalty*alpha_eigen[:,target])-linear_penalty*beta[cols,target]
        max_stationarity = max(max_stationarity,float(np.max(np.abs(discrepancy))))
    coef = sw[:,None]*(u@alpha_eigen)
    if max_stationarity > 1e-9 or not np.isfinite(coef).all():
        raise ValueError('joint normal equations failed')
    return {'beta':beta,'coef':coef,'max_stationarity_error':max_stationarity}


def predict_joint(z_query, centered_cross, state):
    zq, kq = np.asarray(z_query,float), np.asarray(centered_cross,float)
    if zq.ndim != 2 or kq.ndim != 2 or len(zq)!=len(kq):
        raise ValueError('query matrices required')
    if zq.shape[1]!=state['beta'].shape[0] or kq.shape[1]!=state['coef'].shape[0]:
        raise ValueError('query dimensions changed')
    if not np.isfinite(zq).all() or not np.isfinite(kq).all():
        raise ValueError('nonfinite query')
    return zq@state['beta']+kq@state['coef']

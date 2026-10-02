"""Weighted hybrid-kernel spectral correction with train-only centering."""
from __future__ import annotations
import numpy as np


def kernel(x,z,nonlinear=True):
    x,z=np.asarray(x,float),np.asarray(z,float)
    if x.ndim!=2 or z.ndim!=2 or x.shape[1]!=z.shape[1] or not np.isfinite(x).all() or not np.isfinite(z).all():raise ValueError('Invalid kernel inputs')
    linear=x@z.T
    if not nonlinear:return linear
    d=x.shape[1];squared=np.maximum((x*x).sum(1)[:,None]+(z*z).sum(1)[None,:]-2*linear,0.)
    return linear+d*np.exp(-squared/(2*d))


class KernelSpectral:
    def __init__(self,z,residual,weights,nonlinear=True):
        self.z=np.asarray(z,float).copy();self.w=np.asarray(weights,float).copy();self.residual=np.asarray(residual,float).copy();self.nonlinear=bool(nonlinear)
        if self.w.shape!=(len(self.z),) or self.residual.ndim!=2 or len(self.residual)!=len(self.z) or not np.isfinite(self.residual).all() or not np.isfinite(self.w).all() or (self.w<=0).any() or abs(self.w.sum()-1)>1e-12:raise ValueError('Invalid weights or residuals')
        raw=kernel(self.z,self.z,self.nonlinear);self.train_mean=self.w@raw;self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w);matrix=self.sw[:,None]*centered*self.sw[None,:]
        matrix=(matrix+matrix.T)/2
        e,u=np.linalg.eigh(matrix)
        if e.min()<-1e-10:raise ValueError('Kernel is not positive semidefinite')
        self.e=np.maximum(e,0.);self.u=u
        self.ur=u.T@(self.sw[:,None]*self.residual)

    def coefficients(self,penalty,fraction):
        if penalty<=0 or not np.isfinite(penalty) or not 0<=fraction<=1:raise ValueError('Invalid spectral option')
        matrix=self.ur.T@((self.e/(self.e+penalty))[:,None]*self.ur)
        eig,vec=np.linalg.eigh((matrix+matrix.T)/2)
        o=np.argsort(eig)[::-1];s=np.sqrt(np.maximum(eig[o],0.));vec=vec[:,o]
        ratio=np.divide(np.maximum(s-fraction*s[0],0.),s,out=np.zeros_like(s),where=s>1e-15)
        projector=(vec*ratio)@vec.T
        coef=self.sw[:,None]*(self.u@(self.ur/(self.e+penalty)[:,None]))@projector
        return coef,s,projector

    def centered_cross(self,z):
        raw=kernel(z,self.z,self.nonlinear)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand

    def predict(self,z,coefficients):
        return self.centered_cross(z)@coefficients

    def arrays(self,coefficients):
        return {'z_training':self.z,'weights':self.w,'train_kernel_mean':self.train_mean,'kernel_grand':self.grand,'dual_coefficients':coefficients,'nonlinear':np.asarray(self.nonlinear)}

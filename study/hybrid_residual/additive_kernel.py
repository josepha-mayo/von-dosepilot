"""Low-dimensional Gaussian dose-group features with shared output shrinkage."""
from __future__ import annotations
import numpy as np
from kernel_spectral import KernelSpectral

class AdditiveKernel(KernelSpectral):
    def __init__(self,z,residual,weights,owner):
        self.z=np.asarray(z,float).copy();self.residual=np.asarray(residual,float).copy();self.w=np.asarray(weights,float).copy();self.owner=np.asarray(owner);self.nonlinear=True
        if self.z.ndim!=2 or self.z.shape[1]!=64 or not np.isfinite(self.z).all() or self.owner.shape!=(64,) or self.owner.dtype.kind not in 'iu':raise ValueError('Invalid fitting features or ownership')
        if set(self.owner)!=set(range(24)):raise ValueError('Exactly24owner groups required')
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if sorted(map(len,self.groups))!=[2]*8+[3]*16:raise ValueError('Original64well allocation required')
        if self.w.shape!=(len(z),) or not np.isfinite(self.w).all() or (self.w<=0).any() or abs(self.w.sum()-1)>1e-12 or self.residual.shape!=(len(z),24) or not np.isfinite(self.residual).all():raise ValueError('Invalid fitting responses or weights')
        raw=self.raw_cross(self.z);self.train_mean=self.w@raw;self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w);matrix=self.sw[:,None]*centered*self.sw[None,:]
        e,u=np.linalg.eigh((matrix+matrix.T)/2)
        if e.min()<-1e-10:raise ValueError('Kernel is not positive semidefinite')
        self.e=np.maximum(e,0.);self.u=u;self.ur=u.T@(self.sw[:,None]*self.residual)
    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():raise ValueError('64 finite query coordinates required')
        result=z@self.z.T
        for group in self.groups:
            a,b=z[:,group],self.z[:,group];dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(group)*np.exp(-dist/(2*len(group)))
        return result
    def centered_cross(self,z):
        raw=self.raw_cross(z)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
    def arrays(self,coefficients):return dict(super().arrays(coefficients),kernel_owner=self.owner)

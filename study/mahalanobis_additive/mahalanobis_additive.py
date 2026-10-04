"""Response-free covariance-aware geometry for the frozen bandwidth-0.7 additive kernel."""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel

class MahalanobisAdditive(AdditiveKernel):
    """Replace each drug group's Euclidean RBF distance by a shrunk correlation metric.

    The metric is fitted from standardized purchased inputs only. rho=0 recovers
    the ordinary bandwidth-0.7 Euclidean group kernel; the prefrozen candidate
    uses rho=0.5.
    """
    def __init__(self,z,residual,weights,owner,rho=.5,bandwidth=.7):
        self.rho=float(rho);self.bandwidth=float(bandwidth)
        if not np.isfinite(self.rho) or not 0<=self.rho<=1:
            raise ValueError('rho must be finite in [0,1]')
        if not np.isfinite(self.bandwidth) or self.bandwidth<=0:
            raise ValueError('bandwidth must be positive')
        self.z=np.asarray(z,float).copy()
        self.residual=np.asarray(residual,float).copy()
        self.w=np.asarray(weights,float).copy()
        self.owner=np.asarray(owner)
        self.nonlinear=True
        if self.z.ndim!=2 or self.z.shape[1]!=64 or not np.isfinite(self.z).all() or self.owner.shape!=(64,) or self.owner.dtype.kind not in 'iu':
            raise ValueError('Invalid fitting features or ownership')
        if set(self.owner)!=set(range(24)):
            raise ValueError('Exactly24owner groups required')
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if sorted(map(len,self.groups))!=[2]*8+[3]*16:
            raise ValueError('Original64well allocation required')
        if self.w.shape!=(len(z),) or not np.isfinite(self.w).all() or (self.w<=0).any() or abs(self.w.sum()-1)>1e-12 or self.residual.shape!=(len(z),24) or not np.isfinite(self.residual).all():
            raise ValueError('Invalid fitting responses or weights')
        self.precisions=self._fit_precisions()
        raw=self.raw_cross(self.z)
        self.train_mean=self.w@raw
        self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w)
        matrix=self.sw[:,None]*centered*self.sw[None,:]
        e,u=np.linalg.eigh((matrix+matrix.T)/2)
        if e.min()<-1e-10:
            raise ValueError('Kernel is not positive semidefinite')
        self.e=np.maximum(e,0.)
        self.u=u
        self.ur=u.T@(self.sw[:,None]*self.residual)

    def _fit_precisions(self):
        values=[]
        for group in self.groups:
            x=self.z[:,group]
            mean=self.w@x
            centered=x-mean
            cov=(centered.T*self.w)@centered
            variance=np.maximum(np.diag(cov),1e-12)
            denom=np.sqrt(variance[:,None]*variance[None,:])
            corr=np.divide(cov,denom,out=np.zeros_like(cov),where=denom>0)
            corr=(corr+corr.T)/2
            np.fill_diagonal(corr,1.)
            d=len(group)
            shrunk=(1-self.rho)*np.eye(d)+self.rho*corr
            precision=np.linalg.inv(shrunk)
            precision=(precision+precision.T)/2
            precision*=d/np.trace(precision)
            if not np.isfinite(precision).all() or np.linalg.eigvalsh(precision).min()<=0:
                raise ValueError('Invalid Mahalanobis precision')
            values.append(precision)
        return values

    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():
            raise ValueError('64 finite query coordinates required')
        result=z@self.z.T
        scale=self.bandwidth*self.bandwidth
        for group,precision in zip(self.groups,self.precisions):
            delta=z[:,None,group]-self.z[None,:,group]
            dist=np.einsum('abi,ij,abj->ab',delta,precision,delta,optimize=True)
            dist=np.maximum(dist,0.)
            result+=len(group)*np.exp(-dist/(2*len(group)*scale))
        return result

    def arrays(self,coefficients):
        padded=np.zeros((24,3,3))
        dims=np.empty(24,dtype=np.int64)
        for j,p in enumerate(self.precisions):
            d=len(p);padded[j,:d,:d]=p;dims[j]=d
        return dict(super().arrays(coefficients),
                    kernel_bandwidth_multiplier=np.asarray(self.bandwidth),
                    mahalanobis_rho=np.asarray(self.rho),
                    mahalanobis_precision_padded=padded,
                    mahalanobis_group_dims=dims)

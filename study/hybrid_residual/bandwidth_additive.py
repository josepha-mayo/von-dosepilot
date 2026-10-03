"""Additive drug-group Gaussian kernel with an explicit global lengthscale.

The historical additive model corresponds to multiplier 1.0. The verified
successor uses multiplier 0.7. This module is additive: old source files and
their receipt hashes remain unchanged.
"""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel

class BandwidthAdditive(AdditiveKernel):
    def __init__(self,z,residual,weights,owner,multiplier=.7):
        self.multiplier=float(multiplier)
        if not np.isfinite(self.multiplier) or self.multiplier<=0:
            raise ValueError('Invalid additive-kernel bandwidth multiplier')
        super().__init__(z,residual,weights,owner)
    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():
            raise ValueError('64 finite query coordinates required')
        result=z@self.z.T
        scale=self.multiplier*self.multiplier
        for group in self.groups:
            a,b=z[:,group],self.z[:,group]
            dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(group)*np.exp(-dist/(2*len(group)*scale))
        return result
    def arrays(self,coefficients):
        return dict(super().arrays(coefficients),
                    kernel_bandwidth_multiplier=np.asarray(self.multiplier))
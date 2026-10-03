"""Response-free per-drug-group bandwidth geometry.

The 24 local multipliers are derived only from the standardized purchased-input
cloud and whole-patient fitting weights. No response target enters this rule.
Their geometric mean is fixed to the verified global value 0.7.
"""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel

GLOBAL_BANDWIDTH=.7

def weighted_median(values,weights):
    values=np.asarray(values,float);weights=np.asarray(weights,float)
    if values.ndim!=1 or weights.shape!=values.shape or len(values)==0:
        raise ValueError("Bad weighted median input")
    if (not np.isfinite(values).all() or not np.isfinite(weights).all()
            or (weights<0).any() or weights.sum()<=0):
        raise ValueError("Bad weighted median values")
    order=np.argsort(values,kind="mergesort");v=values[order];w=weights[order]
    return float(v[np.searchsorted(np.cumsum(w),.5*w.sum(),side="left")])

def local_multipliers(z,weights,owner):
    z=np.asarray(z,float);weights=np.asarray(weights,float);owner=np.asarray(owner,int)
    if (z.ndim!=2 or z.shape[1]!=64 or weights.shape!=(len(z),)
            or owner.shape!=(64,) or not np.isfinite(z).all()
            or not np.isfinite(weights).all() or (weights<0).any()
            or weights.sum()<=0):
        raise ValueError("Bad local-bandwidth inputs")
    groups=[np.flatnonzero(owner==j) for j in range(24)]
    if sorted(map(len,groups))!=[2]*8+[3]*16:
        raise ValueError("Bad group allocation")
    if len(z)<2:
        raise ValueError("At least two fitting rows are required")
    iu=np.triu_indices(len(z),1)
    pair_w=(weights[:,None]*weights[None,:])[iu]
    raw=[]
    for group in groups:
        a=z[:,group]
        dist=((a[:,None,:]-a[None,:,:])**2).sum(2)[iu]
        q=weighted_median(dist,pair_w)
        raw.append(1. if q<=1e-12 else np.sqrt(q/(2*len(group))))
    raw=np.asarray(raw)
    geo=float(np.exp(np.mean(np.log(raw))))
    ell=GLOBAL_BANDWIDTH*np.sqrt(raw/geo)
    if not np.isfinite(ell).all() or (ell<=0).any():
        raise ValueError("Invalid local multipliers")
    if abs(float(np.exp(np.mean(np.log(ell))))-GLOBAL_BANDWIDTH)>1e-12:
        raise ValueError("Bandwidth normalization failed")
    return ell

class LocalBandwidthAdditive(AdditiveKernel):
    def __init__(self,z,residual,weights,owner):
        self.local_multipliers=local_multipliers(z,weights,owner)
        super().__init__(z,residual,weights,owner)

    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():
            raise ValueError("64 finite query coordinates required")
        result=z@self.z.T
        for ell,group in zip(self.local_multipliers,self.groups):
            a,b=z[:,group],self.z[:,group]
            dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(group)*np.exp(-dist/(2*len(group)*ell*ell))
        return result

    def arrays(self,coefficients):
        return dict(super().arrays(coefficients),
                    kernel_bandwidth_multiplier=np.asarray(GLOBAL_BANDWIDTH),
                    local_bandwidth_multipliers=self.local_multipliers)

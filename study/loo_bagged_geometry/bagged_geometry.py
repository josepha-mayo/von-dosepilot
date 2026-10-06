"""Leave-one-whole-patient empirical kernel bagging over response-free bandwidths."""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel
from median_bandwidth import estimate_group_bandwidths

def loo_bandwidth_ensemble(z,weights,owner,patient_ids):
    z=np.asarray(z,float);weights=np.asarray(weights,float);patient_ids=np.asarray(patient_ids,str)
    medians,raw=estimate_group_bandwidths(z,weights,owner,patient_ids)
    groups=np.unique(patient_ids);G=len(groups)
    if G<4:raise ValueError("At least four patients required")
    loo=np.empty((G,24),float)
    for i,g in enumerate(groups):
        keep=patient_ids!=g;wk=weights[keep].copy();wk/=wk.sum()
        _,loo[i]=estimate_group_bandwidths(z[keep],wk,owner,patient_ids[keep])
    if not np.isfinite(loo).all() or (loo<=0).any():raise ValueError("Invalid LOO bandwidths")
    return medians,raw,loo

def empirical_rbf_bag(distance,group_size,bandwidths):
    distance=np.asarray(distance,float);b=np.asarray(bandwidths,float)
    if b.ndim!=1 or not len(b) or (b<=0).any() or not np.isfinite(b).all():raise ValueError("bandwidths")
    scale=2.0*float(group_size)*b*b
    acc=np.zeros_like(distance,float)
    for s in scale:acc+=np.exp(-distance/s)
    return acc/len(scale)

class LeaveOnePatientBaggedBandwidth(AdditiveKernel):
    def __init__(self,z,residual,weights,owner,patient_ids):
        self.fitting_patient_ids=np.asarray(patient_ids,str).copy()
        self.group_medians,self.raw_group_bandwidths,self.loo_group_bandwidths=loo_bandwidth_ensemble(
            z,weights,owner,self.fitting_patient_ids)
        super().__init__(z,residual,weights,owner)
    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():raise ValueError("64 finite query coordinates required")
        result=z@self.z.T
        for target,group in enumerate(self.groups):
            a,b=z[:,group],self.z[:,group]
            dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(group)*empirical_rbf_bag(dist,len(group),self.loo_group_bandwidths[:,target])
        return result
    def arrays(self,coefficients):
        return dict(super().arrays(coefficients),
          kernel_group_distance_medians=self.group_medians,
          kernel_raw_group_bandwidth_multipliers=self.raw_group_bandwidths,
          kernel_loo_group_bandwidth_multipliers=self.loo_group_bandwidths,
          kernel_fitting_patient_ids=self.fitting_patient_ids)

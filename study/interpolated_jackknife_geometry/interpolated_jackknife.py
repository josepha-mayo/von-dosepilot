"""Jackknife bias correction for midpoint-CDF interpolated response-free bandwidths."""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel
from interpolated_geometry import estimate_interpolated_bandwidths

def interpolated_jackknife_bandwidths(z,weights,owner,patient_ids):
    z=np.asarray(z,float);weights=np.asarray(weights,float);patient_ids=np.asarray(patient_ids,str)
    medians,raw=estimate_interpolated_bandwidths(z,weights,owner,patient_ids)
    groups=np.unique(patient_ids);G=len(groups)
    if G<4:raise ValueError("At least four patients required")
    theta=np.log(raw);loo=np.empty((G,24),float)
    for i,g in enumerate(groups):
        keep=patient_ids!=g;wk=weights[keep].copy();wk/=wk.sum()
        _,b=estimate_interpolated_bandwidths(z[keep],wk,owner,patient_ids[keep]);loo[i]=np.log(b)
    mean_loo=loo.mean(0);theta_bc=G*theta-(G-1)*mean_loo;corrected=np.exp(theta_bc)
    if not np.isfinite(corrected).all() or (corrected<=0).any():raise ValueError("Invalid corrected bandwidths")
    return medians,raw,mean_loo,theta_bc,corrected

class InterpolatedJackknifeBandwidth(AdditiveKernel):
    def __init__(self,z,residual,weights,owner,patient_ids):
        self.fitting_patient_ids=np.asarray(patient_ids,str).copy()
        (self.group_medians,self.raw_group_bandwidths,self.mean_loo_log_bandwidth,
         self.bias_corrected_log_bandwidth,self.group_bandwidths)=interpolated_jackknife_bandwidths(
             z,weights,owner,self.fitting_patient_ids)
        super().__init__(z,residual,weights,owner)
    def raw_cross(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():raise ValueError("64 finite query coordinates required")
        result=z@self.z.T
        for t,g in enumerate(self.groups):
            a,b=z[:,g],self.z[:,g];dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            bw=self.group_bandwidths[t];result+=len(g)*np.exp(-dist/(2*len(g)*bw*bw))
        return result
    def arrays(self,coefficients):
        return dict(super().arrays(coefficients),
          kernel_group_distance_interpolated_medians=self.group_medians,
          kernel_raw_group_bandwidth_multipliers=self.raw_group_bandwidths,
          kernel_mean_loo_log_bandwidth=self.mean_loo_log_bandwidth,
          kernel_bias_corrected_log_bandwidth=self.bias_corrected_log_bandwidth,
          kernel_group_bandwidth_multipliers=self.group_bandwidths,
          kernel_fitting_patient_ids=self.fitting_patient_ids)

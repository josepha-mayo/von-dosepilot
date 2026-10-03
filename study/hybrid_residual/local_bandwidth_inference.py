"""Identity-checked inference for the response-free local-bandwidth model."""
from __future__ import annotations
import numpy as np
from additive_inference import AdditiveModel
from local_bandwidth_additive import GLOBAL_BANDWIDTH

class LocalBandwidthAdditiveModel(AdditiveModel):
    MODEL_KIND="dosepilot.additive_kernel_local_bandwidth.v1"

    def _check_kernel_metadata(self):
        super()._check_kernel_metadata()
        global_value=self.a.get("kernel_bandwidth_multiplier")
        local=self.a.get("local_bandwidth_multipliers")
        if global_value is None or global_value.shape!=() or not np.isfinite(global_value):
            raise ValueError("Missing global bandwidth metadata")
        if abs(float(global_value)-GLOBAL_BANDWIDTH)>1e-15:
            raise ValueError("Unexpected global bandwidth anchor")
        if local is None or local.shape!=(24,) or not np.isfinite(local).all() or (local<=0).any():
            raise ValueError("Missing or invalid local bandwidth metadata")
        if abs(float(np.exp(np.mean(np.log(local))))-GLOBAL_BANDWIDTH)>1e-12:
            raise ValueError("Local bandwidth geometric mean changed")
        self.local_bandwidths=np.asarray(local,float).copy()

    def _kernel(self,z,training):
        z,training=np.asarray(z,float),np.asarray(training,float)
        if (z.ndim!=2 or training.ndim!=2 or z.shape[1]!=64 or training.shape[1]!=64
                or not np.isfinite(z).all() or not np.isfinite(training).all()):
            raise ValueError("64 finite query inputs required")
        result=z@training.T
        for j,ell in enumerate(self.local_bandwidths):
            group=np.flatnonzero(self.owner==j)
            a,b=z[:,group],training[:,group]
            distance=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(group)*np.exp(-distance/(2*len(group)*ell*ell))
        return result

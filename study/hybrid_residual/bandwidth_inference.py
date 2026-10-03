[Reading 28 lines from start (total: 28 lines, 0 remaining)]

"""Identity-checked inference for the verified 0.7x additive bandwidth model."""
from __future__ import annotations
import numpy as np
from additive_inference import AdditiveModel

class BandwidthAdditiveModel(AdditiveModel):
    MODEL_KIND='dosepilot.additive_kernel_bandwidth.v1'
    EXPECTED_MULTIPLIER=.7
    def _check_kernel_metadata(self):
        super()._check_kernel_metadata()
        value=self.a.get('kernel_bandwidth_multiplier')
        if value is None or value.shape!=() or not np.isfinite(value):
            raise ValueError('Missing additive-kernel bandwidth metadata')
        if abs(float(value)-self.EXPECTED_MULTIPLIER)>1e-15:
            raise ValueError('Unexpected additive-kernel bandwidth multiplier')
        self.bandwidth=float(value)
    def _kernel(self,z,training):
        z,training=np.asarray(z,float),np.asarray(training,float)
        if z.ndim!=2 or training.ndim!=2 or z.shape[1]!=64 or training.shape[1]!=64 or not np.isfinite(z).all() or not np.isfinite(training).all():
            raise ValueError('64 finite query inputs required')
        result=z@training.T
        scale=self.bandwidth*self.bandwidth
        for j in range(24):
            g=np.flatnonzero(self.owner==j)
            a,b=z[:,g],training[:,g]
            distance=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(g)*np.exp(-distance/(2*len(g)*scale))
        return result

[executed on device: joseph-hp-elitebook (952b4ec0-09f4-4bcf-9153-2dd8c5e6a1d5)]
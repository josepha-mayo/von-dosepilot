"""Identity-checked backend for the fixed additive drug-dose kernel."""
import numpy as np
from hybrid_inference import HybridModel

class AdditiveModel(HybridModel):
    MODEL_KIND='dosepilot.additive_kernel.v1'
    def _check_kernel_metadata(self):
        owner=self.a.get('kernel_owner')
        if owner is None or owner.dtype.kind not in 'iu' or not np.array_equal(owner,self.owner):raise ValueError('Kernel dose groups disagree with the committed acquisition')
    def _kernel(self,z,training):
        z,training=np.asarray(z,float),np.asarray(training,float)
        if z.ndim!=2 or training.ndim!=2 or z.shape[1]!=64 or training.shape[1]!=64 or not np.isfinite(z).all() or not np.isfinite(training).all():raise ValueError('64 finite query inputs required')
        result=z@training.T
        for j in range(24):
            g=np.flatnonzero(self.owner==j);a,b=z[:,g],training[:,g]
            distance=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            result+=len(g)*np.exp(-distance/(2*len(g)))
        return result

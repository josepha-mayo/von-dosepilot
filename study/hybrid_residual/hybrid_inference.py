"""Strict all-input inference for the fixed hybrid-kernel research model.

Model files contain fitted training feature vectors and must remain private.
This subclass reuses the original native/dose/plate/sample/run checks; it does
not turn caller-declared values into verified physical measurements.
"""
from __future__ import annotations
from pathlib import Path
import json,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spectral_residual'))
from inference import SpectralModel,digest
from kernel_spectral import kernel

class HybridModel(SpectralModel):
    def __init__(self,arrays,plan):
        if 'correction' in arrays:raise ValueError('Hybrid storage must not impersonate a linear-correction model')
        super().__init__(dict(arrays,correction=np.zeros((64,24))),plan)
        z=self.a.get('z_training');w=self.a.get('weights');dual=self.a.get('dual_coefficients')
        if z is None or z.ndim!=2 or z.shape[1]!=64 or not 1<=len(z)<=238 or not np.isfinite(z).all():raise ValueError('Invalid private kernel reference features')
        if w is None or w.shape!=(len(z),) or not np.isfinite(w).all() or (w<=0).any() or abs(float(w.sum())-1)>1e-12:raise ValueError('Invalid kernel centering weights')
        if dual is None or dual.shape!=(len(z),24) or not np.isfinite(dual).all():raise ValueError('Invalid kernel coefficients')
        if 'nonlinear' not in self.a or self.a['nonlinear'].shape!=() or self.a['nonlinear'].dtype.kind!='b' or not bool(self.a['nonlinear']):raise ValueError('The declared hybrid kernel must include its fixed nonlinear term')
        mean=self.a.get('train_kernel_mean');grand=self.a.get('kernel_grand')
        if mean is None or mean.shape!=(len(z),) or not np.isfinite(mean).all() or grand is None or grand.shape!=() or not np.isfinite(grand):raise ValueError('Invalid centering statistics')
        recomputed=w@kernel(z,z,True)
        if not np.allclose(recomputed,mean,atol=1e-11,rtol=0) or abs(float(recomputed@w)-float(grand))>1e-11:raise ValueError('Kernel centering statistics do not match the model')

    @classmethod
    def load(cls,directory):
        directory=Path(directory)
        receipt=json.loads((directory/'CONSTRUCTION.json').read_text())
        if receipt.get('model_kind')!='dosepilot.hybrid_kernel.v1':raise ValueError('Wrong model family; use its matching inference backend')
        for name,key in [('plan.json','plan_sha256'),('model_private.npz','model_sha256')]:
            if digest(directory/name)!=receipt[key]:raise ValueError('Constructed artifact digest mismatch: '+name)
        with np.load(directory/'model_private.npz',allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
        return cls(arrays,json.loads((directory/'plan.json').read_text()))

    def predict(self,request):
        original=super().predict(request)
        supplied={r['native_id']:r['value'] for r in request['measurements']}
        paid=np.array([supplied[n] for n in self.native],float)[None,:]
        z=(paid-self.a['mean_x'])/self.a['scale_x']
        raw=kernel(z,self.a['z_training'],True)
        centered=raw-(raw@self.a['weights'])[:,None]-self.a['train_kernel_mean'][None,:]+self.a['kernel_grand']
        correction=(centered@self.a['dual_coefficients'])[0]
        prediction=np.array([original['predictions'][n] for n in self.targets])+correction
        if not np.isfinite(prediction).all():raise ValueError('Nonfinite output; all predictions withheld')
        return dict(original,predictions=dict(zip(self.targets,map(float,prediction))),model_kind='dosepilot.hybrid_kernel.v1',requires_all64_values=True)

"""Compiled additive inference with original identity and all-input checks.

An exact algebraic cache changes operation ordering, not the fitted model.
Use the accompanying new workflow and an explicit fresh runtime commitment.
"""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hybrid_residual'))
from additive_inference import AdditiveModel
from hybrid_inference import SpectralModel
from compiled_kernel import CompiledCorrection


class CompiledAdditiveModel(AdditiveModel):
    IMPLEMENTATION='dosepilot.compiled_additive.v1'
    def __init__(self,arrays,plan):
        super().__init__(arrays,plan)
        self.compiled=CompiledCorrection(self.a,self.owner)
    def predict(self,request):
        # SpectralModel sees a zero correction supplied by the validated
        # additive superclass. All original 64-record identity checks run.
        original=SpectralModel.predict(self,request)
        supplied={r['native_id']:r['value'] for r in request['measurements']}
        paid=np.array([supplied[n] for n in self.native],float)[None,:]
        z=(paid-self.a['mean_x'])/self.a['scale_x']
        correction=self.compiled.predict(z)[0]
        prediction=np.array([original['predictions'][t] for t in self.targets])+correction
        if not np.isfinite(prediction).all():raise ValueError('Nonfinite output; all predictions withheld')
        return dict(original,predictions=dict(zip(self.targets,map(float,prediction))),
                    model_kind=self.MODEL_KIND,requires_all64_values=True,
                    implementation=self.IMPLEMENTATION)

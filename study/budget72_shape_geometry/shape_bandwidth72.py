from __future__ import annotations
from pathlib import Path
import sys
import numpy as np

PARENT=Path(__file__).resolve().parents[1]/"budget72_bandwidth07_residual"
sys.path.insert(0,str(PARENT))
from bandwidth_additive72 import BandwidthAdditive72

_SHAPE_T=np.array([
    [1.0,1.0,1.0],
    [-1.0,0.0,1.0],
    [1.0,-2.0,1.0],
],dtype=float)
_SHAPE_T[0]/=np.sqrt(3.0)
_SHAPE_T[1]/=np.sqrt(2.0)
_SHAPE_T[2]/=np.sqrt(6.0)

class ShapeBandwidth72(BandwidthAdditive72):
    def __init__(self,z,residual,weights,owner,concentrations,shape_weights,multiplier=0.7):
        self.concentrations=np.asarray(concentrations,float).copy()
        if self.concentrations.shape!=(72,) or not np.isfinite(self.concentrations).all():
            raise ValueError("72 finite selected concentrations required")
        sw=np.asarray(shape_weights,float)
        if sw.shape!=(3,) or not np.isfinite(sw).all() or (sw<=0).any():
            raise ValueError("three positive shape weights required")
        self.shape_weights=sw/sw.mean()
        super().__init__(z,residual,weights,owner,multiplier)

    def raw_cross(self,q):
        q=np.asarray(q,float)
        if q.ndim!=2 or q.shape[1]!=72 or not np.isfinite(q).all():
            raise ValueError("72 finite query coordinates required")
        result=q@self.z.T
        scale=self.multiplier*self.multiplier
        for target in range(24):
            group=np.flatnonzero(self.owner==target)
            if len(group)!=3:
                raise ValueError("three-dose target group required")
            order=group[np.argsort(self.concentrations[group],kind="stable")]
            a=q[:,order]@_SHAPE_T.T
            b=self.z[:,order]@_SHAPE_T.T
            delta=a[:,None,:]-b[None,:,:]
            dist=np.sum(delta*delta*self.shape_weights[None,None,:],axis=2)
            result+=3.0*np.exp(-dist/(6.0*scale))
        return result

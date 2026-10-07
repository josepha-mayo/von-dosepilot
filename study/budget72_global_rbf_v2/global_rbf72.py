from __future__ import annotations
from pathlib import Path
import sys
import numpy as np

PARENT=Path(__file__).resolve().parents[1]/"budget72_bandwidth07_residual"
sys.path.insert(0,str(PARENT))
from bandwidth_additive72 import BandwidthAdditive72

class GlobalRBF72(BandwidthAdditive72):
    def __init__(self,z,residual,weights,owner,global_strength,multiplier=0.7):
        self.global_strength=float(global_strength)
        if self.global_strength not in (0.0,0.0625,0.125,0.25,0.5):
            raise ValueError("unregistered global RBF strength")
        super().__init__(z,residual,weights,owner,multiplier)

    def raw_cross(self,q):
        q=np.asarray(q,float)
        base=BandwidthAdditive72.raw_cross(self,q)
        if self.global_strength==0.0:
            return base
        linear=q@self.z.T
        dist=np.maximum(
            (q*q).sum(1)[:,None]+(self.z*self.z).sum(1)[None,:]-2*linear,
            0.0,
        )
        global_rbf=72.0*np.exp(-dist/(2.0*72.0))
        return base+self.global_strength*global_rbf

from __future__ import annotations
from pathlib import Path
import sys
import numpy as np

PARENT=Path(__file__).resolve().parents[1]/"budget72_bandwidth07_residual"
sys.path.insert(0,str(PARENT))
from bandwidth_additive72 import BandwidthAdditive72

class GlobalQuadratic72(BandwidthAdditive72):
    def __init__(self,z,residual,weights,owner,quadratic_strength,multiplier=0.7):
        self.quadratic_strength=float(quadratic_strength)
        if self.quadratic_strength not in (0.0,0.0625,0.125,0.25,0.5,1.0):
            raise ValueError("unregistered quadratic strength")
        super().__init__(z,residual,weights,owner,multiplier)

    def raw_cross(self,q):
        q=np.asarray(q,float)
        base=BandwidthAdditive72.raw_cross(self,q)
        if self.quadratic_strength==0.0:
            return base
        linear=q@self.z.T
        quadratic=(linear*linear)/72.0
        return base+self.quadratic_strength*quadratic

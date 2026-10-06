from __future__ import annotations
from pathlib import Path
import sys
import numpy as np

PARENT=Path(__file__).resolve().parents[1]/"budget72_bandwidth07_residual"
sys.path.insert(0,str(PARENT))
from bandwidth_additive72 import BandwidthAdditive72

class PairAugmented72(BandwidthAdditive72):
    def __init__(self,z,residual,weights,owner,pair_strength,multiplier=0.7):
        self.pair_strength=float(pair_strength)
        if self.pair_strength not in (0.0,0.1,0.25,0.5):
            raise ValueError("unregistered pair strength")
        self.group_means=None
        self.group_grands=None
        self.pair_scale=None
        super().__init__(z,residual,weights,owner,multiplier)

    def gaussian_groups(self,q):
        q=np.asarray(q,float)
        scale=self.multiplier*self.multiplier
        out=[]
        for group in self.groups:
            a,b=q[:,group],self.z[:,group]
            dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.0)
            out.append(np.exp(-dist/(2*len(group)*scale)))
        return out

    def pair_components(self,q):
        raw=self.gaussian_groups(q)
        if self.group_means is None:
            if not np.array_equal(q,self.z):
                raise ValueError("training pair centering must precede query")
            self.group_means=[self.w@k for k in raw]
            self.group_grands=[float(m@self.w) for m in self.group_means]
        total=np.zeros((len(q),len(self.z)))
        squared=np.zeros_like(total)
        for group,k,m,g in zip(self.groups,raw,self.group_means,self.group_grands):
            centered=k-(k@self.w)[:,None]-m[None,:]+g
            comp=len(group)*centered
            total+=comp
            squared+=comp*comp
        pairs=(total*total-squared)/2.0
        return total,pairs

    def raw_cross(self,q):
        q=np.asarray(q,float)
        base=BandwidthAdditive72.raw_cross(self,q)
        if self.pair_strength==0.0:
            return base
        main,pairs=self.pair_components(q)
        if self.pair_scale is None:
            main_energy=float(self.w@np.diag(main))
            pair_energy=float(self.w@np.diag(pairs))
            if main_energy<-1e-10 or pair_energy<-1e-10:
                raise ValueError("negative pair-kernel energy")
            self.pair_scale=main_energy/pair_energy if pair_energy>1e-14 else 0.0
        if not np.isfinite(self.pair_scale) or self.pair_scale<0:
            raise ValueError("invalid pair scale")
        return base+self.pair_strength*self.pair_scale*pairs

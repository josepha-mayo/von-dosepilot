from __future__ import annotations
import numpy as np

class BandwidthAdditive72:
    def __init__(self,z,residual,weights,owner,multiplier=0.7):
        self.z=np.asarray(z,float).copy()
        self.residual=np.asarray(residual,float).copy()
        self.w=np.asarray(weights,float).copy()
        self.owner=np.asarray(owner,int).copy()
        self.multiplier=float(multiplier)
        if self.z.ndim!=2 or self.z.shape[1]!=72 or not np.isfinite(self.z).all():
            raise ValueError("72 finite fitting coordinates required")
        if self.owner.shape!=(72,) or set(self.owner)!=set(range(24)):
            raise ValueError("owner contract")
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if any(len(g)!=3 for g in self.groups):
            raise ValueError("all 24 target groups must contain three doses")
        if self.w.shape!=(len(self.z),) or abs(self.w.sum()-1)>1e-12 or (self.w<=0).any():
            raise ValueError("weights")
        if self.residual.shape!=(len(self.z),24) or not np.isfinite(self.residual).all():
            raise ValueError("residual")
        raw=self.raw_cross(self.z)
        self.train_mean=self.w@raw
        self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w)
        matrix=self.sw[:,None]*centered*self.sw[None,:]
        eig,vec=np.linalg.eigh((matrix+matrix.T)/2)
        if eig.min()<-1e-10:
            raise ValueError("kernel is not positive semidefinite")
        self.e=np.maximum(eig,0.0)
        self.u=vec
        self.ur=vec.T@(self.sw[:,None]*self.residual)

    def raw_cross(self,q):
        q=np.asarray(q,float)
        if q.ndim!=2 or q.shape[1]!=72 or not np.isfinite(q).all():
            raise ValueError("72 finite query coordinates required")
        result=q@self.z.T
        scale=self.multiplier*self.multiplier
        for group in self.groups:
            a,b=q[:,group],self.z[:,group]
            dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.0)
            result+=len(group)*np.exp(-dist/(2*len(group)*scale))
        return result

    def centered_cross(self,q):
        raw=self.raw_cross(q)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand

    def coefficients(self,penalty,fraction):
        if penalty<=0 or not np.isfinite(penalty) or not 0<=fraction<=1:
            raise ValueError("spectral option")
        matrix=self.ur.T@((self.e/(self.e+penalty))[:,None]*self.ur)
        eig,vec=np.linalg.eigh((matrix+matrix.T)/2)
        order=np.argsort(eig)[::-1]
        s=np.sqrt(np.maximum(eig[order],0.0))
        vec=vec[:,order]
        ratio=np.divide(np.maximum(s-fraction*s[0],0.0),s,out=np.zeros_like(s),where=s>1e-15)
        projector=(vec*ratio)@vec.T
        coef=self.sw[:,None]*(self.u@(self.ur/(self.e+penalty)[:,None]))@projector
        return coef,s,projector

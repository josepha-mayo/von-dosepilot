"""Exact algebraic compilation of an already fitted additive-kernel correction.

No approximation, model refitting, or precision reduction is performed. Floating
point operation ordering may differ slightly; original stored predictions are
never silently replaced by this implementation.
"""
from __future__ import annotations
import numpy as np


class CompiledCorrection:
    def __init__(self,arrays,owner):
        training=np.asarray(arrays['z_training'],float)
        weights=np.asarray(arrays['weights'],float)
        dual=np.asarray(arrays['dual_coefficients'],float)
        mean=np.asarray(arrays['train_kernel_mean'],float)
        grand=float(arrays['kernel_grand'])
        owner=np.asarray(owner)
        if (training.ndim!=2 or training.shape[1]!=64 or not 1<=len(training)<=238
            or weights.shape!=(len(training),) or dual.shape!=(len(training),24)
            or mean.shape!=(len(training),) or owner.shape!=(64,)
            or owner.dtype.kind not in 'iu' or set(owner)!=set(range(24))):
            raise ValueError('Malformed additive correction')
        if not all(np.isfinite(v).all() for v in (training,weights,dual,mean)) or not np.isfinite(grand):
            raise ValueError('Nonfinite fitted parameters')
        if (weights<=0).any() or abs(weights.sum()-1)>1e-12:
            raise ValueError('Invalid fitting weights')
        groups=[np.flatnonzero(owner==j) for j in range(24)]
        if sorted(map(len,groups))!=[2]*8+[3]*16:
            raise ValueError('Original 64-well drug grouping required')
        indices=np.full((24,3),64,dtype=int)
        for j,g in enumerate(groups):indices[j,:len(g)]=g
        widths=np.array(list(map(len,groups)),float)
        mass=dual.sum(0)
        effective=dual-weights[:,None]*mass[None,:]
        self.linear=training.T@effective
        self.offset=-mean@dual+grand*mass
        self.effective=effective.copy()
        self.indices=indices
        self.widths=widths
        self.training=np.pad(training,((0,0),(0,1)))[:,indices].transpose(1,0,2).copy()
        self.training_norm=(self.training*self.training).sum(2)
        for value in (self.linear,self.offset,self.effective,self.indices,self.widths,self.training,self.training_norm):
            value.setflags(write=False)

    def predict(self,z):
        z=np.asarray(z,float)
        if z.ndim!=2 or z.shape[1]!=64 or not np.isfinite(z).all():
            raise ValueError('Exactly 64 finite purchased values required')
        query=np.pad(z,((0,0),(0,1)))[:,self.indices]
        dot=np.einsum('bgi,gni->bgn',query,self.training,optimize=False)
        dist=np.maximum((query*query).sum(2)[:,:,None]+self.training_norm[None,:,:]-2*dot,0.)
        nonlinear=np.sum(self.widths[None,:,None]*np.exp(-dist/(2*self.widths[None,:,None])),axis=1)
        result=z@self.linear+nonlinear@self.effective+self.offset
        if not np.isfinite(result).all():raise ValueError('Nonfinite correction')
        return result

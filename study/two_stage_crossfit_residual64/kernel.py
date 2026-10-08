"""Task-aligned residual geometry on values, dose metadata and missingness flags.
Features are derived from 64 purchased values, not 264 additional measurements.
"""
from __future__ import annotations
import numpy as np
BLOCK=11
DIMENSION=24*BLOCK
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]


def encode(bank,first,actions,later,seed,base,query_positions):
    x=np.asarray(first,float);a=np.asarray(actions,int);z=np.asarray(later,float);bp=np.asarray(base,float)
    if x.shape!=(len(a),24,2) or a.shape!=(len(x),24) or z.shape!=a.shape or bp.shape!=a.shape:
        raise ValueError('aligned 24-target staged observations required')
    if not np.isfinite(x).all() or not np.isfinite(z[a>0]).all() or not np.isfinite(bp).all():raise ValueError('missing purchased values')
    output=np.zeros((len(x),24,BLOCK))
    for j in range(24):
        start=bank[f't{j}_initial_native'];pre=f't{j}_s{seed}_';mask=a[:,j]>0
        output[:,j,0]=x[:,j,0];output[:,j,1]=query_positions[start[0]];output[:,j,2]=seed
        output[:,j,3]=x[:,j,1];output[:,j,4]=query_positions[start[1]];output[:,j,5]=1-seed
        rows=np.flatnonzero(mask);options=a[rows,j]
        output[rows,j,6]=z[rows,j]
        output[rows,j,7]=query_positions[bank[pre+'option_native'][options]]
        output[rows,j,8]=bank[pre+'option_plate'][options]
        output[:,j,9]=mask.astype(float);output[:,j,10]=bp[:,j]
    if not np.isfinite(output).all():raise ValueError('nonfinite encoded features')
    return output.reshape(len(x),DIMENSION)


class Kernel:
    def __init__(self,features,residual,weights):
        f=np.asarray(features,float);r=np.asarray(residual,float);w=np.asarray(weights,float)
        if f.ndim!=2 or f.shape[1]!=DIMENSION or r.shape!=(len(f),24) or w.shape!=(len(f),):raise ValueError('fitting matrix dimensions')
        if not all(np.isfinite(v).all() for v in (f,r,w)) or w.min()<=0 or abs(w.sum()-1)>1e-12:raise ValueError('fitting matrix validity')
        self.mean=w@f;self.scale=np.maximum(np.sqrt(w@((f-self.mean)**2)),.05)
        self.z=(f-self.mean)/self.scale;self.w=w.copy();self.residual_mean=w@r
        centered_y=r-self.residual_mean
        raw=self.raw_cross(self.z);self.train_mean=w@raw;self.grand=float(self.train_mean@w)
        centered=raw-(raw@w)[:,None]-self.train_mean[None,:]+self.grand
        sw=np.sqrt(w);matrix=sw[:,None]*centered*sw[None,:]
        e,u=np.linalg.eigh((matrix+matrix.T)/2)
        if e.min()<-1e-10:raise ValueError('non-PSD task kernel')
        e=np.maximum(e,0);ur=u.T@(sw[:,None]*centered_y)
        self.coefficients=[np.zeros_like(r)]
        for fraction,penalty in OPTIONS[1:]:
            gram=ur.T@((e/(e+penalty))[:,None]*ur);values,vec=np.linalg.eigh((gram+gram.T)/2)
            order=np.argsort(values)[::-1];s=np.sqrt(np.maximum(values[order],0));vec=vec[:,order]
            shrink=np.divide(np.maximum(s-fraction*s[0],0),s,out=np.zeros_like(s),where=s>1e-15)
            projector=(vec*shrink)@vec.T
            self.coefficients.append(sw[:,None]*(u@(ur/(e+penalty)[:,None]))@projector)
    def raw_cross(self,zq):
        zq=np.asarray(zq,float)
        if zq.ndim!=2 or zq.shape[1]!=DIMENSION or not np.isfinite(zq).all():raise ValueError('finite task-aligned queries required')
        raw=zq@self.z.T
        for j in range(24):
            q=zq[:,j*BLOCK:(j+1)*BLOCK];t=self.z[:,j*BLOCK:(j+1)*BLOCK]
            d=np.maximum(np.sum(q*q,1)[:,None]+np.sum(t*t,1)[None,:]-2*q@t.T,0.)
            raw+=BLOCK*np.exp(-d/(2*BLOCK*.7**2))
        return raw
    def predict_all(self,features,base):
        f=np.asarray(features,float);bp=np.asarray(base,float)
        raw=self.raw_cross((f-self.mean)/self.scale)
        cross=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        out=np.empty((10,len(f),24));out[0]=bp
        for i,c in enumerate(self.coefficients[1:],1):out[i]=bp+self.residual_mean+cross@c
        return out
    def arrays(self,selected):
        return {'feature_mean':self.mean,'feature_scale':self.scale,'training_z':self.z,'training_weights':self.w,
          'kernel_train_mean':self.train_mean,'kernel_grand':np.asarray(self.grand),'residual_mean':self.residual_mean,
          'coefficient':self.coefficients[selected],'selected_index':np.asarray(selected),'block_size':np.asarray(BLOCK)}


def predict_saved(state,features,base):
    bp=np.asarray(base,float);f=np.asarray(features,float)
    if bp.shape!=(len(f),24) or f.shape[1:]!=(DIMENSION,) or not np.isfinite(f).all() or not np.isfinite(bp).all():raise ValueError('invalid saved-model query')
    if int(state['selected_index'])==0:return bp.copy()
    z=(f-state['feature_mean'])/state['feature_scale'];zt=state['training_z'];raw=z@zt.T
    for j in range(24):
        a=z[:,j*BLOCK:(j+1)*BLOCK];b=zt[:,j*BLOCK:(j+1)*BLOCK]
        d=np.maximum(np.sum(a*a,1)[:,None]+np.sum(b*b,1)[None,:]-2*a@b.T,0.)
        raw+=BLOCK*np.exp(-d/(2*BLOCK*.7**2))
    cross=raw-(raw@state['training_weights'])[:,None]-state['kernel_train_mean'][None,:]+state['kernel_grand']
    return bp+state['residual_mean']+cross@state['coefficient']

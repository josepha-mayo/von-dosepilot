"""Query-specific patient-weighted local linear heads, with exact physical costs.
Only purchased values are passed to inference. Research code, not clinical use.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import accuracy_tiers as tiers
# An isolated experiment-specific whitelist. The original worktree is untouched.
BUDGETS=(64,120,124,128)
tiers.BUDGETS=BUDGETS
core=tiers.core
OPTIONS=tiers.OPTIONS
CONFIGS=(('original',0.,0.),('own',.7,.5),('own',.7,1.),('own',1.4,1.),('response',.7,.5),('response',.7,1.),('response',1.4,1.))
NAMES=('original','own07_half','own07_full','own14_full','response07_half','response07_full','response14_full')


def local_delta(state,paid,config):
    """Return changes to the own-target heads; retain the original global residual.
    Query-specific observation weights are a mixture of the whole-patient prior
    and a Gaussian neighborhood defined by available response features only.
    """
    pp=np.asarray(paid,float);budget=int(state['budget'])
    if pp.ndim!=2 or pp.shape[1]!=budget or not np.isfinite(pp).all():raise ValueError('exactly the declared number of finite purchased values is required')
    kind,h,rho=config
    if kind=='original':return np.zeros((len(pp),24))
    if kind not in ('own','response') or h<=0 or not 0<=rho<=1:raise ValueError('invalid local head configuration')
    z=(pp-state['mean_x'])/state['scale_x'];train=state['kernel_z'];w=state['kernel_weights'];y=state['train_y']
    bp=state['mean_y']+z@state['beta'];out=np.empty_like(bp)
    if kind=='response':
        q=(bp-state['response_mean'])/state['response_scale']
        t=state['response_training']
        dist=np.maximum(np.sum(q*q,1)[:,None]+np.sum(t*t,1)[None,:]-2*q@t.T,0)/24
        logk=-dist/(2*h*h);logk-=np.max(logk,axis=1,keepdims=True)
        kw=np.exp(logk)*w[None,:];kw/=kw.sum(1,keepdims=True)
        response_weights=(1-rho)*w[None,:]+rho*kw
    for j in range(24):
        cols=np.flatnonzero(state['kernel_owner']==j);t=train[:,cols];q=z[:,cols]
        if kind=='own':
            dist=np.maximum(np.sum(q*q,1)[:,None]+np.sum(t*t,1)[None,:]-2*q@t.T,0)/len(cols)
            logk=-dist/(2*h*h);logk-=np.max(logk,axis=1,keepdims=True)
            kw=np.exp(logk)*w[None,:];kw/=kw.sum(1,keepdims=True)
            weights=(1-rho)*w[None,:]+rho*kw
        else:weights=response_weights
        mx=weights@t;my=weights@y[:,j]
        gram=np.einsum('mn,ni,nj->mij',weights,t,t,optimize=True)-mx[:,:,None]*mx[:,None,:]
        gram=(gram+gram.transpose(0,2,1))/2+.01*np.eye(len(cols))[None,:,:]
        cross=np.einsum('mn,ni,n->mi',weights,t,y[:,j],optimize=True)-mx*my[:,None]
        beta=np.linalg.solve(gram,cross[...,None])[...,0]
        out[:,j]=my+np.sum((q-mx)*beta,axis=1)
    if not np.isfinite(out).all():raise ValueError('nonfinite local reconstruction')
    return out-bp


def augment_model(model,y,p):
    s=tiers.payload(model,0);s['all_coefs']=np.stack(model[3]);s['train_y']=np.r_[y,y]
    s['training_patients']=np.r_[p,p].astype(str)
    tb=s['mean_y']+s['kernel_z']@s['beta'];w=s['kernel_weights']
    mu=w@tb;scale=np.maximum(np.sqrt(w@((tb-mu)**2)),.05)
    s['response_mean']=mu;s['response_scale']=scale;s['response_training']=(tb-mu)/scale
    return s


def fit(x,y,p,catalog):
    models=tiers.fit_models(x,y,p,catalog)
    return {b:{'model':models[b],'state':augment_model(models[b],y,p)} for b in BUDGETS}


def predict_all(query,fit):
    model,s=fit['model'],fit['state'];plan=model[0]
    baseline=tiers.predict_options(query,model)
    out=np.empty((70,2,len(query),24))
    for i,config in enumerate(CONFIGS):
        for oi,o in enumerate(('A','B')):
            delta=local_delta(s,tiers.paid(query,plan,o),config)
            out[10*i:10*(i+1),oi]=baseline[:,oi]+delta[None,:,:]
    if not np.isfinite(out).all():raise ValueError('incomplete predictions')
    return out


def replay(state,paid,index):
    local,spectral=divmod(int(index),10)
    if not 0<=local<len(CONFIGS):raise ValueError('option outside frozen family')
    base_state=dict(state);base_state['coef']=state['all_coefs'][spectral]
    return tiers.replay(base_state,paid)+local_delta(state,paid,CONFIGS[local])

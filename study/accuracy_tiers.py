"""Explicitly costed DosePilot accuracy tiers. Higher tiers purchase more wells.
They are NOT same-budget successors to the retained 64-well procedure.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from itertools import combinations
from decimal import Decimal
from copy import deepcopy
import numpy as np
import run_crossplate64_20261008 as core
from coverage_methods import validate_catalog
from sparse_methods import fit_sparse_context
from kernel_spectral import KernelSpectral
BUDGETS=(64,80,96,112,128)
OPTIONS=core.OPTIONS

def patient_weights(p):
    return core.patient_weights(p)/len(np.unique(p))

def choices_for_sizes(x,y,p,catalog):
    validate_catalog(catalog);x=np.asarray(x,float);y=np.asarray(y,float);p=np.asarray(p,str)
    if x.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(p),24) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('fitting population')
    w=np.tile(patient_weights(p),2)/2;allchoices=[]
    for j in range(24):
        native=sorted(map(int,np.flatnonzero(catalog.native_target_indices==j)),key=lambda q:(Decimal(catalog.concentrations[q]),str(catalog.native_ids[q])))
        values=x[:,native,:];xx=np.r_[values.reshape(len(values),-1),values[:,:,::-1].reshape(len(values),-1)]
        yy=np.tile(y[:,j],2);mx=w@xx;my=w@yy;sx=np.maximum(np.sqrt(w@((xx-mx)**2)),.05)
        z=(xx-mx)/sx;center=yy-my;G=(z.T*w)@z;xy=(z.T*w)@center;variance=float(w@(center*center));choices={}
        for size in range(2,min(6,len(native))+1):
            subsets=list(combinations(range(len(native)),size))
            cols=np.asarray([[2*q+i%2 for i,q in enumerate(s)] for s in subsets],int)
            mat=G[cols[:,:,None],cols[:,None,:]]+.1*np.eye(size)[None,:,:]
            cross=xy[cols];coefs=np.linalg.solve(mat,cross[...,None])[...,0]
            scores=variance-np.sum(cross*coefs,axis=1)
            ix=min(range(len(subsets)),key=lambda i:(float(scores[i]),tuple(str(catalog.native_ids[native[q]]) for q in subsets[i])))
            choices[size]={'risk':float(scores[ix]),'subset':[native[q] for q in subsets[ix]],'candidate_count':len(subsets)}
        allchoices.append(choices)
    return allchoices

def optimal_sizes(costs,budget):
    """Exact finite knapsack for the provided risk surrogates, not true test risk."""
    dp={0:(0.0,())}
    for options in costs:
        nxt={}
        for total,(risk,path) in dp.items():
            for k,value in sorted(options.items()):
                newtotal=total+k
                if newtotal>budget:continue
                proposal=(risk+float(value),path+(k,))
                if newtotal not in nxt or proposal<nxt[newtotal]:nxt[newtotal]=proposal
        dp=nxt
    if budget not in dp:raise ValueError('infeasible physical budget')
    return dp[budget]

def validate(plan,catalog):
    budget=int(plan['treatment_wells']);n=np.asarray(plan['selected_native_indices'],int);own=np.asarray(plan['coordinate_target_indices'],int)
    a=np.asarray(plan['orientation_A_plate_indices'],int);b=np.asarray(plan['orientation_B_plate_indices'],int)
    if budget not in BUDGETS or n.shape!=(budget,) or len(set(n.tolist()))!=budget or np.any(n<0) or np.any(n>=len(catalog.native_ids)):raise ValueError('physical/native budget')
    if own.shape!=(budget,) or not np.array_equal(own,catalog.native_target_indices[n]):raise ValueError('native ownership')
    counts=np.bincount(own,minlength=24)
    if len(counts)!=24 or counts.min()<2 or counts.max()>6:raise ValueError('target coverage')
    if not np.array_equal(b,1-a) or np.count_nonzero(a==0)!=budget//2 or np.count_nonzero(a==1)!=budget//2:raise ValueError('balanced alternative plates')
    if len(set(zip(n,a)))!=budget or len(set(zip(n,b)))!=budget:raise ValueError('duplicate physical measurements')
    if plan['selected_native_ids']!=list(map(str,catalog.native_ids[n])):raise ValueError('native identities')
    return True

def build_plans(x,y,p,catalog):
    original=core.plan_panel_fast(x,y,p,catalog);original=deepcopy(original);original['treatment_wells']=64
    plans={64:original};choices=choices_for_sizes(x,y,p,catalog)
    for budget in BUDGETS[1:]:
        risk,sizes=optimal_sizes([{k:v['risk'] for k,v in c.items()} for c in choices],budget)
        odd=sorted([j for j,k in enumerate(sizes) if k%2],key=lambda j:str(catalog.target_ids[j]))
        starts={j:i%2 for i,j in enumerate(odd)};selected=[];owners=[];plates=[]
        if len(odd)%2:raise ValueError('even budget requires an even number of odd groups')
        for j,k in enumerate(sizes):
            selected+=choices[j][k]['subset'];owners+=[j]*k;plates+=[(starts.get(j,0)+i)%2 for i in range(k)]
        plans[budget]={'selected_native_indices':selected,'selected_native_ids':[str(catalog.native_ids[q]) for q in selected],'selected_concentrations_nM':[str(catalog.concentrations[q]) for q in selected],'coordinate_target_indices':owners,'orientation_A_plate_indices':plates,'orientation_B_plate_indices':[1-v for v in plates],'treatment_wells':budget,'per_plate':[budget//2,budget//2],'cardinalities':list(sizes),'proxy_risk_sum':risk,'acquisition':'fitting-only per-drug subset search plus exact cardinality knapsack','cost_tier_not_same_budget':True}
    for plan in plans.values():validate(plan,catalog)
    return plans

def paid(x,plan,o):
    if o not in ('A','B'):raise ValueError('unknown layout')
    a=np.asarray(x,float)[:,plan['selected_native_indices'],plan[f'orientation_{o}_plate_indices']]
    if a.shape!=(len(x),plan['treatment_wells']) or not np.isfinite(a).all():raise ValueError('complete paid panel required')
    return a

class Ridge:
    def __init__(self,ctx,plan):
        self.mean_x=ctx.mean_x.copy();self.scale_x=ctx.scale_x.copy();self.mean_y=ctx.mean_y.copy()
        own=np.asarray(plan['coordinate_target_indices']);self.beta=np.zeros((len(own),24))
        for j in range(24):
            cols=np.flatnonzero(own==j)
            self.beta[cols,j]=np.linalg.solve(ctx.cxx[np.ix_(cols,cols)]+.01*np.eye(len(cols)),ctx.cxy[cols,j])
    def predict(self,x):return self.mean_y+((x-self.mean_x)/self.scale_x)@self.beta

class Additive(KernelSpectral):
    def __init__(self,z,res,w,owner):
        self.z=np.asarray(z,float).copy();self.residual=np.asarray(res,float).copy();self.w=np.asarray(w,float).copy();self.owner=np.asarray(owner,int);self.nonlinear=True
        if self.z.ndim!=2 or self.z.shape[1] not in BUDGETS or self.owner.shape!=(self.z.shape[1],) or self.residual.shape!=(len(z),24):raise ValueError('tier kernel dimensions')
        if not np.isfinite(z).all() or not np.isfinite(res).all() or self.w.shape!=(len(z),) or abs(self.w.sum()-1)>1e-12 or (self.w<=0).any():raise ValueError('kernel training values')
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if min(map(len,self.groups))<2 or max(map(len,self.groups))>6:raise ValueError('2-6 physical inputs per target')
        raw=self.raw_cross(self.z);self.train_mean=self.w@raw;self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w);K=self.sw[:,None]*centered*self.sw[None,:]
        e,u=np.linalg.eigh((K+K.T)/2)
        if e.min()<-1e-10:raise ValueError('non-PSD kernel')
        self.e=np.maximum(e,0);self.u=u;self.ur=u.T@(self.sw[:,None]*self.residual)
    def raw_cross(self,q):
        q=np.asarray(q,float)
        if q.ndim!=2 or q.shape[1]!=self.z.shape[1] or not np.isfinite(q).all():raise ValueError('wrong paid feature count')
        result=q@self.z.T
        for cols in self.groups:
            a=q[:,cols];b=self.z[:,cols];d=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0)
            result+=len(cols)*np.exp(-d/(2*len(cols)*.49))
        return result
    def centered_cross(self,q):
        raw=self.raw_cross(q)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand

def fit_models(x,y,p,catalog):
    plans=build_plans(x,y,p,catalog);models={};w=np.tile(patient_weights(p),2)/2
    for budget,plan in plans.items():
        a,b=paid(x,plan,'A'),paid(x,plan,'B');xx=np.r_[a,b];yy=np.r_[y,y];pp=np.r_[p,p]
        ctx=fit_sparse_context(xx,yy,pp,plan['selected_native_ids'],catalog.target_ids);base=Ridge(ctx,plan)
        z=(xx-base.mean_x)/base.scale_x;res=yy-base.predict(xx)
        kernel=Additive(z,res,w,plan['coordinate_target_indices'])
        coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        models[budget]=(plan,base,kernel,coefs)
    return models

def predict_options(x,model):
    plan,base,kernel,coefs=model;out=np.empty((10,2,len(x),24))
    for oi,o in enumerate(('A','B')):
        pp=paid(x,plan,o);bp=base.predict(pp);K=kernel.centered_cross((pp-base.mean_x)/base.scale_x)
        for i,c in enumerate(coefs):out[i,oi]=bp+K@c
    if not np.isfinite(out).all():raise ValueError('nonfinite predictions')
    return out

def payload(model,option):
    plan,base,kernel,coefs=model
    return {'mean_x':base.mean_x,'scale_x':base.scale_x,'mean_y':base.mean_y,'beta':base.beta,'kernel_z':kernel.z,'kernel_owner':kernel.owner,'kernel_weights':kernel.w,'kernel_mean':kernel.train_mean,'kernel_grand':np.asarray(kernel.grand),'coef':coefs[option],'native':np.asarray(plan['selected_native_indices'],int),'plate_A':np.asarray(plan['orientation_A_plate_indices'],int),'plate_B':np.asarray(plan['orientation_B_plate_indices'],int),'budget':np.asarray(plan['treatment_wells'])}

def replay(s,p):
    p=np.asarray(p,float);B=int(s['budget'])
    if p.ndim!=2 or p.shape[1]!=B or not np.isfinite(p).all():raise ValueError('complete explicitly costed paid panel required')
    q=(p-s['mean_x'])/s['scale_x'];t=s['kernel_z'];raw=q@t.T
    for j in range(24):
        idx=np.flatnonzero(s['kernel_owner']==j);a=q[:,idx];b=t[:,idx];dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
        raw+=len(idx)*np.exp(-dist/(2*len(idx)*.49))
    K=raw-(raw@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+s['kernel_grand']
    return s['mean_y']+q@s['beta']+K@s['coef']

"""Fixed-total-well allocation with variable per-target cardinality.
No dataset or filesystem access. The DP is exact for the supplied risk table.
"""
from __future__ import annotations
from decimal import Decimal
from itertools import combinations
import numpy as np
from coverage_methods import validate_catalog, subset_orientations
from sparse_methods import fit_sparse_context
from kernel_spectral import KernelSpectral


def choose_sizes(risk_tables, budget):
    if not isinstance(budget,int) or budget<1 or not risk_tables:
        raise ValueError('positive integer budget and nonempty risk tables required')
    states={0:(0.0,())}
    for table in risk_tables:
        if not table or any(not isinstance(k,int) or k<1 or not np.isfinite(v) for k,v in table.items()):
            raise ValueError('finite risk for positive integer cardinalities required')
        nxt={}
        for spent,(risk,sizes) in states.items():
            for size in sorted(table):
                total=spent+size
                if total>budget:continue
                option=(risk+float(table[size]),sizes+(size,))
                if total not in nxt or option<nxt[total]:nxt[total]=option
        states=nxt
    if budget not in states:raise ValueError('infeasible fixed total budget')
    return states[budget][1],states[budget][0]


def fitting_subset_table(values,y,patients,catalog):
    validate_catalog(catalog)
    values,y=np.asarray(values,float),np.asarray(y,float);p=np.asarray(patients,str)
    if values.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(p),24):raise ValueError('fit shape')
    if not np.isfinite(values).all() or not np.isfinite(y).all() or not len(p):raise ValueError('finite fitting rows required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    w=np.tile(1./(2*len(ids)*count[inv]),2);pp=np.tile(p,2);tables=[]
    for j,target in enumerate(catalog.target_ids):
        native=sorted(map(int,np.flatnonzero(catalog.native_target_indices==j)),key=lambda q:(Decimal(catalog.concentrations[q]),str(catalog.native_ids[q])))
        v=values[:,native,:];full=np.r_[v.reshape(len(v),-1),v[:,:,::-1].reshape(len(v),-1)]
        yy=np.tile(y[:,j],2);mx=w@full;my=w@yy;sx=np.maximum(np.sqrt(w@((full-mx)**2)),.05)
        z=(full-mx)/sx;cy=yy-my;cxx=(z.T*w)@z;cxy=(z.T*w)@cy;cyy=float(w@(cy*cy));best={}
        for size in range(1,min(6,len(native))+1):
            local=np.asarray(list(combinations(range(len(native)),size)),dtype=int)
            cols=2*local+np.arange(size)[None,:]%2
            systems=cxx[cols[:,:,None],cols[:,None,:]]+.1*np.eye(size)[None,:,:]
            cross=cxy[cols];solved=np.linalg.solve(systems,cross[:,:,None])[:,:,0]
            risks=cyy-np.sum(cross*solved,axis=1)
            near=np.flatnonzero(risks<=float(risks.min())+1e-12)
            checked=[]
            for index in near:
                subset=tuple(native[k] for k in local[index]);names=tuple(str(catalog.native_ids[q]) for q in subset)
                a,b=subset_orientations(values,subset)
                ctx=fit_sparse_context(np.r_[a,b],np.tile(y[:,[j]],(2,1)),pp,names,[target])
                cc=ctx.cxy[:,0];risk=float(ctx.cyy[0,0]-cc@np.linalg.solve(ctx.cxx+.1*np.eye(size),cc))
                checked.append((risk,names,subset))
            risk,names,subset=min(checked)
            best[size]={'risk':risk,'subset':list(subset),'native_ids':list(names)}
        tables.append(best)
    return tables


def make_plan(tables,catalog,minimum):
    if minimum not in (1,2):raise ValueError('unregistered minimum cardinality')
    risks=[{int(k):v['risk'] for k,v in table.items() if k>=minimum} for table in tables]
    sizes,risk=choose_sizes(risks,64)
    odd=sorted((j for j,size in enumerate(sizes) if size%2),key=lambda j:str(catalog.target_ids[j]))
    if len(odd)%2:raise ValueError('odd-group parity')
    starts={j:k%2 for k,j in enumerate(odd)}
    selected=[];owner=[];plates=[]
    for j,size in enumerate(sizes):
        subset=tables[j][size]['subset'];selected.extend(subset);owner.extend([j]*size)
        plates.extend((starts.get(j,0)+k)%2 for k in range(size))
    plan={'selected_native_indices':selected,'selected_native_ids':[str(catalog.native_ids[q]) for q in selected],
          'coordinate_target_indices':owner,'orientation_A_plate_indices':plates,
          'orientation_B_plate_indices':[1-p for p in plates],'cardinalities':list(sizes),
          'allocation_policy':'flexible_min'+str(minimum),'allocation_alpha':.1,
          'fitting_risk_sum':float(risk),'treatment_wells':64,'per_plate':[32,32]}
    validate_plan(plan,catalog)
    return plan


def validate_plan(plan,catalog=None):
    native=np.asarray(plan['selected_native_indices'],int);owner=np.asarray(plan['coordinate_target_indices'],int)
    a=np.asarray(plan['orientation_A_plate_indices'],int);b=np.asarray(plan['orientation_B_plate_indices'],int)
    if native.shape!=(64,) or len(set(native.tolist()))!=64 or (native<0).any():raise ValueError('64 distinct native doses required')
    if owner.shape!=(64,) or not np.isin(owner,np.arange(24)).all():raise ValueError('owner shape')
    counts=np.bincount(owner,minlength=24)
    if (counts<1).any() or (counts>6).any():raise ValueError('one to six doses per target required')
    if a.shape!=(64,) or b.shape!=(64,) or not np.isin(a,(0,1)).all() or not np.array_equal(b,1-a) or int((a==0).sum())!=32:raise ValueError('physical plate balance')
    if catalog is not None:
        if native.max()>=len(catalog.native_ids) or not np.array_equal(owner,catalog.native_target_indices[native]):raise ValueError('catalog ownership')
        if plan['selected_native_ids']!=list(map(str,catalog.native_ids[native])):raise ValueError('catalog identity')


def acquire(values,plan,orientation):
    validate_plan(plan)
    if orientation not in ('A','B'):raise ValueError('orientation')
    x=np.asarray(values,float)
    if x.ndim!=3 or x.shape[2]!=2:raise ValueError('query shape')
    q=x[:,plan['selected_native_indices'],plan[f'orientation_{orientation}_plate_indices']].copy()
    if q.shape!=(len(x),64) or not np.isfinite(q).all():raise ValueError('64 finite purchased values required')
    return q


class OwnDrugBase:
    def __init__(self,a,b,y,patients,plan,target_ids):
        validate_plan(plan)
        ctx=fit_sparse_context(np.r_[a,b],np.r_[y,y],np.tile(patients,2),plan['selected_native_ids'],target_ids)
        self.mean_x,self.scale_x,self.mean_y=ctx.mean_x,ctx.scale_x,ctx.mean_y
        self.beta=np.zeros((64,24));owner=np.asarray(plan['coordinate_target_indices'])
        for j in range(24):
            cols=np.flatnonzero(owner==j)
            self.beta[cols,j]=np.linalg.solve(ctx.cxx[np.ix_(cols,cols)]+.01*np.eye(len(cols)),ctx.cxy[cols,j])
    def predict(self,paid):
        paid=np.asarray(paid,float)
        if paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('paid shape/values')
        return self.mean_y+((paid-self.mean_x)/self.scale_x)@self.beta


class FlexibleKernel(KernelSpectral):
    def __init__(self,z,residual,w,owner,multiplier=.7):
        self.z=np.asarray(z,float).copy();self.residual=np.asarray(residual,float).copy();self.w=np.asarray(w,float).copy();self.owner=np.asarray(owner,int).copy()
        self.multiplier=float(multiplier)
        if self.z.ndim!=2 or self.z.shape[1]!=64 or self.residual.shape!=(len(z),24) or self.owner.shape!=(64,):raise ValueError('kernel shape')
        if not all(np.isfinite(v).all() for v in (self.z,self.residual,self.w)) or self.w.shape!=(len(z),) or (self.w<=0).any() or abs(self.w.sum()-1)>1e-12:raise ValueError('kernel values/weights')
        if set(self.owner)!=set(range(24)):raise ValueError('kernel target ownership')
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if any(not 1<=len(g)<=6 for g in self.groups):raise ValueError('kernel group cardinality')
        raw=self.raw_cross(self.z);self.train_mean=self.w@raw;self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w);matrix=self.sw[:,None]*centered*self.sw[None,:]
        e,u=np.linalg.eigh((matrix+matrix.T)/2)
        if e.min() < -1e-9:raise ValueError('kernel PSD check')
        self.e=np.maximum(e,0.);self.u=u;self.ur=u.T@(self.sw[:,None]*self.residual)
    def raw_cross(self,q):
        q=np.asarray(q,float)
        if q.ndim!=2 or q.shape[1]!=64 or not np.isfinite(q).all():raise ValueError('kernel query')
        out=q@self.z.T
        for g in self.groups:
            a,b=q[:,g],self.z[:,g];d=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
            out+=len(g)*np.exp(-d/(2*len(g)*self.multiplier**2))
        return out
    def centered_cross(self,q):
        raw=self.raw_cross(q)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand

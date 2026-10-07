"""Nonlinear pooled curve residuals with realizable same-cardinality mask augmentation.
Every virtual context retains the original number of purchased treatment wells.
"""
from __future__ import annotations
from itertools import combinations
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

SEED=202610071719
PARAMETERS={'loss':'squared_error','learning_rate':.03,'max_iter':400,'max_leaf_nodes':7,
 'max_depth':3,'min_samples_leaf':64,'l2_regularization':10.,'max_bins':128,
 'categorical_features':None,'early_stopping':False,'random_state':SEED}

def weights(p):
    p=np.asarray(p,str);ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    if len(ids)<2:raise ValueError('at least two fitting patients required')
    return 1./(len(ids)*count[inv])

def local_ridge(a,b,y,p):
    a,b,y=np.asarray(a,float),np.asarray(b,float),np.asarray(y,float)
    if a.shape!=b.shape or a.ndim!=2 or y.shape!=(len(a),) or not np.isfinite(np.r_[a,b]).all() or not np.isfinite(y).all():raise ValueError('finite aligned own-dose inputs required')
    x=np.r_[a,b];target=np.tile(y,2);w=np.tile(weights(p),2)/2
    mean=w@x;my=float(w@target);scale=np.maximum(np.sqrt(w@((x-mean)**2)),.05)
    z=(x-mean)/scale;beta=np.linalg.solve(z.T@(w[:,None]*z)+.01*np.eye(x.shape[1]),z.T@(w*(target-my)))
    return {'mean':mean,'scale':scale,'beta':beta,'mean_y':my}

def predict_ridge(state,x):return state['mean_y']+((np.asarray(x)-state['mean'])/state['scale'])@state['beta']

def context_stats(paid,owner,target):
    a=np.asarray(paid,float);o=np.asarray(owner,int)
    if a.ndim!=2 or a.shape[1]!=64 or o.shape!=(64,) or not np.isfinite(a).all():raise ValueError('64 finite paid observations required')
    other=a[:,o!=target]
    return np.column_stack((other.mean(1),other.std(1),np.quantile(other,[.1,.5,.9],axis=1).T,other.min(1),other.max(1)))

def encode(values,doses,plates,bounds,base,context,target,orientation):
    v=np.asarray(values,float);d=np.asarray(doses,float);plate=np.asarray(plates,int);k=len(d)
    if k not in (2,3) or v.ndim!=2 or v.shape[1]!=k or not np.isfinite(v).all() or not np.isfinite(d).all() or np.any(d<=0) or np.any(np.diff(d)<=0):raise ValueError('ordered 2/3-dose finite curve required')
    if plate.shape!=(k,) or not np.isin(plate,(0,1)).all() or not 0<=target<24 or orientation not in ('A','B'):raise ValueError('invalid public curve metadata')
    lo,hi=np.log(np.asarray(bounds,float));t=(np.log(d)-lo)/(hi-lo)
    vp=np.pad(v,((0,0),(0,3-k)),mode='edge');tp=np.pad(t,(0,3-k),mode='edge');pp=np.pad(plate,(0,3-k),mode='edge')
    slope=np.diff(v,axis=1)/np.diff(t)[None,:];slope=np.pad(slope,((0,0),(0,2-slope.shape[1])),mode='edge')
    nodes=np.r_[0.,t[(t>0)&(t<1)],1.];basis=np.stack([np.interp(nodes,t,np.eye(k)[:,j]) for j in range(k)],axis=1)
    qw=np.sum(np.diff(nodes)[:,None]*(basis[:-1]+basis[1:])/2,axis=0);approx=v@qw
    onehot=np.zeros((len(v),24));onehot[:,target]=1
    out=np.column_stack((onehot,vp,np.tile(tp,(len(v),1)),np.tile(pp,(len(v),1)),slope,np.full(len(v),k),np.asarray(base),approx,context,np.full(len(v),0 if orientation=='A' else 1)))
    if out.shape!=(len(v),46) or not np.isfinite(out).all():raise ValueError('encoded feature contract')
    return out

def build_rows(x,y,p,catalog,bounds,plan,augment):
    x=np.asarray(x,float);y=np.asarray(y,float);p=np.asarray(p,str)
    native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices']);pa=np.asarray(plan['orientation_A_plate_indices']);pb=np.asarray(plan['orientation_B_plate_indices'])
    if x.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(p),24) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('fitting inputs malformed')
    paidA=x[:,native,pa];paidB=x[:,native,pb];ww=weights(p);total_mass=2*len(p)*24
    features=[];labels=[];rowweights=[];states=[];inventory=[]
    for target in range(24):
        pos=np.flatnonzero(owner==target);current=tuple(native[pos].tolist());k=len(pos)
        plateA=pa[pos];plateB=pb[pos]
        eligible=sorted(map(int,np.flatnonzero(catalog.native_target_indices==target)),key=lambda j:float(catalog.concentrations[j]))
        masks=list(combinations(eligible,k)) if augment else [current]
        ca=context_stats(paidA,owner,target);cb=context_stats(paidB,owner,target);target_state=None
        for subset in masks:
            cols=np.asarray(subset);doses=[float(catalog.concentrations[j]) for j in cols]
            a=x[:,cols,plateA];b=x[:,cols,plateB];state=local_ridge(a,b,y[:,target],p)
            aa=predict_ridge(state,a);bb=predict_ridge(state,b)
            for o,v,plate,bp,ctx in (('A',a,plateA,aa,ca),('B',b,plateB,bb,cb)):
                features.append(encode(v,doses,plate,bounds[str(catalog.target_ids[target])],bp,ctx,target,o))
                labels.append(y[:,target]-bp)
                rowweights.append(ww*(total_mass/(24*2*len(masks))))
            if subset==current:target_state=state
        if target_state is None:raise ValueError('current mask missing from augmentation')
        states.append(target_state);inventory.append({'target_index':target,'dose_count':k,'masks':len(masks)})
    xx=np.concatenate(features);yy=np.concatenate(labels);sw=np.concatenate(rowweights)
    if abs(sw.sum()-total_mass)>1e-7:raise ValueError('augmentation changed total fitting weight')
    return xx,yy,sw,states,inventory

def fit_model(x,y,w):
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(w).all() or (w<=0).any():raise ValueError('nonfinite/missing training values rejected')
    return HistGradientBoostingRegressor(**PARAMETERS).fit(x,y,sample_weight=w)

def predict_paid(model,states,paid,plan,catalog,bounds,o):
    paid=np.asarray(paid,float)
    if paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('exactly 64 finite paid values required')
    native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices']);plates=np.asarray(plan[f'orientation_{o}_plate_indices'])
    out=np.empty((len(paid),24));encoded=[];base=[]
    for target in range(24):
        pos=np.flatnonzero(owner==target);v=paid[:,pos];bp=predict_ridge(states[target],v)
        encoded.append(encode(v,[float(catalog.concentrations[i]) for i in native[pos]],plates[pos],bounds[str(catalog.target_ids[target])],bp,context_stats(paid,owner,target),target,o));base.append(bp)
    correction=model.predict(np.concatenate(encoded)).reshape(24,len(paid)).T
    return np.column_stack(base)+correction

def export_trees(model):
    result={'tree_baseline':np.asarray(model._baseline_prediction).reshape(-1)}
    for i,row in enumerate(model._predictors):
        if len(row)!=1:raise ValueError('scalar regressor expected')
        nodes=row[0].nodes.copy()
        if np.any(nodes['is_categorical']):raise ValueError('only numerical tree splits can be exported')
        result[f'tree_{i}']=nodes
    result['tree_count']=np.asarray(len(model._predictors))
    return result

def predict_exported(tree_state,x):
    x=np.asarray(x,float)
    if x.ndim!=2 or not np.isfinite(x).all():raise ValueError('finite features required')
    output=np.full(len(x),float(tree_state['tree_baseline'][0]))
    for i in range(int(tree_state['tree_count'])):
        nodes=tree_state[f'tree_{i}'];idx=np.zeros(len(x),dtype=int)
        for _ in range(len(nodes)):
            active=~nodes['is_leaf'][idx].astype(bool)
            if not active.any():break
            rows=np.flatnonzero(active);nidx=idx[active]
            takeleft=x[rows,nodes['feature_idx'][nidx]]<=nodes['num_threshold'][nidx]
            idx[rows]=np.where(takeleft,nodes['left'][nidx],nodes['right'][nidx])
        else:raise ValueError('invalid cyclic tree')
        output+=nodes['value'][idx]
    return output

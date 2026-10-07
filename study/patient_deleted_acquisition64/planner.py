"""Select physical doses using exact internally patient-deleted prediction risk.
This changes the acquisition risk estimator, not the 64-well budget or outputs.
"""
from __future__ import annotations
from decimal import Decimal
from itertools import combinations
import numpy as np
from coverage_methods import validate_catalog,validate_plan
RIDGE=.01


def patient_moments(x,y,patients):
    x=np.asarray(x,float);y=np.asarray(y,float);p=np.asarray(patients,str)
    if x.ndim!=2 or y.shape!=(len(x),) or p.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('finite aligned scalar-target rows required')
    ids=np.unique(p)
    if len(ids)<3:raise ValueError('at least three fitting patients required')
    rows=[]
    for g in ids:
        a=x[p==g];b=y[p==g]
        rows.append((a.mean(0),a.T@a/len(a),float(b.mean()),a.T@b/len(a),float(np.mean(b*b))))
    return tuple(np.asarray([r[k] for r in rows]) for k in range(5))


def deleted_risk(moments,columns):
    px,pxx,py,pxy,pyy=moments;c=np.asarray(columns,int);g=len(py)
    hx=px[:,c];hxx=pxx[:,c][:,:,c];hxy=pxy[:,c]
    mx=(hx.sum(0)-hx)/(g-1);my=(py.sum()-py)/(g-1)
    xx=(hxx.sum(0)-hxx)/(g-1);xy=(hxy.sum(0)-hxy)/(g-1)
    scale=np.maximum(np.sqrt(np.maximum(np.diagonal(xx,axis1=1,axis2=2)-mx*mx,0)),.05)
    covariance=(xx-mx[:,:,None]*mx[:,None,:])/(scale[:,:,None]*scale[:,None,:])
    cross=(xy-mx*my[:,None])/scale
    standardized=np.linalg.solve(covariance+RIDGE*np.eye(len(c))[None,:,:],cross[:,:,None])[:,:,0]
    beta=standardized/scale;intercept=my-np.sum(mx*beta,axis=1)
    loss=pyy-2*intercept*py-2*np.sum(beta*hxy,axis=1)+intercept**2
    loss+=2*intercept*np.sum(beta*hx,axis=1)+np.einsum('gi,gij,gj->g',beta,hxx,beta)
    if not np.isfinite(loss).all() or loss.min()<-1e-9:raise ValueError('invalid deleted-patient risk')
    return np.maximum(loss,0),beta,intercept


def plan_patient_deleted(replicates,y,patients,catalog):
    validate_catalog(catalog)
    x=np.asarray(replicates,float);y=np.asarray(y,float);p=np.asarray(patients,str)
    if x.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(p),24) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('malformed TRAIN arrays')
    choices=[];all_scores=[]
    for j,target in enumerate(catalog.target_ids):
        native=sorted(map(int,np.flatnonzero(catalog.native_target_indices==j)),key=lambda q:(Decimal(catalog.concentrations[q]),str(catalog.native_ids[q])))
        v=x[:,native,:];full=np.concatenate((v.reshape(len(v),-1),v[:,:,::-1].reshape(len(v),-1)))
        pp=np.concatenate((p,p));yy=np.concatenate((y[:,j],y[:,j]));mom=patient_moments(full,yy,pp);best={}
        for size in (2,3):
            candidates=[]
            for local in combinations(range(len(native)),size):
                subset=tuple(native[q] for q in local);cols=[2*q+i%2 for i,q in enumerate(local)]
                losses,_,_=deleted_risk(mom,cols);score=float(losses.mean());ids=tuple(str(catalog.native_ids[q]) for q in subset)
                candidates.append((score,ids,subset));all_scores.append({'target_index':j,'size':size,'native_indices':list(subset),'patient_deleted_mse':score})
            best[size]=min(candidates)
        choices.append({'target_index':j,'target_id':str(target),'best2':list(best[2][2]),'best3':list(best[3][2]),
            'proxy2':best[2][0],'proxy3':best[3][0],'upgrade_gain':best[2][0]-best[3][0]})
    upgraded={r['target_index'] for r in sorted(choices,key=lambda r:(-r['upgrade_gain'],r['target_id']))[:16]}
    order=sorted(upgraded,key=lambda j:str(catalog.target_ids[j]));starts={j:i%2 for i,j in enumerate(order)}
    selected=[];own=[];plates=[]
    for j in range(24):
        subset=choices[j]['best3' if j in upgraded else 'best2'];selected+=subset;own+=[j]*len(subset)
        plates += [(starts.get(j,0)+i)%2 for i in range(len(subset))]
    plan={'library_id':'lib1','allocation_rule':'exact_leave_one_fitting_patient_out_own_drug_ridge_risk',
       'planning_ridge':RIDGE,'selected_native_indices':selected,'selected_native_ids':[str(catalog.native_ids[q]) for q in selected],
       'coordinate_target_indices':own,'selected_concentrations_nM':[str(catalog.concentrations[q]) for q in selected],
       'orientation_A_plate_indices':plates,'orientation_B_plate_indices':[1-p for p in plates],
       'choices':choices,'all_subset_scores':all_scores,'upgraded_target_ids':[str(catalog.target_ids[j]) for j in order],
       'distinct_native_doses':64,'treatment_wells_per_orientation':64,'plate_wells_per_orientation':{'p1':32,'p2':32},
       'exact_auc_count':0,'prediction_semantics':'raw purchased single-well normalized viability',
       'primary_orientation_semantics':'average losses only; never average A/B predictions'}
    validate_plan(plan,catalog);return plan

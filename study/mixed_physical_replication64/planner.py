"""Mixed replication design: 64 distinct PHYSICAL cells, not necessarily
64 distinct native concentrations. This is an explicit acquisition-contract
extension, never a silent bypass of the incumbent native-dose validator.
"""
from __future__ import annotations
from decimal import Decimal
from itertools import combinations
import numpy as np
ALPHA=.1


def weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or len(p)==0:raise ValueError('nonempty patient vector required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1./(len(ids)*count[inv])


def target_moments(replicates,target,patients):
    v=np.asarray(replicates,float);y=np.asarray(target,float)
    if v.ndim!=3 or v.shape[2]!=2 or y.shape!=(len(v),) or len(patients)!=len(v):raise ValueError('aligned one-target curves required')
    if not np.isfinite(v).all() or not np.isfinite(y).all():raise ValueError('finite fitting rows required')
    x=np.r_[v.reshape(len(v),-1),v[:,:,::-1].reshape(len(v),-1)];yy=np.r_[y,y]
    w=np.tile(weights(patients),2)/2;mx=w@x;my=float(w@yy)
    sx=np.maximum(np.sqrt(w@((x-mx)**2)),.05);z=(x-mx)/sx;yc=yy-my
    return {'cxx':z.T@(w[:,None]*z),'cxy':z.T@(w*yc),'cyy':float(w@(yc*yc))}


def enumerate_physical(dose_count,size,allow_replication):
    if dose_count<3 or size not in (2,3):raise ValueError('native universe/cardinality')
    # Canonical majority is on p1; all A/B rows are scored symmetrically.
    p1=[2*i for i in range(dose_count)];p2=[2*i+1 for i in range(dose_count)]
    rows=[]
    for a in combinations(p1,size-1):
        for b in p2:
            subset=tuple(sorted((*a,b)))
            if not allow_replication and len({q//2 for q in subset})!=size:continue
            rows.append(subset)
    return np.asarray(rows,int)


def batched_proxy(moment,subsets):
    s=np.asarray(subsets,int)
    if s.ndim!=2 or len(s)==0:raise ValueError('nonempty candidate subsets required')
    matrix=moment['cxx'][s[:,:,None],s[:,None,:]]+ALPHA*np.eye(s.shape[1])[None,:,:]
    cross=moment['cxy'][s]
    solution=np.linalg.solve(matrix,cross[:,:,None])[:,:,0]
    value=moment['cyy']-np.sum(cross*solution,axis=1)
    if not np.isfinite(value).all() or value.min()<-1e-10:raise ValueError('invalid variance proxy')
    return np.maximum(value,0.)


def validate_physical(plan,catalog=None):
    native=np.asarray(plan['selected_native_indices'],int);own=np.asarray(plan['coordinate_target_indices'],int)
    pa=np.asarray(plan['orientation_A_plate_indices'],int);pb=np.asarray(plan['orientation_B_plate_indices'],int)
    if native.shape!=(64,) or own.shape!=(64,) or pa.shape!=(64,) or pb.shape!=(64,):raise ValueError('64 paid coordinate slots required')
    if not np.isin(own,np.arange(24)).all() or not np.isin(pa,(0,1)).all() or not np.array_equal(pb,1-pa):raise ValueError('invalid target/layout')
    counts=np.bincount(own,minlength=24)
    if np.sum(counts==2)!=8 or np.sum(counts==3)!=16:raise ValueError('two/three physical-cell target counts changed')
    for plate in (pa,pb):
        if len(set(zip(native.tolist(),plate.tolist())))!=64:raise ValueError('duplicate physical well counted twice')
        if np.bincount(plate,minlength=2).tolist()!=[32,32]:raise ValueError('32/32 per-plate budget required')
        for j in range(24):
            present=plate[own==j]
            if len(set(present.tolist()))!=2:raise ValueError('every target must observe both plates')
    if catalog is not None:
        if native.min()<0 or native.max()>=len(catalog.native_ids) or not np.array_equal(own,catalog.native_target_indices[native]):raise ValueError('native eligibility or ownership changed')
        if list(plan['selected_native_ids'])!=list(map(str,catalog.native_ids[native])):raise ValueError('native identities changed')
    if int(plan['distinct_native_doses'])!=len(set(native.tolist())):raise ValueError('native count misreported')
    if plan.get('allows_same_native_on_both_plates') is False and len(set(native.tolist()))!=64:raise ValueError('replicate forbidden in control arm')


def plan_pair(x,y,p,catalog):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if x.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(p),24):raise ValueError('task arrays changed')
    records={'distinct_physical':[],'mixed_replication':[]}
    for j,name in enumerate(catalog.target_ids):
        native=sorted(map(int,np.flatnonzero(catalog.native_target_indices==j)),key=lambda k:(Decimal(catalog.concentrations[k]),str(catalog.native_ids[k])))
        moment=target_moments(x[:,native,:],y[:,j],p)
        for policy,allow in (('distinct_physical',False),('mixed_replication',True)):
            choices={}
            for size in (2,3):
                subsets=enumerate_physical(len(native),size,allow);scores=batched_proxy(moment,subsets)
                # Deterministic lexicographic physical-coordinate tie break.
                best=min(range(len(scores)),key=lambda k:(float(scores[k]),tuple(subsets[k])))
                selected=subsets[best]
                choices[size]={'native':[native[q//2] for q in selected],'plates':[int(q%2) for q in selected],
                               'risk':float(scores[best]),'enumerated_candidates':len(scores)}
            records[policy].append({'target_index':j,'target_id':str(name),'best2':choices[2],'best3':choices[3],
                                   'upgrade_gain':choices[2]['risk']-choices[3]['risk']})
    plans={}
    for policy,rows in records.items():
        upgraded={r['target_index'] for r in sorted(rows,key=lambda r:(-r['upgrade_gain'],r['target_id']))[:16]}
        order=sorted(upgraded,key=lambda j:str(catalog.target_ids[j]));flip={j:i%2 for i,j in enumerate(order)}
        native=[];own=[];plates=[]
        for j,row in enumerate(rows):
            record=row['best3' if j in upgraded else 'best2']
            native+=record['native'];own += [j]*len(record['native'])
            plates += [v^flip.get(j,0) for v in record['plates']]
        unique=len(set(native));plan={'library_id':'lib1','policy':policy,'allocation_alpha':ALPHA,
           'selected_native_indices':native,'selected_native_ids':[str(catalog.native_ids[q]) for q in native],
           'coordinate_target_indices':own,'orientation_A_plate_indices':plates,'orientation_B_plate_indices':[1-v for v in plates],
           'choices':rows,'upgraded_target_ids':[str(catalog.target_ids[j]) for j in order],
           'distinct_physical_wells':64,'distinct_native_doses':unique,'replicated_native_doses':64-unique,
           'allows_same_native_on_both_plates':policy=='mixed_replication',
           'original_64_distinct_native_contract_satisfied':unique==64,'treatment_wells':64,'per_plate':[32,32],
           'prediction_semantics':'64 individually purchased physical values, not free plate-pair means',
           'orientation_rule':'A/B are alternative acquisitions; average losses only'}
        validate_physical(plan,catalog);plans[policy]=plan
    return plans


def acquire_physical(x,plan,orientation):
    validate_physical(plan)
    if orientation not in ('A','B'):raise ValueError('unknown orientation')
    values=np.asarray(x,float);native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{orientation}_plate_indices'])
    if values.ndim!=3 or values.shape[2]!=2:raise ValueError('native-by-plate query required')
    paid=values[:,native,plate].copy()
    if paid.shape!=(len(values),64) or not np.isfinite(paid).all():raise ValueError('exactly 64 complete purchased values required')
    return paid

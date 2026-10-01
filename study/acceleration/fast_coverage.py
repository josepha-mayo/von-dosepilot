"""Cached-moment implementation of the existing R13 allocation rule.

The scientific objective, candidate dose subsets, alternating plate patterns,
upgrades, tie-breaks and final physical accounting are unchanged. This is an
engineering acceleration, not a new predictor. Near-tied options fall back to
the reference calculation rather than relying on floating-point ordering.
"""
from __future__ import annotations
from itertools import combinations
from decimal import Decimal
import numpy as np
from coverage_methods import validate_catalog,validate_plan,subset_orientations
from sparse_methods import fit_sparse_context
ALPHA=.1
TIE_TOL=1e-12

def plan_panel_fast(replicates,y,patients,catalog):
 validate_catalog(catalog)
 values,y=np.asarray(replicates,float),np.asarray(y,float);patients=np.asarray(patients,str)
 if values.shape!=(len(y),len(catalog.native_ids),2) or y.shape!=(len(patients),24) or not np.isfinite(values).all() or not np.isfinite(y).all():raise ValueError('Malformed fitting data')
 u,inv,count=np.unique(patients,return_inverse=True,return_counts=True)
 norm=np.tile(1./(2*len(u)*count[inv]),2);pp=np.tile(patients,2)
 all_scores=[];choices=[];fallbacks=0
 for j,target in enumerate(catalog.target_ids):
  native=sorted(map(int,np.flatnonzero(catalog.native_target_indices==j)),key=lambda q:(Decimal(catalog.concentrations[q]),str(catalog.native_ids[q])))
  v=values[:,native,:];full=np.r_[v.reshape(len(v),-1),v[:,:,::-1].reshape(len(v),-1)];yy=np.tile(y[:,j],2)
  mx=norm@full;my=norm@yy;sx=np.maximum(np.sqrt(norm@((full-mx)**2)),.05);z=(full-mx)/sx;cy=yy-my
  cxx=(z.T*norm)@z;cxy=(z.T*norm)@cy;cyy=float(norm@(cy*cy));best={}
  for k in (2,3):
   candidates=[]
   for local in combinations(range(len(native)),k):
    subset=tuple(native[q] for q in local);cols=np.array([2*q+i%2 for i,q in enumerate(local)])
    cross=cxy[cols];risk=float(cyy-cross@np.linalg.solve(cxx[np.ix_(cols,cols)]+ALPHA*np.eye(k),cross));ids=tuple(str(catalog.native_ids[q]) for q in subset)
    candidates.append([risk,ids,subset])
   minimum=min(c[0] for c in candidates)
   near=[i for i,c in enumerate(candidates) if abs(c[0]-minimum)<=TIE_TOL]
   # Always compute the winner in the reference arithmetic. Include all near ties.
   for i in near:
    _,ids,subset=candidates[i];a,b=subset_orientations(values,subset)
    ctx=fit_sparse_context(np.r_[a,b],np.tile(y[:,[j]],(2,1)),pp,list(ids),[target]);cross=ctx.cxy[:,0]
    candidates[i][0]=float(ctx.cyy[0,0]-cross@np.linalg.solve(ctx.cxx+ALPHA*np.eye(k),cross))
   fallbacks+=max(0,len(near)-1)
   winner=min((tuple(c) for c in candidates));best[k]=winner
   for r,ids,subset in candidates:all_scores.append({'target_index':j,'target_id':str(target),'size':k,'native_indices':list(subset),'native_ids':list(ids),'residual_proxy':r})
  choices.append({'target_index':j,'target_id':str(target),'best2':list(best[2][2]),'best3':list(best[3][2]),'proxy2':best[2][0],'proxy3':best[3][0],'upgrade_gain':best[2][0]-best[3][0]})
 upgraded={r['target_index'] for r in sorted(choices,key=lambda r:(-r['upgrade_gain'],r['target_id']))[:16]}
 order=sorted(upgraded,key=lambda j:str(catalog.target_ids[j]));starts={j:i%2 for i,j in enumerate(order)}
 selected=[];own=[];plate=[]
 for j in range(24):
  subset=choices[j]['best3' if j in upgraded else 'best2'];selected+=subset;own += [j]*len(subset);plate += [(starts.get(j,0)+i)%2 for i in range(len(subset))]
 plan={'library_id':catalog.library_id,'allocation_alpha':ALPHA,'selected_native_indices':selected,'selected_native_ids':[str(catalog.native_ids[q]) for q in selected],'coordinate_target_indices':own,
   'selected_concentrations_nM':[str(catalog.concentrations[q]) for q in selected],'orientation_A_plate_indices':plate,'orientation_B_plate_indices':[1-p for p in plate],
   'choices':choices,'all_subset_scores':all_scores,'upgraded_target_ids':[str(catalog.target_ids[j]) for j in order],
   'distinct_native_doses':64,'treatment_wells_per_orientation':64,'plate_wells_per_orientation':{'p1':32,'p2':32},'exact_auc_count':0,
   'prediction_semantics':'raw purchased single-well normalized viability','primary_orientation_semantics':'equal average of two alternative orientation losses; never average predictions',
   'implementation':'cached per-target symmetric moments','near_tie_reference_rechecks':fallbacks}
 validate_plan(plan,catalog);return plan

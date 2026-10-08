"""Use routine control fields to transport raw plate values into and out of a
common coordinate system. Endpoints remain the ORIGINAL raw normalized AUCs.
No fitting function accepts held-out treatment outcomes implicitly.
"""
from __future__ import annotations
import numpy as np
FIELD_RIDGE=.1
GAIN_BOUNDS=(.25,4.)
BASE_RIDGE=.01


def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or not len(p):raise ValueError('nonempty patients required')
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1./(len(ids)*count[inv])


def control_plane(positions,signals,center,span,mode):
    pos=np.asarray(positions,float);sig=np.asarray(signals,float)
    if pos.ndim!=2 or pos.shape[1]!=2 or sig.shape!=(len(pos),) or not len(pos):
        raise ValueError('aligned control locations/signals required')
    if not np.isfinite(pos).all() or not np.isfinite(sig).all() or not np.isfinite([center,span]).all() or span<=0:
        raise ValueError('finite controls and positive dynamic range required')
    if mode not in ('identity','flat','spatial'):raise ValueError('unknown fixed arm')
    avg_pos=pos.mean(0);response=(sig-center)/span;intercept=float(response.mean())
    if mode=='identity':return {'center':avg_pos,'intercept':0.,'slope':np.zeros(2),'geometry_rank':0}
    if mode=='flat':return {'center':avg_pos,'intercept':intercept,'slope':np.zeros(2),'geometry_rank':0}
    z=pos-avg_pos
    gram=z.T@z/len(z)+FIELD_RIDGE*np.eye(2)
    slope=np.linalg.solve(gram,z.T@(response-intercept)/len(z))
    # A constant control coordinate has zero slope, not an inferred gradient.
    rank=int(np.linalg.matrix_rank(z))
    return {'center':avg_pos,'intercept':intercept,'slope':slope,'geometry_rank':rank}


def evaluate_plane(plane,positions):
    pos=np.asarray(positions,float)
    if pos.ndim!=2 or pos.shape[1]!=2 or not np.isfinite(pos).all():raise ValueError('finite physical positions required')
    return plane['intercept']+(pos-plane['center'])@plane['slope']


def field(negative_positions,negative_signal,positive_positions,positive_signal,query_positions,mode):
    neg=np.asarray(negative_signal,float);pos=np.asarray(positive_signal,float)
    mn,mp=float(np.median(neg)),float(np.median(pos));span=mn-mp
    if not np.isfinite(span) or span<=0:raise ValueError('controls do not define positive dynamic range')
    nf=control_plane(negative_positions,neg,mn,span,mode)
    pf=control_plane(positive_positions,pos,mp,span,mode)
    additive=evaluate_plane(pf,query_positions)
    raw_gain=1.+evaluate_plane(nf,query_positions)-additive
    gain=np.clip(raw_gain,*GAIN_BOUNDS)
    if not np.isfinite(additive).all() or not np.isfinite(gain).all():raise ValueError('invalid control transform')
    audit={'negative_geometry_rank':nf['geometry_rank'],'positive_geometry_rank':pf['geometry_rank'],
           'gain_clip_count':int(np.sum(gain!=raw_gain)),'gain_min':float(gain.min()),'gain_max':float(gain.max()),
           'max_abs_offset':float(np.max(np.abs(additive)))}
    return additive,gain,audit


def to_latent(raw,offset,gain):
    x,a,g=(np.asarray(v,float) for v in (raw,offset,gain))
    if x.shape!=a.shape or x.shape!=g.shape or not all(np.isfinite(v).all() for v in (x,a,g)) or np.any(g<=0):
        raise ValueError('finite aligned physical fields and values required')
    return (x-a)/g


def fit_curve_head(paid_A,paid_B,latent_full,patients,paid_owner,full_owner):
    a,b,y=(np.asarray(v,float) for v in (paid_A,paid_B,latent_full))
    own=np.asarray(paid_owner,int);full=np.asarray(full_owner,int)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=64 or y.ndim!=2 or len(y)!=len(a) or len(patients)!=len(a):
        raise ValueError('64 purchased coordinates and aligned fitting curves required')
    if own.shape!=(64,) or full.shape!=(y.shape[1],) or set(own)!=set(full):raise ValueError('target ownership mismatch')
    if not all(np.isfinite(v).all() for v in (a,b,y)):raise ValueError('nonfinite fitting data')
    x=np.r_[a,b];yy=np.r_[y,y];w=np.tile(patient_weights(patients),2)/2
    mx=w@x;my=w@yy;sx=np.maximum(np.sqrt(w@((x-mx)**2)),.05)
    z=(x-mx)/sx;centered=yy-my;beta=np.zeros((64,y.shape[1]))
    for target in np.unique(own):
        cols=np.flatnonzero(own==target);out=np.flatnonzero(full==target);xx=z[:,cols]
        beta[np.ix_(cols,out)]=np.linalg.solve(xx.T@(w[:,None]*xx)+BASE_RIDGE*np.eye(len(cols)),xx.T@(w[:,None]*centered[:,out]))
    return {'mean_x':mx,'scale_x':sx,'mean_curve':my,'beta_curve':beta}


def predict_curve_head(state,latent_paid,full_offset,full_gain,quadrature):
    x=np.asarray(latent_paid,float);a=np.asarray(full_offset,float);g=np.asarray(full_gain,float);q=np.asarray(quadrature,float)
    if x.ndim!=2 or x.shape[1]!=64 or a.shape!=g.shape or a.shape!=(len(x),len(state['mean_curve'])) or q.shape[0]!=a.shape[1]:
        raise ValueError('query shape mismatch')
    if not all(np.isfinite(v).all() for v in (x,a,g,q)) or (g<=0).any():raise ValueError('invalid query fields')
    latent=state['mean_curve']+((x-state['mean_x'])/state['scale_x'])@state['beta_curve']
    raw=a+g*latent
    return raw@q

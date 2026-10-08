"""Two-stage retrospective acquisition with an explicit physical measurement budget.
No query outcomes beyond the first 48 values enter choose_actions(). Risk is
expected squared error of a fixed fitting-only ridge head under a curve mixture.
"""
from __future__ import annotations
import numpy as np
import shape_prior


def fit_ridge(curves, y, patients, indices):
    """Fit the same own-drug ridge on complementary training layouts."""
    x=np.asarray(curves,float);y=np.asarray(y,float);ix=np.asarray(indices,int)
    if x.ndim!=3 or x.shape[2]!=2 or y.shape!=(len(x),) or len(patients)!=len(x):
        raise ValueError('aligned fitting rows required')
    v=x.reshape(len(x),-1);paid=np.concatenate((v[:,ix],v[:,ix^1]))
    labels=np.tile(y,2);weights=np.tile(shape_prior.patient_weights(patients),2)/2
    mean=weights@paid;my=float(weights@labels)
    scale=np.maximum(np.sqrt(weights@((paid-mean)**2)),.05);z=(paid-mean)/scale
    beta=np.linalg.solve(z.T@(weights[:,None]*z)+.01*np.eye(len(ix)),z.T@(weights*(labels-my)))/scale
    return beta,float(my-mean@beta)


def risk_state(population, observed_indices, quadrature, ridge_beta, intercept, extra_index=None):
    """Exact conditional risk for a linear estimator in a Gaussian mixture.
    The unpurchased candidate value is integrated out, never read.
    """
    means=np.asarray(population['means'],float);cov=np.asarray(population['covariance'],float)
    weights=np.asarray(population['weights'],float);a=np.asarray(observed_indices,int)
    q=np.asarray(quadrature,float);beta=np.asarray(ridge_beta,float)
    if a.shape!=(2,) or len(set(a))!=2 or q.shape!=(means.shape[1],) or beta.shape not in ((2,),(3,)):
        raise ValueError('two initial measurements and a two/three-input estimator required')
    if (extra_index is None)!=(len(beta)==2):raise ValueError('estimator/candidate mismatch')
    if not all(np.isfinite(v).all() for v in (means,cov,weights,q,beta)) or not np.isfinite(intercept):
        raise ValueError('nonfinite risk model')
    css=cov[np.ix_(a,a)];precision=np.linalg.solve(css,np.eye(2));transport=cov[:,a]@precision
    residual_cov=cov-transport@cov[a]
    functional=-q.copy()
    if extra_index is not None:
        if extra_index in set(a) or not 0<=extra_index<len(q):raise ValueError('invalid new physical coordinate')
        functional[extra_index]+=beta[2]
    slope=transport.T@functional
    offsets=intercept+means@functional-means[:,a]@slope
    variance=float(functional@residual_cov@functional)
    if variance < -1e-9:raise ValueError('negative conditional variance')
    total=functional.copy();total[a]+=beta[:2]
    unconditional=float(total@cov@total+weights@((intercept+means@total)**2))
    return {'observed_means':means[:,a].copy(),'precision':precision,'weights':weights.copy(),
       'offsets':offsets,'slope':slope+beta[:2],'variance':np.asarray(max(variance,0.)),
       'unconditional_risk':np.asarray(max(unconditional,0.))}


def conditional_risk(state, observed):
    x=np.asarray(observed,float)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():raise ValueError('exactly two finite initial readings required')
    delta=x[:,None,:]-state['observed_means'][None,:,:]
    dist=np.einsum('bni,ij,bnj->bn',delta,state['precision'],delta)
    logp=np.log(state['weights'])[None,:]-.5*dist;logp-=logp.max(axis=1,keepdims=True)
    posterior=np.exp(logp);posterior/=posterior.sum(axis=1,keepdims=True)
    conditional_mean=state['offsets'][None,:]+(x@state['slope'])[:,None]
    risk=float(state['variance'])+np.sum(posterior*conditional_mean**2,axis=1)
    if not np.isfinite(risk).all() or risk.min() < -1e-12:raise ValueError('invalid conditional risk')
    return risk


def balanced_choices(costs, budget_per_plate=8):
    """DP: one option per target, exactly k third wells on each plate.
    costs[j] = (no third well, one on p1, one on p2). Smallest code breaks ties.
    """
    cost=np.asarray(costs,float);k=int(budget_per_plate)
    if cost.ndim!=2 or cost.shape[1]!=3 or not np.isfinite(cost).all() or k<0 or 2*k>len(cost):
        raise ValueError('feasible finite target costs required')
    states={(0,0):(0.,())}
    for row in cost:
        nxt={}
        for (a,b),(loss,path) in states.items():
            for code,(da,db) in enumerate(((0,0),(1,0),(0,1))):
                key=(a+da,b+db)
                if key[0]>k or key[1]>k:continue
                candidate=(loss+float(row[code]),path+(code,))
                if key not in nxt or candidate<nxt[key]:nxt[key]=candidate
        states=nxt
    if (k,k) not in states:raise ValueError('no feasible allocation')
    loss,path=states[(k,k)];return np.asarray(path,int),float(loss)


def build_bank(training_full, training_y, patients, catalog, full_owner, query_to_full, q, positions, original_plan):
    """No held-out rows may be passed. Store numeric sufficient state only."""
    x=np.asarray(training_full,float);y=np.asarray(training_y,float)
    if x.ndim!=3 or y.shape!=(len(x),24) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('finite training matrices with 24 targets required')
    bank={}
    for j in range(24):
        full_indices=np.flatnonzero(full_owner==j);physical=np.column_stack((2*full_indices,2*full_indices+1)).reshape(-1)
        local={int(v):i for i,v in enumerate(full_indices)}
        curves=x[:,full_indices,:];quadrature=q[physical,j]
        population=shape_prior.fit_population(curves,positions[j],patients)
        start=np.asarray(original_plan['choices'][j]['best2'],int)
        if len(start)!=2 or len(set(start))!=2:raise ValueError('original best-two plan malformed')
        choices=[int(v) for v in np.flatnonzero(catalog.native_target_indices==j) if int(v) not in set(start)]
        if not choices:raise ValueError('no eligible third dose')
        bank[f't{j}_means']=population['means'];bank[f't{j}_covariance']=population['covariance'];bank[f't{j}_weights']=population['weights']
        bank[f't{j}_quadrature']=quadrature;bank[f't{j}_initial_native']=start
        for seed in (0,1):
            initial=np.array([2*local[int(query_to_full[n])]+p for n,p in zip(start,(seed,1-seed))])
            # Baseline option zero, followed by candidate native IDs and both plates.
            natives=[-1]+[n for n in choices for plate in (0,1)]
            plates=[-1]+[plate for n in choices for plate in (0,1)]
            physical_extra=[-1]+[2*local[int(query_to_full[n])]+plate for n in choices for plate in (0,1)]
            prefix=f't{j}_s{seed}_';bank[prefix+'option_native']=np.asarray(natives,int);bank[prefix+'option_plate']=np.asarray(plates,int)
            bank[prefix+'physical_extra']=np.asarray(physical_extra,int);bank[prefix+'initial_physical']=initial
            betas=[];biases=[];offsets=[];slopes=[];variances=[];unconditional=[]
            for option,extra in enumerate(physical_extra):
                indices=initial if option==0 else np.r_[initial,extra]
                beta,bias=fit_ridge(curves,y[:,j],patients,indices)
                state=risk_state(population,initial,quadrature,beta,bias,None if option==0 else extra)
                betas.append(np.r_[beta,0.] if option==0 else beta);biases.append(bias)
                offsets.append(state['offsets']);slopes.append(state['slope']);variances.append(state['variance']);unconditional.append(state['unconditional_risk'])
            for key,value in {'betas':betas,'intercepts':biases,'risk_offsets':offsets,'risk_slopes':slopes,'risk_variances':variances,'static_risk':unconditional}.items():
                bank[prefix+key]=np.asarray(value)
            bank[prefix+'observed_means']=population['means'][:,initial]
            bank[prefix+'precision']=np.linalg.solve(population['covariance'][np.ix_(initial,initial)],np.eye(2))
    return bank


def choose_actions(bank, initial_readings, seed, adaptive=True):
    """The complete acquisition policy. Deliberately accepts NO later readings."""
    x=np.asarray(initial_readings,float)
    if x.ndim!=3 or x.shape[1:]!=(24,2) or not np.isfinite(x).all() or seed not in (0,1):
        raise ValueError('exactly 48 finite purchased first-round values required')
    costs=np.empty((len(x),24,3));options=np.zeros((len(x),24,3),int)
    for j in range(24):
        pre=f't{j}_s{seed}_';plates=bank[pre+'option_plate']
        if adaptive:
            v=x[:,j,:];d=v[:,None,:]-bank[pre+'observed_means'][None,:,:]
            logp=np.log(bank[f't{j}_weights'])[None,:]-.5*np.einsum('bni,ij,bnj->bn',d,bank[pre+'precision'],d)
            logp-=logp.max(1,keepdims=True);post=np.exp(logp);post/=post.sum(1,keepdims=True)
            mean=bank[pre+'risk_offsets'][None,:,:]+np.einsum('bd,kd->bk',v,bank[pre+'risk_slopes'])[:,:,None]
            allcost=bank[pre+'risk_variances'][None,:]+np.sum(post[:,None,:]*mean**2,axis=2)
        else:allcost=np.repeat(bank[pre+'static_risk'][None,:],len(x),axis=0)
        costs[:,j,0]=allcost[:,0]
        for plate in (0,1):
            ids=np.flatnonzero(plates==plate);best=ids[np.argmin(allcost[:,ids],axis=1)]
            options[:,j,1+plate]=best;costs[:,j,1+plate]=allcost[np.arange(len(x)),best]
    selected=np.zeros((len(x),24),int);expected=[]
    for i in range(len(x)):
        code,risk=balanced_choices(costs[i],8);selected[i]=options[i,np.arange(24),code];expected.append(risk/24)
    return selected,np.asarray(expected)


def validate_actions(bank, actions, seed):
    a=np.asarray(actions,int)
    if a.ndim!=2 or a.shape[1]!=24 or seed not in (0,1):raise ValueError('24 target action indices required')
    for row in a:
        cells=[];natives=[];counts=[24,24]
        for j,option in enumerate(row):
            pre=f't{j}_s{seed}_';start=bank[f't{j}_initial_native']
            cells.extend(zip(start.tolist(),(seed,1-seed)));natives.extend(start.tolist())
            if not 0<=option<len(bank[pre+'option_native']):raise ValueError('unknown action')
            if option:
                native=int(bank[pre+'option_native'][option]);plate=int(bank[pre+'option_plate'][option])
                if native in start:raise ValueError('repurchasing first-round native dose')
                cells.append((native,plate));natives.append(native);counts[plate]+=1
        if len(cells)!=64 or len(set(cells))!=64 or len(set(natives))!=64 or counts!=[32,32] or np.sum(row>0)!=16:
            raise ValueError('physical cost or distinct-dose contract violated')
    return True


def infer(bank, initial_readings, actions, final_readings, seed, estimator='ridge'):
    x=np.asarray(initial_readings,float);a=np.asarray(actions,int);z=np.asarray(final_readings,float)
    validate_actions(bank,a,seed)
    if x.shape!=(len(a),24,2) or z.shape!=a.shape or not np.isfinite(x).all() or not np.isfinite(z[a>0]).all():
        raise ValueError('missing purchased query value')
    if estimator not in ('ridge','mixture'):raise ValueError('unknown declared estimator')
    out=np.empty((len(a),24))
    for j in range(24):
        pre=f't{j}_s{seed}_'
        for option in np.unique(a[:,j]):
            ix=np.flatnonzero(a[:,j]==option);paid=x[ix,j,:]
            if option:paid=np.column_stack((paid,z[ix,j]))
            if estimator=='ridge':
                beta=bank[pre+'betas'][option,:paid.shape[1]];out[ix,j]=bank[pre+'intercepts'][option]+paid@beta
            else:
                population={k:bank[f't{j}_{k}'] for k in ('means','covariance','weights')}
                physical=bank[pre+'initial_physical']
                if option:physical=np.r_[physical,bank[pre+'physical_extra'][option]]
                state=shape_prior.condition(population,physical,bank[f't{j}_quadrature'],'mixture')
                out[ix,j]=shape_prior.predict(state,paid)
    if not np.isfinite(out).all():raise ValueError('nonfinite prediction')
    return out

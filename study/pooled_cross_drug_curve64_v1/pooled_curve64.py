"""Shared plus drug-specific nonlinear residual mapping from paid wells only.

This is an experimental implementation of established multitask regularization,
not a claim of a new statistical method or measured DosePilot improvement.
"""
from __future__ import annotations
import numpy as np

FEATURE_SEED=202610071328
RFF_COMPONENTS=64
ALPHAS=(.001,.01,.1)
FEATURE_DIM=15

def patient_weights(patients):
    p=np.asarray(patients,str)
    if p.ndim!=1 or len(p)==0 or np.any(np.char.str_len(p)==0):
        raise ValueError('nonempty one-dimensional patient identities required')
    groups,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1.0/(len(groups)*count[inv])

def assert_disjoint(train_patients,test_patients):
    if set(map(str,train_patients))&set(map(str,test_patients)):
        raise ValueError('patient leakage across fitting and evaluation')

def encode_paid(paid,baseline,plan,bounds,orientation):
    """Return (n*24,15) rows, in sample-major, target-minor order.

    Zero padding marks the ABSENT third coordinate of a two-dose target. It never
    imputes a missing purchased reading: all 64 purchased readings must be finite.
    """
    x=np.asarray(paid,float);bp=np.asarray(baseline,float)
    if x.ndim!=2 or x.shape[1]!=64 or bp.shape!=(len(x),24):raise ValueError('64 paid values and 24 base predictions required')
    if not np.isfinite(x).all() or not np.isfinite(bp).all():raise ValueError('nonfinite purchased value/prediction')
    if orientation not in ('A','B'):raise ValueError('unknown alternative layout')
    raw_owner=np.asarray(plan['coordinate_target_indices'])
    if raw_owner.shape!=(64,) or not np.issubdtype(raw_owner.dtype,np.integer):raise ValueError('integer ownership required')
    owner=raw_owner.astype(int);counts=np.bincount(owner,minlength=24) if np.min(owner)>=0 else np.array([])
    if counts.shape!=(24,) or np.sum(counts==2)!=8 or np.sum(counts==3)!=16:raise ValueError('frozen 2/3-dose contract violated')
    native=np.asarray(plan['selected_native_indices']);dose=np.asarray(plan['selected_concentrations_nM'],float)
    plate=np.asarray(plan[f'orientation_{orientation}_plate_indices']);other=np.asarray(plan[f'orientation_{"B" if orientation=="A" else "A"}_plate_indices'])
    if native.shape!=(64,) or len(set(native.tolist()))!=64 or dose.shape!=(64,) or not np.isfinite(dose).all() or (dose<=0).any():raise ValueError('malformed native identities/doses')
    if plate.shape!=(64,) or not np.isin(plate,(0,1)).all() or np.sum(plate==0)!=32 or not np.array_equal(other,1-plate):raise ValueError('32/32 complementary physical layout required')
    b=np.asarray(bounds,float)
    if b.shape!=(24,2) or not np.isfinite(b).all() or (b[:,0]<=0).any() or (b[:,1]<=b[:,0]).any():raise ValueError('fixed valid endpoint bounds required')
    out=np.zeros((len(x),24,FEATURE_DIM),float)
    for t in range(24):
        cols=np.flatnonzero(owner==t);cols=cols[np.argsort(dose[cols],kind='stable')];k=len(cols)
        if len(set(dose[cols]))!=k:raise ValueError('duplicate dose within target')
        pos=(np.log(dose[cols])-np.log(b[t,0]))/np.log(b[t,1]/b[t,0])
        out[:,t,:k]=pos
        out[:,t,3:3+k]=x[:,cols]
        out[:,t,6:6+k]=1.0
        out[:,t,9:9+k]=2*plate[cols]-1
        out[:,t,12]=bp[:,t]
        out[:,t,13]=np.mean(x[:,cols],axis=1)
        out[:,t,14]=pos[-1]-pos[0]
    return out.reshape(-1,FEATURE_DIM),np.tile(np.arange(24),len(x))

def solve_shared_private(phi,residual,tasks,weights,alpha,task_count):
    """Exact block-Schur solution for shared and task-specific ridge effects.

    Objective: sum_i w_i (r_i - phi_i a - phi_i b_task(i))^2
               + alpha * (||a||^2 + sum_t ||b_t||^2).
    """
    f=np.asarray(phi,float);r=np.asarray(residual,float);raw_task=np.asarray(tasks);w=np.asarray(weights,float)
    if f.ndim!=2 or r.shape!=(len(f),) or w.shape!=r.shape or raw_task.shape!=r.shape:raise ValueError('aligned rows required')
    if not np.issubdtype(raw_task.dtype,np.integer):raise ValueError('integer task indices required')
    t=raw_task.astype(int)
    if not isinstance(task_count,int) or task_count<1 or set(t)!=set(range(task_count)):raise ValueError('all declared tasks must have fitting rows')
    if not all(np.isfinite(v).all() for v in (f,r,w)) or (w<=0).any() or not np.isclose(w.sum(),1,atol=1e-12,rtol=0):raise ValueError('finite arrays and positive normalized weights required')
    if not np.isfinite(alpha) or alpha<=0:raise ValueError('positive ridge required')
    m=f.shape[1];eye=np.eye(m);schur=alpha*eye.copy();rhs=np.zeros(m);cache=[]
    for j in range(task_count):
        mask=t==j;fj=f[mask];wj=w[mask];rj=r[mask]
        gram=fj.T@(wj[:,None]*fj);cross=fj.T@(wj*rj)
        # Algebraically equivalent to G - G(G+alpha I)^-1 G, but avoids cancellation.
        inv_g=np.linalg.solve(gram+alpha*eye,gram)
        inv_c=np.linalg.solve(gram+alpha*eye,cross)
        schur+=alpha*inv_g;rhs+=alpha*inv_c
        cache.append((gram,cross))
    shared=np.linalg.solve((schur+schur.T)/2,rhs)
    private=np.stack([np.linalg.solve(gram+alpha*eye,cross-gram@shared) for gram,cross in cache])
    discrepancy=[]
    shared_residual=np.zeros(m)
    for j,(gram,cross) in enumerate(cache):
        normal=cross-gram@(shared+private[j]);shared_residual+=normal
        discrepancy.append(float(np.max(np.abs(normal-alpha*private[j]))))
    discrepancy.append(float(np.max(np.abs(shared_residual-alpha*shared))))
    if max(discrepancy)>1e-9:raise ValueError('normal equations failed')
    return {'shared':shared,'private':private,'max_normal_equation_error':max(discrepancy)}

class PooledCurveResidual:
    def __init__(self,alpha=.01,task_count=24):
        if alpha not in ALPHAS:raise ValueError('outside fixed regularization menu')
        self.alpha=float(alpha);self.task_count=int(task_count);self.state=None
    def fit(self,features,residual,tasks,patients):
        x=np.asarray(features,float)
        if x.ndim!=2 or x.shape[1]!=FEATURE_DIM or not np.isfinite(x).all():raise ValueError('finite 15-column curve representation required')
        w=patient_weights(patients)
        if len(w)!=len(x):raise ValueError('patient row alignment')
        mean=w@x;scale=np.maximum(np.sqrt(w@((x-mean)**2)),.05)
        z=(x-mean)/scale;rng=np.random.default_rng(FEATURE_SEED)
        omega=rng.normal(size=(FEATURE_DIM,RFF_COMPONENTS))/np.sqrt(FEATURE_DIM)
        phase=rng.uniform(0,2*np.pi,RFF_COMPONENTS)
        phi=np.c_[np.ones(len(z)),z,np.sqrt(2/RFF_COMPONENTS)*np.cos(z@omega+phase)]
        solved=solve_shared_private(phi,residual,tasks,w,self.alpha,self.task_count)
        self.state={**solved,'mean':mean,'scale':scale,'omega':omega,'phase':phase,'alpha':self.alpha,'task_count':self.task_count}
        return self
    def predict(self,features,tasks):
        if self.state is None:raise ValueError('model not fitted')
        return self.predict_state(self.state,features,tasks)
    @staticmethod
    def predict_state(state,features,tasks):
        x=np.asarray(features,float);tt=np.asarray(tasks)
        if x.ndim!=2 or x.shape[1]!=FEATURE_DIM or not np.isfinite(x).all() or tt.shape!=(len(x),) or not np.issubdtype(tt.dtype,np.integer):raise ValueError('invalid query features/tasks')
        if np.any(tt<0) or np.any(tt>=int(state['task_count'])):raise ValueError('unknown drug/task')
        z=(x-state['mean'])/state['scale'];phi=np.c_[np.ones(len(z)),z,np.sqrt(2/RFF_COMPONENTS)*np.cos(z@state['omega']+state['phase'])]
        coefficients=state['shared'][None,:]+state['private'][tt]
        return np.einsum('ij,ij->i',phi,coefficients)

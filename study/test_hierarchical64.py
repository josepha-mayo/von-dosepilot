"""Synthetic algebra tests; no biological outcomes read."""
import numpy as np
from hierarchical64 import conditional_coefficients,structured_covariance,patient_weights,fit_populations,predict

def run():
    rng=np.random.default_rng(81026)
    n=12;latent=rng.normal(size=(2*n,2*n));cov=latent@latent.T+.3*np.eye(2*n)
    cm=cov[:n,:n];cd=cov[n:,n:];cmd=cov[:n,n:]
    indices=np.array([1,2,4,7,9]);sign=np.array([1,-1,1,-1,1]);W=rng.normal(size=(n,3))
    H=np.zeros((len(indices),2*n));H[np.arange(len(indices)),indices]=1
    H[np.arange(len(indices)),n+indices]=sign
    L=np.r_[W,np.zeros_like(W)]
    obs=H@cov@H.T
    expected=np.linalg.solve(obs+.01*np.diag(np.diag(obs)),H@cov@L)
    actual=conditional_coefficients(cm,cd,cmd,indices,sign,W,.01)
    assert np.allclose(actual,expected,rtol=1e-11,atol=1e-11)
    mirrored=conditional_coefficients(cm,cd,-cmd,indices,-sign,W,.01)
    assert np.allclose(actual,mirrored,atol=1e-12)
    diagonal=np.diag(np.linspace(.1,1.,n));q=np.eye(n)
    direct=conditional_coefficients(diagonal,diagonal,np.zeros((n,n)),np.arange(n),np.ones(n),q,0.)
    assert np.allclose(direct,.5*np.eye(n),atol=1e-12)
    p=np.array(['A','A','B','C','C','C']);w=patient_weights(p)
    assert all(abs(w[p==g].sum()-1/3)<1e-12 for g in np.unique(p))
    x=rng.normal(size=(30,12,2));patients=np.array([f'P{i//2}' for i in range(30)]);owner=np.repeat(np.arange(3),4)
    populations=fit_populations(x,patients,owner)
    repeat=fit_populations(np.repeat(x,2,axis=0),np.repeat(patients,2),owner)
    for a,b in zip(populations,repeat):
        joint=np.block([[a['cm'],a['cmd']],[a['cmd'].T,a['cd']]])
        assert np.linalg.eigvalsh(joint).min()>-1e-8
        for k in ('mean_m','mean_d','scale','cm','cd','cmd'):
            assert np.allclose(a[k],b[k],atol=1e-10,rtol=1e-10)
    state={'mean_y':np.zeros(24),'orientations':{'A':{'mean_x':np.zeros(64),'scale_x':np.ones(64),'beta':np.ones((64,24))/64}}}
    assert np.allclose(predict(state,np.ones((2,64)),'A'),1.)
    for bad in (np.ones((2,63)),np.full((2,64),np.nan)):
        try:predict(state,bad,'A')
        except ValueError:pass
        else:raise AssertionError('malformed input accepted')
    print('PASS: direct Gaussian equivalence, plate exchange, independent diagonal case, equal patient mass, PSD mixtures, replication invariance, purchased-input contract',flush=True)

if __name__=='__main__':run()

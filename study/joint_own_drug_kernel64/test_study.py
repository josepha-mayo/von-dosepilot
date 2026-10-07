import unittest
import numpy as np
from joint import solve_joint, predict_joint

class JointTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(114)
        z=rng.normal(size=(17,6)); y=rng.normal(size=(17,3))
        w=np.arange(1,18,dtype=float); w/=w.sum()
        z-=w@z; y-=w@y
        phi=rng.normal(size=(17,8)); phi-=w@phi
        k=phi@phi.T; sw=np.sqrt(w)
        e,u=np.linalg.eigh(sw[:,None]*k*sw[None,:])
        return z,y,w,np.repeat(np.arange(3),2),k,e,u
    def test_independent_summed_kernel_solution(self):
        z,y,w,owner,k,e,u=self.fixture(); kap=.3; lam=.01
        state=solve_joint(z,y,w,owner,e,u,kap,lam)
        pred=predict_joint(z,k,state); sw=np.sqrt(w)
        expected=np.empty_like(y)
        for j in range(3):
            q=z[:,owner==j]; combined=k+(kap/lam)*(q@q.T)
            a=np.linalg.solve(sw[:,None]*combined*sw[None,:]+kap*np.eye(len(w)),sw*y[:,j])
            expected[:,j]=combined@(sw*a)
        np.testing.assert_allclose(pred,expected,atol=3e-11,rtol=0)
    def test_joint_objective_not_worse_than_sequential(self):
        z,y,w,owner,k,e,u=self.fixture(); kap=1.;lam=.01; sw=np.sqrt(w)
        state=solve_joint(z,y,w,owner,e,u,kap,lam)
        beta=np.zeros_like(state['beta'])
        for j in range(3):
            c=np.flatnonzero(owner==j); q=z[:,c]
            beta[c,j]=np.linalg.solve(q.T@(w[:,None]*q)+lam*np.eye(2),q.T@(w*y[:,j]))
        coef=sw[:,None]*np.linalg.solve(sw[:,None]*k*sw[None,:]+kap*np.eye(len(w)),sw[:,None]*(y-z@beta))
        def objective(b,a):
            residual=y-z@b-k@a
            return np.sum(w[:,None]*residual**2)+lam*np.sum(b*b)+kap*np.sum(a*(k@a))
        self.assertLessEqual(objective(state['beta'],state['coef']),objective(beta,coef)+1e-10)
    def test_zero_kernel_recovers_own_drug_ridge(self):
        z,y,w,owner,k,e,u=self.fixture()
        state=solve_joint(z,y,w,owner,np.zeros(len(w)),np.eye(len(w)),1.,.01)
        for j in range(3):
            c=np.flatnonzero(owner==j);q=z[:,c]
            b=np.linalg.solve(q.T@(w[:,None]*q)+.01*np.eye(2),q.T@(w*y[:,j]))
            np.testing.assert_allclose(state['beta'][c,j],b,atol=1e-12)
    def test_normal_equations(self):
        z,y,w,owner,k,e,u=self.fixture()
        s=solve_joint(z,y,w,owner,e,u,1.,.01)
        self.assertLess(s['max_stationarity_error'],1e-11)
    def test_nonfinite_rejected(self):
        z,y,w,owner,k,e,u=self.fixture();z[0,0]=np.nan
        with self.assertRaises(ValueError): solve_joint(z,y,w,owner,e,u,1.)
    def test_wrong_query_shape_rejected(self):
        z,y,w,owner,k,e,u=self.fixture();s=solve_joint(z,y,w,owner,e,u,1.)
        with self.assertRaises(ValueError): predict_joint(z[:,:-1],k,s)
    def test_nan_query_rejected(self):
        z,y,w,owner,k,e,u=self.fixture();s=solve_joint(z,y,w,owner,e,u,1.);k[0,0]=np.nan
        with self.assertRaises(ValueError): predict_joint(z,k,s)

if __name__=='__main__': unittest.main(verbosity=2)

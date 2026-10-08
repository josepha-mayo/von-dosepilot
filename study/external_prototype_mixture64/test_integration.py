"""Synthetic 24-target end-to-end state test, with no external/patient file I/O."""
import unittest
from types import SimpleNamespace
import numpy as np
import run_study as r

class WiringTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(281);x=rng.normal(size=(30,72,2));p=np.array([f'p{i//2}' for i in range(30)])
        owner=np.repeat(np.arange(24),3);targets=np.array([f't{i}' for i in range(24)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=targets,
            native_target_indices=owner,concentrations=tuple(['1','10','100']*24))
        centres=rng.normal(size=(11,5));weights=np.full(11,1/11)
        cov=r.external_covariance(centres,weights)+.1*np.eye(5)
        bank={'centres5':centres,'weights':weights,'mean5':weights@centres,'covariance5':cov}
        q=np.zeros((144,24));metadata=[]
        for j in range(24):
            ix=np.arange(3*j,3*j+3);local=np.full(72,-1,int);local[ix]=np.arange(3);pos=np.array([0.,.5,1.])
            qw=np.repeat(np.array([.25,.5,.25])/2,2);q[6*j:6*j+6,j]=qw
            metadata.append({'native':ix,'quadrature':qw,'source_correlation':r.relative_correlation(cov,pos),
                 'glob_to_local':local,'positions':pos,'source_bank':bank})
        y=x.reshape(30,-1)@q;full={'values':x.copy(),'owner':owner,'query_to_full':np.arange(72),'q':q}
        return x,y,p,cat,full,metadata
    def test_all_arms_saved_numeric_state_replay(self):
        x,y,p,cat,full,meta=self.fixture();bundle=r.build(x,y,p,cat,full,meta,np.arange(22))
        pred=r.predict_all(x,np.arange(22,30),bundle)
        self.assertEqual(pred.shape,(3,10,2,8,24));self.assertTrue(np.isfinite(pred).all())
        self.assertEqual(len(set(bundle['plan']['selected_native_indices'])),64)
        for vi in range(3):
            state=r.pack_payload(bundle,10*vi+4);state['kernel_weights']=bundle['variants'][vi]['kernel'].w.copy()
            self.assertEqual(int(state['mixture_flag']),int(vi==2))
            for oi,o in enumerate(('A','B')):
                paid=r.g.acquire(x[22:],bundle['plan'],o)
                np.testing.assert_allclose(r.predict_payload(state,paid,o),pred[vi,4,oi],atol=1e-12,rtol=0)
    def test_query_labels_and_unfitted_curves_never_reach_model(self):
        x,y,p,cat,full,meta=self.fixture();tr=np.arange(22);te=np.arange(22,30)
        first=r.build(x,y,p,cat,full,meta,tr);pred=r.predict_all(x,te,first)
        xx=x.copy();yy=y.copy();ff=dict(full);ff['values']=full['values'].copy()
        xx[te]+=31;yy[te]-=103;ff['values'][te]+=117
        second=r.build(xx,yy,p,cat,ff,meta,tr);again=r.predict_all(x,te,second)
        np.testing.assert_array_equal(pred,again)

if __name__=='__main__':unittest.main(verbosity=2)

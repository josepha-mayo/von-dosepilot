import unittest
from types import SimpleNamespace
import numpy as np
import run_study as r

class WiringTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(827);x=rng.normal(size=(30,72,2));p=np.array([f'p{i//2}' for i in range(30)])
        own=np.repeat(np.arange(24),3);ids=np.array([f't{i}' for i in range(24)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=ids,native_target_indices=own,concentrations=tuple(['1','10','100']*24))
        q=np.zeros((144,24));meta=[]
        for j in range(24):
            ix=np.arange(3*j,3*j+3);local=np.full(72,-1,int);local[ix]=np.arange(3);qw=np.repeat(np.array([.25,.5,.25])/2,2);q[6*j:6*j+6,j]=qw
            meta.append({'native':ix,'quadrature':qw,'pooled_correlation':np.eye(3),
                 'partial_correlation':.4*np.ones((3,3))+.6*np.eye(3),'glob_to_local':local,'positions':np.array([0,.5,1])})
        y=x.reshape(30,-1)@q;full={'values':x.copy(),'owner':own,'query_to_full':np.arange(72),'q':q}
        return x,y,p,cat,full,meta
    def test_three_arms_distinct_and_saved_models_replay(self):
        x,y,p,cat,full,meta=self.fixture();bundle=r.build(x,y,p,cat,full,meta,np.arange(22));pred=r.predict_all(x,np.arange(22,30),bundle)
        self.assertEqual(pred.shape,(3,10,2,8,24));self.assertTrue(np.isfinite(pred).all())
        self.assertGreater(float(np.max(abs(pred[1]-pred[2]))),1e-8)
        for vi in range(3):
            s=r.g.payload(bundle,10*vi+4);s['kernel_weights']=bundle['variants'][vi]['kernel'].w.copy()
            for oi,o in enumerate(('A','B')):
                paid=r.g.acquire(x[22:],bundle['plan'],o)
                np.testing.assert_allclose(r.g.predict_payload(s,paid,o),pred[vi,4,oi],atol=1e-12,rtol=0)
    def test_test_labels_and_full_curves_are_excluded(self):
        x,y,p,cat,full,meta=self.fixture();first=r.build(x,y,p,cat,full,meta,np.arange(22));pr=r.predict_all(x,np.arange(22,30),first)
        xx=x.copy();yy=y.copy();ff=dict(full);ff['values']=full['values'].copy();xx[22:]+=101;yy[22:]-=51;ff['values'][22:]+=201
        second=r.build(xx,yy,p,cat,ff,meta,np.arange(22));again=r.predict_all(x,np.arange(22,30),second)
        np.testing.assert_array_equal(pr,again)

if __name__=='__main__':unittest.main(verbosity=2)

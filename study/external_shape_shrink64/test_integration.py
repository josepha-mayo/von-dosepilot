"""Complete 24-output synthetic wiring test, without private or NCI files."""
import unittest
from types import SimpleNamespace
import numpy as np
import run_study as r

class IntegrationTests(unittest.TestCase):
    def test_arms_replay_and_share_one_physical_plan(self):
        rng=np.random.default_rng(183);x=rng.normal(size=(30,72,2));p=np.array([f'p{i//2}' for i in range(30)])
        owner=np.repeat(np.arange(24),3);targets=np.array([f't{i}' for i in range(24)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=targets,
           native_target_indices=owner,concentrations=tuple(['1','10','100']*24))
        q=np.zeros((144,24));meta=[]
        for j in range(24):
            ix=np.arange(3*j,3*j+3);local=np.full(72,-1,int);local[ix]=np.arange(3)
            qw=np.repeat(np.array([.25,.5,.25])/2,2);q[np.arange(6*j,6*j+6),j]=qw
            meta.append({'native':ix,'quadrature':qw,'source_correlation':np.eye(3),'glob_to_local':local,'positions':np.array([0,.5,1])})
        y=x.reshape(30,-1)@q;full={'values':x.copy(),'owner':owner,'query_to_full':np.arange(72),'q':q}
        bundle=r.build(x,y,p,cat,full,meta,np.arange(22));pred=r.predict_all(x,np.arange(22,30),bundle)
        self.assertEqual(pred.shape,(3,10,2,8,24));self.assertTrue(np.isfinite(pred).all())
        self.assertEqual(len(set(bundle['plan']['selected_native_indices'])),64)
        for vi in range(3):
            state=r.g.payload(bundle,10*vi+4);state['kernel_weights']=bundle['variants'][vi]['kernel'].w.copy()
            for oi,o in enumerate(('A','B')):
                paid=r.g.acquire(x[22:],bundle['plan'],o)
                np.testing.assert_allclose(r.g.predict_payload(state,paid,o),pred[vi,4,oi],atol=1e-12,rtol=0)

if __name__=='__main__':unittest.main(verbosity=2)

import unittest
from types import SimpleNamespace
import numpy as np
import run_study as r

class WiringTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(826);x=rng.normal(size=(30,72,2));y=rng.normal(size=(30,24));p=np.array([f'p{i//2}' for i in range(30)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=np.array([f't{i}' for i in range(24)]),
            native_target_indices=np.repeat(np.arange(24),3),concentrations=tuple(['1','10','100']*24))
        prior=.3*np.ones((24,24))+.7*np.eye(24)
        return x,y,p,cat,prior
    def test_complete_variable_option_shapes_and_saved_replay(self):
        x,y,p,cat,c=self.fixture();b=r.build(x,y,p,cat,np.arange(22),c);out=r.predict_all(x,np.arange(22,30),b)
        self.assertEqual(out['operating_reproduction'].shape,(10,2,8,24));self.assertEqual(out['external_output_primary'].shape,(4,2,8,24))
        for vi,name in enumerate(r.ARMS):
            s=r.g.payload(b,10*vi+2);s['kernel_weights']=b['variants'][vi]['kernel'].w.copy()
            for oi,o in enumerate(('A','B')):
                paid=r.g.acquire(x[22:],b['plan'],o)
                np.testing.assert_allclose(r.g.predict_payload(s,paid,o),out[name][2,oi],atol=1e-12,rtol=0)
    def test_identity_output_prior_recovers_matched_control(self):
        x,y,p,cat,c=self.fixture();out=r.predict_all(x,np.arange(22,30),r.build(x,y,p,cat,np.arange(22),np.eye(24)))
        np.testing.assert_array_equal(out['external_output_primary'],out['independent_output_control'])
    def test_outer_labels_and_curve_rows_never_enter_fitting(self):
        x,y,p,cat,c=self.fixture();a=r.predict_all(x,np.arange(22,30),r.build(x,y,p,cat,np.arange(22),c))
        xx=x.copy();yy=y.copy();xx[22:]+=391;yy[22:]-=129
        b=r.predict_all(x,np.arange(22,30),r.build(xx,yy,p,cat,np.arange(22),c))
        for name in r.ARMS:np.testing.assert_array_equal(a[name],b[name])

if __name__=='__main__':unittest.main(verbosity=2)

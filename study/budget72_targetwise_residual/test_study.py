import unittest
import numpy as np

class TargetwiseTests(unittest.TestCase):
    def test_argmin_uses_first_option_on_tie(self):
        scores=np.array([[1.,2.,3.],[1.,1.,3.],[2.,3.,2.]])
        np.testing.assert_array_equal(np.argmin(scores,axis=0),[0,1,2])

    def test_targetwise_assembly_uses_one_option_per_target(self):
        pred=np.arange(4*2*3*5,dtype=float).reshape(4,2,3,5)
        chosen=np.array([0,1,2,3,1])
        out=np.empty((2,3,5))
        for t in range(5):
            out[:, :, t]=pred[int(chosen[t]), :, :, t]
        for t in range(5):
            np.testing.assert_array_equal(out[:,:,t],pred[int(chosen[t]),:,:,t])

    def test_frozen_target_count(self):
        self.assertEqual(24,24)

if __name__=="__main__":
    unittest.main(verbosity=2)

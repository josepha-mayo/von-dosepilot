import unittest
import numpy as np
from noise import contrast_transforms

class ContrastTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(311)
        reps=rng.normal(size=(18,24,2));p=np.array([f'p{i}' for i in range(18)])
        return reps,p
    def test_identity_is_exact(self):
        reps,p=self.fixture();s=contrast_transforms(reps,p)[0]
        np.testing.assert_array_equal(s['white'],np.eye(24));np.testing.assert_array_equal(s['color'],np.eye(24))
    def test_inverse_transforms(self):
        reps,p=self.fixture()
        for s in contrast_transforms(reps,p):np.testing.assert_allclose(s['white']@s['color'],np.eye(24),atol=1e-12,rtol=0)
    def test_shrinkage_bounds_small_eigenvalues(self):
        reps,p=self.fixture()
        for s in contrast_transforms(reps,p):self.assertGreaterEqual(s['min_eigenvalue'],.5-1e-12)
    def test_zero_contrast_identity_fallback(self):
        reps,p=self.fixture();reps[:,:,1]=reps[:,:,0]
        for s in contrast_transforms(reps,p):np.testing.assert_array_equal(s['white'],np.eye(24))
    def test_patient_duplicates_preserve_total_weight(self):
        reps,p=self.fixture();duplicated=np.concatenate([reps,reps[[0]]]);pp=np.concatenate((p,p[:1]))
        for a,b in zip(contrast_transforms(reps,p),contrast_transforms(duplicated,pp)):
            np.testing.assert_allclose(a['white'],b['white'],atol=1e-12,rtol=0)
    def test_nonfinite_rejected(self):
        reps,p=self.fixture();reps[0,0,0]=np.nan
        with self.assertRaises(ValueError):contrast_transforms(reps,p)
    def test_invalid_plate_dimension(self):
        reps,p=self.fixture()
        with self.assertRaises(ValueError):contrast_transforms(reps[:,:,:1],p)

if __name__=='__main__':unittest.main(verbosity=2)

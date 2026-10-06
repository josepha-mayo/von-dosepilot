import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class TransferTests(unittest.TestCase):
    def test_recipe_dimensions_and_strengths(self):
        q=np.arange(60,dtype=float).reshape(6,10)+1
        self.assertEqual(r.recipe.A_level_basis(q).shape,(6,7))
        self.assertEqual(r.recipe.B_full_quality_basis(q).shape,(6,11))
        self.assertAlmostEqual(r.A_STRENGTH,1/9)
        self.assertAlmostEqual(r.B_STRENGTH,1/3)
    def test_patient_balanced_metric(self):
        y=np.zeros((6,2))
        a=np.array([[1.,1.],[3.,3.],[2.,2.],[1.,1.],[1.,1.],[1.,1.]])
        b=a.copy()
        p=np.array(["p1","p1","p2","p3","p4","p5"])
        folds=np.array([0,0,1,2,3,4])
        m=r.metrics(y,a,b,p,folds)
        self.assertAlmostEqual(m["mse"],(5+4+1+1+1)/5)
    def test_rank1_prediction_shape(self):
        rng=np.random.default_rng(0)
        q=rng.normal(size=(12,10));res=rng.normal(size=(12,24));p=np.array([f"p{i}" for i in range(12)])
        model=r.recipe.fit_rank1(r.recipe.B_full_quality_basis(q),res,p)
        out=r.recipe.predict_rank1(r.recipe.B_full_quality_basis(q),model)
        self.assertEqual(out.shape,(12,24))
        self.assertEqual(model["rank"],1)
if __name__=="__main__":
    unittest.main(verbosity=2)

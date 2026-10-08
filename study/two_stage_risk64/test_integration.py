import unittest
import numpy as np
import test_study as fixtures
import run_study as r

class OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.PipelineTests.setUpClass();cls.bank=fixtures.PipelineTests.bank;cls.query=fixtures.PipelineTests.full[16:].copy()
    def test_complete_staged_query_and_poison_replay(self):
        predictions,trace,stats,error=r.apply(self.bank,self.query)
        self.assertEqual(set(predictions),set(r.ARMS));self.assertEqual(error,0.)
        for a in predictions:self.assertEqual(predictions[a].shape,(2,6,24))
        for name in ('static','adaptive'):
            for seed in (0,1):
                cells=trace[f'{name}_s{seed}_physical_cells'];self.assertEqual(cells.shape,(6,64,2))
                self.assertTrue(np.all(np.sum(cells[:,:,1]==0,axis=1)==32))
    def test_oracle_repeated_first_round_rejected(self):
        oracle=r.PaidOracle(self.query);oracle.initial(self.bank,0)
        with self.assertRaises(ValueError):oracle.initial(self.bank,0)
    def test_oracle_followup_without_initial_rejected(self):
        oracle=r.PaidOracle(self.query)
        with self.assertRaises(ValueError):oracle.followup(self.bank,np.ones((6,24),int),0)
    def test_oracle_second_followup_rejected(self):
        oracle=r.PaidOracle(self.query);initial=oracle.initial(self.bank,0);actions,_=r.policy.choose_actions(self.bank,initial,0)
        oracle.followup(self.bank,actions,0)
        with self.assertRaises(ValueError):oracle.followup(self.bank,actions,0)

if __name__=='__main__':unittest.main(verbosity=2)

import copy,json,unittest
import test_recover_baseline as fixtures
from complete_recovery import complete

class Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Tests('test_record_order');self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def run_complete(self,observations):
        f=self.f;path=f.d/'complete.json';path.write_text(json.dumps(observations))
        return complete(f.modeldir,f.anchor,f.commitment_path,path,f.d/'primary.json',f.ledger)
    def test_guarded_completion_matches_primary(self):
        f=self.f;f.call(f.partial());got=self.run_complete(f.complete)
        self.assertEqual(len(got['predictions']),24)
        self.assertEqual(got['predictions'],f.model.predict(f.request)['predictions'])
        self.assertEqual(len(list(f.ledger.glob('*.recovery_completion.json'))),1)
        self.assertEqual(got,self.run_complete(f.complete))
    def test_completed_values_cannot_rewrite_prior_observations(self):
        f=self.f;f.call(f.partial());changed=copy.deepcopy(f.complete)
        changed['measurements'][1]['value']+=.01
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CHANGED'):self.run_complete(changed)
        self.assertFalse((f.d/'primary.json').exists())
        self.assertFalse(list(f.ledger.glob('*.prediction.json')))
    def test_requires_existing_recovery_history(self):
        with self.assertRaisesRegex(ValueError,'NO_RECOVERY_HISTORY'):self.run_complete(self.f.complete)
if __name__=='__main__':unittest.main(verbosity=2)

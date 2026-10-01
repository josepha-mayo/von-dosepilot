import unittest
import numpy as np
from verify_protected22 import analyze, validate

def fixture(patients=('a','a','b'),targets=2):
 n=len(patients)
 a={'samples':np.array([f's{i}' for i in range(n)]),'patients':np.array(patients),'targets':np.array([f'd{j}' for j in range(targets)]),'y':np.zeros((n,targets))}
 for key in ('candidate_A','candidate_B'):a[key]=np.ones((n,targets))
 for key in ('comparator_A','comparator_B'):a[key]=np.full((n,targets),2.)
 return a
class Tests(unittest.TestCase):
 def test_equal_patients_not_equal_samples(self):
  a=fixture();a['candidate_A'][:2]=0;a['candidate_B'][:2]=0;a['candidate_A'][2]=2;a['candidate_B'][2]=2
  self.assertEqual(analyze(a)['primary']['candidate_mse'],2.)
 def test_losses_not_prediction_average(self):
  a=fixture();a['candidate_B'][:]=-1
  self.assertEqual(analyze(a)['primary']['candidate_mse'],1.)
 def test_missing_one_sample_removes_whole_patient_only_from_conditional(self):
  a=fixture();a['y'][0,0]=np.nan;r=analyze(a)
  self.assertIsNone(r['primary']);self.assertEqual(r['original_pdos'],3);self.assertEqual(r['original_patients'],2)
  self.assertEqual(r['complete_pdos'],2);self.assertEqual(r['pdos_in_complete_patients'],1)
  self.assertEqual(r['complete_patients'],1)
 def test_targetwise_support_not_primary_rescue(self):
  a=fixture();a['y'][0,0]=np.nan;r=analyze(a)
  self.assertEqual([x['complete_patients'] for x in r['per_target_conditional']],[1,2]);self.assertFalse(r['full_primary_estimable'])
 def test_missing_comparator_alternative_counts_as_incomplete(self):
  a=fixture();a['comparator_B'][0,0]=np.nan;self.assertFalse(analyze(a)['full_primary_estimable'])
 def test_no_complete_patient_has_no_conditional_estimate(self):
  a=fixture();a['y'][:,0]=np.nan;r=analyze(a);self.assertIsNone(r['complete_patient_conditional'])
 def test_duplicate_ids_rejected(self):
  a=fixture();a['samples'][1]=a['samples'][0]
  with self.assertRaises(ValueError):validate(a)
 def test_infinity_rejected(self):
  a=fixture();a['candidate_A'][0,0]=np.inf
  with self.assertRaises(ValueError):validate(a)
if __name__=='__main__':unittest.main(verbosity=2)

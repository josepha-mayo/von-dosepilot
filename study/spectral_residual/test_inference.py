import copy,json,hashlib,tempfile,unittest
from pathlib import Path
import numpy as np
from inference import SpectralModel

def fixture():
    rng=np.random.default_rng(10192)
    owner=np.repeat(np.arange(24),[3]*16+[2]*8)
    plates=[]
    for j in range(24):plates.extend((j%2+np.arange(3 if j<16 else 2))%2)
    ids=[f'q{i:02}' for i in range(64)];targets=[f'd{j:02}' for j in range(24)]
    mask=np.equal(np.arange(24)[:,None],owner[None,:]);beta=rng.normal(size=(64,24))*mask.T
    a=dict(mean_x=rng.normal(size=64),scale_x=np.ones(64),mean_y=rng.normal(size=24),beta=beta,correction=rng.normal(size=(64,24))*.01,feature_mask=mask,native_ids=np.array(ids),drug_ids=np.array(targets),plate_A=np.array(plates),plate_B=1-np.array(plates))
    doses=[str(1+int(i)) for i in range(64)]
    plan=dict(selected_native_ids=ids,coordinate_target_indices=owner.tolist(),selected_concentrations_nM=doses,orientation_A_plate_indices=list(map(int,plates)),orientation_B_plate_indices=list(map(int,1-np.array(plates))))
    values=rng.normal(size=64)
    r=dict(sample_id='fictional',run_id='run1',orientation='A',measurements=[dict(sample_id='fictional',run_id='run1',native_id=ids[i],drug_id=targets[owner[i]],dose_nM=doses[i],plate='p'+str(plates[i]+1),well_id=f'w{i:02}',value=float(values[i])) for i in range(64)])
    return a,plan,r,values
class Tests(unittest.TestCase):
    def setUp(self):self.a,self.plan,self.r,self.values=fixture();self.m=SpectralModel(self.a,self.plan)
    def test_direct_arithmetic(self):
        got=np.array(list(self.m.predict(self.r)['predictions'].values()));z=self.values-self.a['mean_x']
        np.testing.assert_allclose(got,self.a['mean_y']+z@self.a['beta']+z@self.a['correction'],atol=1e-14)
    def test_order_invariant(self):
        r=copy.deepcopy(self.r);r['measurements'].reverse();self.assertEqual(self.m.predict(r),self.m.predict(self.r))
    def test_one_missing_withholds(self):
        r=copy.deepcopy(self.r);r['measurements'][0]['value']=None
        with self.assertRaises(ValueError):self.m.predict(r)
    def test_missing_row_withholds(self):
        r=copy.deepcopy(self.r);r['measurements'].pop()
        with self.assertRaises(ValueError):self.m.predict(r)
    def test_extra_row_rejected(self):
        r=copy.deepcopy(self.r);r['measurements'].append(r['measurements'][0])
        with self.assertRaises(ValueError):self.m.predict(r)
    def test_duplicate_native(self):
        r=copy.deepcopy(self.r);r['measurements'][1]=copy.deepcopy(r['measurements'][0])
        with self.assertRaises(ValueError):self.m.predict(r)
    def test_wrong_plate_or_dose_or_drug(self):
        for key,value in [('plate','p2'),('dose_nM','1.0000000000001'),('drug_id','wrong')]:
            r=copy.deepcopy(self.r);r['measurements'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.m.predict(r)
    def test_mixed_sample_run(self):
        for key in ('sample_id','run_id'):
            r=copy.deepcopy(self.r);r['measurements'][0][key]='wrong'
            with self.subTest(key=key),self.assertRaises(ValueError):self.m.predict(r)
    def test_nonfinite_or_bool(self):
        for value in [float('nan'),float('inf'),True]:
            r=copy.deepcopy(self.r);r['measurements'][0]['value']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.m.predict(r)
    def test_construction_digest(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);np.savez_compressed(d/'model_private.npz',**self.a);(d/'plan.json').write_text(json.dumps(self.plan))
            receipt={'selected':[.1,1.],'model_sha256':hashlib.sha256((d/'model_private.npz').read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256((d/'plan.json').read_bytes()).hexdigest()}
            (d/'CONSTRUCTION.json').write_text(json.dumps(receipt));self.assertEqual(SpectralModel.load(d).predict(self.r),self.m.predict(self.r))
            (d/'plan.json').write_text('{}')
            with self.assertRaises(ValueError):SpectralModel.load(d)
    def test_bad_scale(self):
        a=copy.deepcopy(self.a);a['scale_x'][0]=0
        with self.assertRaises(ValueError):SpectralModel(a,self.plan)
    def test_wrong_native_order(self):
        a=copy.deepcopy(self.a);a['native_ids']=a['native_ids'][::-1]
        with self.assertRaises(ValueError):SpectralModel(a,self.plan)
if __name__=='__main__':unittest.main(verbosity=2)

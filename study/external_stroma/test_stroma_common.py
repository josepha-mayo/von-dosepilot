import hashlib,tempfile,unittest
from pathlib import Path
import numpy as np
import stroma_common as s

def fixture_bytes(dev=True,confirmation=False,canary=False):
    rows=['No.\tOrganoid ID\tMono-/Coculture\tFibroblast ID\tDrug\tConcentration\tReplicate\tRLU value\tUsed value/comment\t\t']
    n=0
    scopes=[]
    if dev:scopes += [(o,'Monoculture','') for o in s.DEV_IDS]
    if confirmation:
        for o,f in s.CONFIRM_PAIRS:scopes += [(o,'Coculture',f),(o,'Monoculture','')]
    for o,ctx,fib in scopes:
        for j,d in enumerate(s.DRUGS):
            labels=('DMSO',)+s.DOSE_LABELS[d]
            for k,label in enumerate(labels):
                for rep in ('1','2'):
                    n+=1;value=100. if label=='DMSO' else 50.+j+k
                    rows.append(f'{n}\t{o}\t{ctx}\t{fib}\t{d}\t{label}\t{rep}\t{value}\t\t\t')
    if canary:
        n+=1;rows.append(f'{n}\tO01\tCoculture\tF01\t5-FU\t0.5\t1\tSECRET_RLU\t\t\t')
    return ('\n'.join(rows)+'\n').encode()

class Tests(unittest.TestCase):
    def pinned(self,raw,scope):
        old=s.SOURCE_SHA
        try:
            s.SOURCE_SHA=hashlib.sha256(raw).hexdigest()
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'x.txt';p.write_bytes(raw)
                return s.load_scope(p,scope)
        finally:s.SOURCE_SHA=old

    def test_constant_auc(self):
        v=np.ones((3,4,7));np.testing.assert_allclose(s.auc_full(v),1)

    def test_loglinear_auc(self):
        v=np.stack([2+3*np.log(s.DOSES[j]) for j in range(4)])[None]
        expected=np.array([2+1.5*(np.log(x[0])+np.log(x[-1]))*2 for x in s.DOSES])
        # integral average of a+b log(d) is a+b*(loglo+loghi)/2
        expected=np.array([2+3*(np.log(x[0])+np.log(x[-1]))/2 for x in s.DOSES])
        np.testing.assert_allclose(s.auc_full(v)[0],expected,rtol=0,atol=1e-13)

    def test_parser_normalizes(self):
        data,audit=self.pinned(fixture_bytes(dev=True),'development')
        self.assertEqual(data['values']['mono'].shape,(13,4,7))
        self.assertTrue((data['values']['mono']<1).all())
        self.assertEqual(audit['invalid_or_nonfinite_rlu'],0)

    def test_dev_parser_ignores_confirmation_canary(self):
        data,audit=self.pinned(fixture_bytes(dev=True,canary=True),'development')
        self.assertEqual(audit['invalid_or_nonfinite_rlu'],0)
        self.assertEqual(len(data['ids']),13)

    def test_confirmation_complete(self):
        data,audit=self.pinned(fixture_bytes(dev=False,confirmation=True),'confirmation')
        self.assertEqual(data['values']['co'].shape,(15,4,7))
        self.assertEqual(data['values']['mono'].shape,(15,4,7))

    def test_confirmation_incomplete_fails(self):
        with self.assertRaises(ValueError):self.pinned(fixture_bytes(dev=True),'confirmation')

    def test_learned_plan_budget(self):
        rng=np.random.default_rng(3);v=rng.uniform(.2,1.2,(13,4,7));y=s.auc_full(v)
        p=s.learned_plan(v,y)
        self.assertEqual(len(p['selected']),11);self.assertEqual(len(p['upgraded']),3)
        self.assertEqual(sorted(np.bincount(p['owner'])),[2,3,3,3])

    def test_interp_plan_budget(self):
        rng=np.random.default_rng(4);v=rng.uniform(.2,1.2,(13,4,7));y=s.auc_full(v)
        p=s.interp_plan(v,y)
        self.assertEqual(sum(3 if d in p['upgraded'] else 2 for d in s.DRUGS),11)

    def test_own_drug_beta(self):
        rng=np.random.default_rng(5);v=rng.normal(size=(13,4,7));y=rng.normal(size=(13,4))
        p=s.learned_plan(v,y);m=s.fit_model(v,y,p,.1)
        owner=np.asarray(p['owner'])
        for j in range(4):self.assertTrue((m['beta'][owner!=j,j]==0).all())

    def test_unpaid_nan_invariance(self):
        rng=np.random.default_rng(6);v=rng.uniform(.2,1.2,(13,4,7));y=s.auc_full(v)
        p=s.learned_plan(v,y);m=s.fit_model(v,y,p,.1);a=s.predict_model(v,p,m)
        selected={tuple(x) for x in p['selected']};masked=v.copy()
        for j in range(4):
            for k in range(7):
                if (j,k) not in selected:masked[:,j,k]=np.nan
        np.testing.assert_array_equal(a,s.predict_model(masked,p,m))

    def test_scale_floor(self):
        c=s.context(np.ones((5,2)),np.ones((5,1)));np.testing.assert_array_equal(c['sx'],[.05,.05])

    def test_source_pin(self):
        raw=fixture_bytes(dev=True)
        old=s.SOURCE_SHA
        try:
            s.SOURCE_SHA='0'*64
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'x';p.write_bytes(raw)
                with self.assertRaises(ValueError):s.load_scope(p,'development')
        finally:s.SOURCE_SHA=old

if __name__=='__main__':unittest.main(verbosity=2)

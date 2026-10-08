"""Synthetic teacher/student separation and 64-input inference tests."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json
import numpy as np
import privileged_student64 as s
from coverage_methods import CoverageCatalog

def main():
    rng=np.random.default_rng(2026100816);n=18;owner=np.repeat(np.arange(24),7);N=len(owner)
    doses=tuple(str(v) for v in np.tile([1,3,10,30,100,300,1000],24))
    cat=CoverageCatalog(np.array([f'q{i}' for i in range(N)]),np.array([f't{i}' for i in range(24)]),owner,doses,'lib1')
    p=np.repeat([f'Pt{i}' for i in range(9)],2);x=rng.normal(size=(n,N,2));y=np.stack([x[:,owner==j].mean(axis=(1,2)) for j in range(24)],axis=1)
    students,receipts=s.fit_students(x,y,p,cat)
    label_groups=[]
    for r in receipts:
        assert not set(r['fit_patients'])&set(r['soft_label_patients'])
        label_groups+=r['soft_label_patients']
    assert sorted(label_groups)==sorted(set(p))
    original=s.m.fit_models(x,y,p,cat)[64]
    assert np.max(abs(s.m.predict_options(x,students['raw'])-s.m.predict_options(x,original)))<1e-12
    maximum=0.
    for name,student in students.items():
        plan=student[0];assert plan['treatment_wells']==64
        state=s.m.payload(student,2);pred=s.m.predict_options(x,student)[2]
        for oi,o in enumerate(('A','B')):
            paid=s.m.paid(x,plan,o);restored=s.m.replay(state,paid)
            maximum=max(maximum,float(np.max(abs(restored-pred[oi]))))
            masked=np.full_like(x,np.nan);masked[:,state['native'],state['plate_'+o]]=paid
            assert np.array_equal(paid,s.m.paid(masked,plan,o))
            assert np.array_equal(restored,s.m.replay(state,s.m.paid(masked,plan,o)))
        try:s.m.replay(state,np.zeros((1,128)))
        except ValueError:pass
        else:raise AssertionError('student accepted teacher inputs')
    assert maximum<1e-12
    print(json.dumps({'status':'PASS','synthetic_only':True,'checks':['whole_patient_teacher_exclusion','one_crossfit_label_per_patient','alpha0_reproduces_original','64_well_student_budget','numeric_model_replay','unpaid_input_invariance','teacher_features_rejected_at_inference'],'max_replay_difference':maximum}),flush=True)
if __name__=='__main__':main()

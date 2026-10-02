#!/usr/bin/env python3
"""Run a fully fictional missing-reading recovery demonstration, without data downloads."""
from pathlib import Path
import argparse,copy,json,shutil
from test_recover_baseline import Tests
from recover_baseline import recover


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():p.error('Output already exists; preserve it and choose a new directory')
    # Reuse the public, seeded fictional fixture. No biological model is loaded.
    fixture=Tests('test_record_order');fixture.setUp()
    try:
        shutil.copytree(fixture.d,a.output)
        model=a.output/'model';ledger=a.output/'ledger';commitment=a.output/'commitment.json'
        partial=copy.deepcopy(fixture.complete);partial['measurements'][0]['value']=None
        observations=a.output/'one_missing.json';observations.write_text(json.dumps(partial,indent=2))
        strict_rejected=False
        try:fixture.w.predict(model,fixture.anchor,commitment,observations,a.output/'strict.json',ledger)
        except ValueError:strict_rejected=True
        if not strict_rejected:raise RuntimeError('Incomplete primary unexpectedly ran')
        report=recover(model,fixture.anchor,commitment,observations,a.output/'baseline_only.json',ledger,True)
        if len(report['baseline_predictions'])!=23 or report['primary_predictions']!={}:raise RuntimeError('Bad demo output')
        summary={'fixture':'FICTIONAL, SEEDED, NOT BIOLOGICAL DATA','strict_primary_rejected_missing':strict_rejected,
            'primary_predictions':0,'explicit_older_baseline_predictions':23,'affected_target_withheld':fixture.model.targets[0],
            'no_imputation':not report['missing_values_imputed'],'committed_wells':64,
            'new_accuracy_claim':False,'clinical_use_validated':False}
        (a.output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
        (a.output/'FICTIONAL_DATA_NOTICE.txt').write_text('All values and model parameters in this folder are seeded fictional fixtures. These results are a software demonstration, not a drug-response experiment.\n')
        print(json.dumps(summary,indent=2))
    finally:fixture.tearDown()
if __name__=='__main__':main()

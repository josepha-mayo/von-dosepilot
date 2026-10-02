#!/usr/bin/env python3
"""Exercise the complete public lifecycle CLI using only fictional data.

No private model, patient data, network download or model API is required.
The generated files demonstrate behavior, not predictive or clinical accuracy.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'hybrid_residual')]
import lifecycle
import test_recover_baseline as fixtures


def run(out):
    if out.exists():raise ValueError('Output already exists; choose a fresh directory')
    f=fixtures.Tests('test_record_order');f.setUp()
    try:
        out.mkdir(parents=True,exist_ok=False)
        shutil.copytree(f.modeldir,out/'model')
        shutil.copy2(f.d/'inventory.json',out/'inventory.json')
        ledger=out/'ledger';ledger.mkdir()
        common=['--model-dir',str(out/'model'),'--construction-sha256',f.anchor,
                '--ledger-dir',str(ledger),'--commitment',str(out/'commitment.json')]
        environment=os.environ.copy()
        for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):environment[k]='1'
        events=[]
        def cli(command,args,expected_code):
            cmd=[sys.executable,str(HERE/'lifecycle.py'),command,*common,*args]
            process=subprocess.run(cmd,env=environment,capture_output=True,text=True,timeout=30)
            text=process.stdout.strip() if expected_code==0 else process.stderr.strip()
            if process.returncode!=expected_code:raise RuntimeError('Demo command failed: '+process.stderr)
            result=json.loads(text)
            events.append({'command':command,'expected_exit':expected_code,'actual_exit':process.returncode,'result':result})
            return result
        cli('commit',['--inventory',str(out/'inventory.json'),'--template',str(out/'template.json')],0)
        complete=json.loads((out/'template.json').read_text())
        for row,value in zip(complete['measurements'],f.values):row['value']=float(value)
        missing=copy.deepcopy(complete);missing['measurements'][0]['value']=None
        (out/'missing.json').write_text(json.dumps(missing,indent=2)+'\n')
        cli('predict',['--measurements',str(out/'missing.json'),'--output',str(out/'rejected.json')],2)
        recovered=cli('recover',['--measurements',str(out/'missing.json'),'--output',str(out/'baseline.json'),'--acknowledge-baseline-only'],0)
        assert recovered['baseline_outputs']==23 and recovered['primary_outputs']==0
        changed=copy.deepcopy(complete);changed['measurements'][1]['value']+=.01
        (out/'changed.json').write_text(json.dumps(changed,indent=2)+'\n')
        rejected=cli('predict',['--measurements',str(out/'changed.json'),'--output',str(out/'forbidden.json')],2)
        assert 'OBSERVATION_CHANGED' in rejected['reason']
        (out/'complete.json').write_text(json.dumps(complete,indent=2)+'\n')
        result=cli('predict',['--measurements',str(out/'complete.json'),'--output',str(out/'primary.json')],0)
        assert result['primary_outputs']==24
        before=(out/'primary.json').read_bytes();(out/'primary.json').unlink()
        cli('predict',['--measurements',str(out/'complete.json'),'--output',str(out/'primary.json')],0)
        assert (out/'primary.json').read_bytes()==before
        summary={'status':'PASS','data':'ALL FICTIONAL; NO BIOLOGICAL VALIDATION',
            'lifecycle_policy':lifecycle.POLICY,'cli_invocations':len(events),
            'missing_primary_rejected':True,'explicit_baseline_outputs':23,
            'changed_old_reading_rejected_automatically':True,'complete_primary_outputs':24,
            'lost_export_recovered_identically':True,'private_data_downloaded':False,
            'clinical_use_validated':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
        (out/'CLI_TRANSCRIPT.json').write_text(json.dumps(events,indent=2)+'\n')
        (out/'FICTIONAL_DATA_NOTICE.txt').write_text('All model parameters and input values in this directory are seeded fictional fixtures. This is a software demonstration, not a biological experiment.\n')
        print(json.dumps(summary,indent=2))
    finally:f.tearDown()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())

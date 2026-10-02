#!/usr/bin/env python3
"""Explicit baseline recovery and guarded completion on the durable runtime.

The baseline values remain the older own-drug component, never incomplete
additive predictions. Existing original-runtime ledgers are not migrated.
"""
from pathlib import Path
import argparse,importlib.util,json,sys
from durable_workflow import load_backend


def module(name):
    path=Path(__file__).resolve().parents[1]/'hybrid_residual'/name
    spec=importlib.util.spec_from_file_location('_durable_'+path.stem,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    value.load_backend=load_backend
    return value


def recover(*args,**kwargs):return module('recover_baseline.py').recover(*args,**kwargs)
def complete(*args,**kwargs):return module('complete_recovery.py').complete(*args,**kwargs)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['baseline','complete'])
    for n in ('model-dir','commitment','measurements','output','ledger-dir'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--construction-sha256',required=True);p.add_argument('--acknowledge-baseline-only',action='store_true');a=p.parse_args()
    try:
        args=(a.model_dir,a.construction_sha256,a.commitment,a.measurements,a.output,a.ledger_dir)
        if a.mode=='baseline':
            r=recover(*args,acknowledge_baseline_only=a.acknowledge_baseline_only)
            result={'status':r['status'],'primary_outputs':0,'baseline_outputs':len(r['baseline_predictions'])}
        else:
            r=complete(*args);result={'status':r['status'],'primary_outputs':len(r['predictions']),'prior_observations_verified':True}
        print(json.dumps(result));return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({'status':'REJECTED','reason':str(exc)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

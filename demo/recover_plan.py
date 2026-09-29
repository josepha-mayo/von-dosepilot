#!/usr/bin/env python3
"""Recover the exact already-committed DosePilot plan into a fresh folder.

This does not allocate another layout, reset a ledger, or infer new measurements.
The original R21 predictor and model are not modified. All example data in the
synthetic package are fictional.
"""
from pathlib import Path
import argparse,json,sys
import dosepilot as core

def recover(model_path,model_sha256,ledger,sample_id,run_id,output):
 core.identity(sample_id,'sample');core.identity(run_id,'run')
 model,params,mhash=core.load_model(model_path,model_sha256)
 root=Path(ledger);out=Path(output)
 if not root.is_dir() or root.is_symlink():raise core.ContractError('LEDGER_DIRECTORY_REQUIRED')
 key=core.ledger_key({'model_sha256':mhash,'library_id':'lib1','sample_id':sample_id,'run_id':run_id})
 entry=root/key
 if not entry.is_file() or entry.is_symlink():raise core.ContractError('PLAN_NOT_COMMITTED')
 plan,raw=core.load(entry)  # one captured commitment snapshot
 core.verify_plan(model,mhash,plan)
 if (plan['sample_id'],plan['run_id'],plan['model_sha256'])!=(sample_id,run_id,mhash):
  raise core.ContractError('COMMITMENT_FRAME_MISMATCH')
 out.mkdir(parents=True,exist_ok=False)
 try:
  core.write_new(out/'plan.json',plan)
  core.write_new(out/'measurement_template.json',core.request_template(plan))
  receipt={'status':'RECOVERED_EXISTING_COMMITMENT','model_sha256':mhash,
   'source_commit_sha256':core.raw_hash(raw),'plan_sha256':core.raw_hash(core.canonical(plan)),
   'orientation':plan['orientation'],'allocation_nonce':plan['allocation_nonce'],
   'new_plan_selected':False,'ledger_modified':False,'new_measurement_access':False,
   'sample_id':sample_id,'run_id':run_id}
  core.write_new(out/'RECOVERY_RECEIPT.json',receipt)
 except Exception as e:
  core.write_new(out/'RECOVERY_FAILURE.json',{'status':'INCOMPLETE_EXPORT','error':str(e),
    'original_commitment_modified':False,'automatic_retry':False})
  raise
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['model','model-sha256','ledger','sample-id','run-id','output']:
  p.add_argument('--'+name,required=True)
 a=p.parse_args()
 try:
  result=recover(a.model,a.model_sha256,a.ledger,a.sample_id,a.run_id,a.output)
  print(json.dumps(result,sort_keys=True));return 0
 except (ValueError,OSError,KeyError,TypeError) as e:
  print(json.dumps({'status':'REJECTED','reason':str(e)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

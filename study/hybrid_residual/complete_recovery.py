#!/usr/bin/env python3
"""Complete a recovered frame without rewriting its recorded observations.

Use this wrapper after explicit baseline recovery. It delegates the actual
complete-input prediction to the unchanged additive operating backend.
"""
from pathlib import Path
import argparse,json,sys
from additive_inference import AdditiveModel
from additive_workflow import load_backend


def complete(model_dir,anchor,commitment_path,measurements_path,output_path,ledger_dir):
    w=load_backend();receipt=w.model_receipt(model_dir,anchor);model=AdditiveModel.load(model_dir)
    commitment,_=w.load_json(commitment_path);w.validate_commitment(model,receipt,commitment)
    measurements,_=w.load_json(measurements_path)
    request=w.request_from_measurements(model,commitment,measurements)
    current={row['native_id']:w.sha256_bytes(w.canonical(float(row['value']))) for row in request['measurements']}
    prefix=commitment['frame_id']+'.baseline_recovery.';records=[]
    for path in sorted(Path(ledger_dir).glob(prefix+'*.json')):
        if path.is_symlink():raise w.WorkflowError('SYMLINK_RECOVERY_LEDGER_REJECTED')
        old,_=w.load_json(path)
        body={k:v for k,v in old.items() if k!='recovery_id'};expected=w.sha256_bytes(w.canonical(body))
        if old.get('recovery_id')!=expected or path.name!=prefix+expected+'.json':
            raise w.WorkflowError('RECOVERY_LEDGER_DIGEST_MISMATCH')
        if old.get('evidence',{}).get('commitment_id')!=commitment['commitment_id']:
            raise w.WorkflowError('RECOVERY_FRAME_MISMATCH')
        if any(current.get(native)!=fingerprint for native,fingerprint in old['observed_value_hashes'].items()):
            raise w.WorkflowError('PREVIOUS_OBSERVATION_CHANGED_OR_REMOVED')
        records.append(expected)
    if not records:raise w.WorkflowError('NO_RECOVERY_HISTORY_USE_ORDINARY_PRIMARY_WORKFLOW')
    guard_path=w.ledger_path(ledger_dir,commitment['frame_id'],'.recovery_completion.json')
    guard={'schema':'dosepilot.recovery_completion_guard.v1','commitment_id':commitment['commitment_id'],
           'construction_sha256':anchor,'measurements_sha256':w.digest(measurements_path),
           'verified_recovery_records':records,'guard_code_sha256':w.digest(Path(__file__))}
    if Path(output_path).resolve()==guard_path.resolve():raise w.WorkflowError('COMPLETION_OUTPUT_COLLISION')
    if guard_path.exists():
        previous,_=w.load_json(guard_path)
        if previous!=guard:raise w.WorkflowError('COMPLETION_GUARD_MISMATCH')
    result=w.predict(model_dir,anchor,commitment_path,measurements_path,output_path,ledger_dir)
    if not guard_path.exists():w.write_new(guard_path,guard)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('model-dir','commitment','measurements','output','ledger-dir'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--construction-sha256',required=True);a=p.parse_args()
    try:
        r=complete(a.model_dir,a.construction_sha256,a.commitment,a.measurements,a.output,a.ledger_dir)
        print(json.dumps({'status':r['status'],'primary_outputs':len(r['predictions']),'recovery_history_verified':True}));return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({'status':'REJECTED','reason':str(exc)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

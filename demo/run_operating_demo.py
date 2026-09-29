#!/usr/bin/env python3
"""Replay the recorded synthetic workflow without its video reading pauses."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    if out.exists():p.error('Use a new output directory; existing records are never overwritten.')
    here=Path(__file__).resolve().parent;records=[];begin=time.perf_counter()
    for step in ['prepare','plan','predict','missing','reject','recover','evidence']:
        print('\n=== '+step.upper()+' ===',flush=True)
        cmd=[sys.executable,'-B',str(here/'demo_steps.py'),step,'--output',str(out)]
        r=subprocess.run(cmd,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=60)
        records.append({'step':step,'returncode':r.returncode})
        if r.returncode:raise RuntimeError('Demo stopped at '+step+'; outputs retained.')
    summary={'status':'passed','steps':records,'elapsed_seconds':time.perf_counter()-begin,
             'synthetic_inputs_and_parameters':True,'biological_fit':False,'new_accuracy_evaluation':False}
    (out/'REPLAY_RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('\nRecorded synthetic workflow replay completed. No biological result was re-evaluated.')
if __name__=='__main__':main()

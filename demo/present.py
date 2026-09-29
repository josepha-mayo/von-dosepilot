#!/usr/bin/env python3
"""Scripted terminal presenter. Runs real synthetic CLI commands, with reading pauses.

The accompanying video records this actual X11 terminal. No fake live LLM activity,
post-hoc output substitutions, or scientific fitting occurs here.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
P=Path(__file__).resolve().parent
B='\033[1m'; CY='\033[38;2;85;215;210m'; W='\033[38;2;238;242;249m'; G='\033[38;2;184;197;215m';R='\033[0m'

def say(s=''): print(s,flush=True)
def screen(chapter, title):
    say('\033[2J\033[H'+CY+B+'von / DosePilot'+R+'  |  '+chapter)
    say(G+'SCRIPTED TERMINAL CAPTURE  |  INVENTED INPUTS + MODEL  |  PRIVATE CANDIDATE'+R)
    say('─'*102);say(B+W+title+R);say()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--timeline',type=Path,required=True)
    ap.add_argument('--pause-scale',type=float,default=1.0);a=ap.parse_args(); start=time.monotonic();timeline=[]
    def wait(n): time.sleep(n*a.pause_scale)
    def step(chapter,title,cmd,notes,hold):
        screen(chapter,title);t=time.monotonic()-start
        say(CY+'$ python demo_steps.py '+cmd+' --output session'+R);wait(2)
        argv=[sys.executable,'-B',str(P/'demo_steps.py'),cmd,'--output',str(a.output)]
        r=subprocess.run(argv,text=True,capture_output=True,timeout=60,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        say(r.stdout.rstrip());
        if r.stderr:say(r.stderr.rstrip())
        if r.returncode:raise RuntimeError('Capture command failed: '+cmd)
        for n in notes:say(G+n+R)
        timeline.append({'chapter':chapter,'title':title,'start_seconds':t,'command':argv,'exit':r.returncode})
        a.timeline.write_text(json.dumps(timeline,indent=2)+'\n');wait(hold)
    screen('00 / WHY','Which measurements can a fixed budget support?')
    say('A researcher has a plate inventory and a treatment-well budget.')
    say('DosePilot binds a supported plan to exact drug, dose, plate and run identities.')
    say('It predicts response summaries and makes unsupported requests explicit.')
    say();say('This recording shows real execution on wholly fictional inputs.')
    say('It is not a wet-lab experiment, biological accuracy test, or live AI session.')
    say();say('Operation first. Recorded research evidence follows, with its limitations.')
    wait(12)
    step('01 / INVENTORY','Verify the input frame before accepting measurements','prepare',[],12)
    step('02 / COMMIT','Commit one 64-well plan before reading responses','plan',[],16)
    step('03 / PREDICT','64 identified values produce 24 response summaries','predict',[],22)
    step('04 / ABSTAIN','One missing value must remain visible','missing',[],18)
    step('05 / REJECT','Do not turn an incompatible experiment into a prediction','reject',[],17)
    step('06 / RECOVER','An export failure must not buy a new layout','recover',[],23)
    step('07 / EVIDENCE','What the retrospective results actually support','evidence',[],23)
    screen('08 / BOUNDARIES','An inspectable workflow, not a claim of clinical validation')
    say('The retained model supports its specified inventory and endpoint.')
    say('It does not optimize arbitrary budgets or certify that laboratory work occurred.')
    say('Cross-library 64-well full-target transfer remains unresolved.')
    say('The first independent evaluation failed before scoring; protected patients stay closed.')
    say();say('Included: exact commands, inputs, result records, timings and hashes.')
    say('Technical report: 19 pages covering methods, regressions, reproduction and limits.')
    say();say(CY+'NEXT RELEASE GATES'+R)
    say('Source permissions and original-source reproduction; public artifact review;')
    say('registration / ownership decisions; final accessible Writeup, code and video.')
    say();say('Private video candidate. No submission or publication in this recording.')
    timeline.append({'chapter':'08 / BOUNDARIES','start_seconds':time.monotonic()-start})
    wait(17)
    a.timeline.write_text(json.dumps(timeline,indent=2)+'\n')
    done={'status':'completed','elapsed_seconds':time.monotonic()-start,'commands':7,
          'scope':'SYNTHETIC SCRIPTED TERMINAL RECORDING','biological_model_fit':False}
    (a.output/'PRESENTATION_COMPLETED.json').write_text(json.dumps(done,indent=2)+'\n')
    wait(2)
if __name__=='__main__':main()

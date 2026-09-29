#!/usr/bin/env python3
"""Execute one invented recovery scenario. No training or network access."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path

def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 here=Path(__file__).resolve().parent;out=a.output.resolve()
 manifest=json.loads((here/'PACKAGE_MANIFEST.json').read_text())
 for name,r in manifest['files'].items():
  raw=(here/name).read_bytes()
  if len(raw)!=r['bytes'] or digest(raw)!=r['sha256']:raise ValueError('Package bytes changed: '+name)
 out.mkdir(parents=True,exist_ok=False);ledger=out/'ledger';ledger.mkdir()
 model=here/'model.json';mh=manifest['files']['model.json']['sha256'];inv=json.loads((here/'inventory.json').read_text())
 common=['--model',str(model),'--model-sha256',mh,'--ledger',str(ledger)];records=[]
 def call(label,program,args,expected):
  command=[sys.executable,'-B',str(here/program),*args];t=time.perf_counter()
  r=subprocess.run(command,capture_output=True,text=True,timeout=30)
  records.append({'label':label,'command':command,'seconds':time.perf_counter()-t,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  (out/'COMMANDS.json').write_text(json.dumps(records,indent=2)+'\n')
  if r.returncode!=expected:raise RuntimeError(label+': unexpected return code '+str(r.returncode))
  return r
 call('intentional export failure','dosepilot.py',['plan',*common,'--inventory',str(here/'inventory.json'),'--budget','64','--nonce',manifest['demo_nonce'],'--output',str(out/'absent_directory'/'plan.json'),'--template',str(out/'unused_template.json')],2)
 entries=list(ledger.glob('*.json'));assert len(entries)==1
 before=entries[0].read_bytes();plan=json.loads(before)
 print('1/4  Deliberate output failure: rejected; one valid commitment retained.')
 call('recover original commitment','recover_plan.py',[*common,'--sample-id',inv['sample_id'],'--run-id',inv['run_id'],'--output',str(out/'recovered')],0)
 restored=json.loads((out/'recovered/plan.json').read_text());assert restored==plan and entries[0].read_bytes()==before
 print('2/4  Recovered the SAME 64-well layout. No reselection; ledger bytes unchanged.')
 for label,fname,n in [('complete','measurements.json',24),('one_missing','one_missing.json',23)]:
  result=out/(label+'.json')
  call(label,'dosepilot.py',['predict',*common,'--plan',str(out/'recovered/plan.json'),'--measurements',str(here/fname),'--output',str(result)],0)
  value=json.loads(result.read_text());assert value['predicted_targets']==n
  print(('3/4' if n==24 else '4/4')+'  '+label+': '+str(n)+' predictions'+(' plus one explicit abstention.' if n==23 else '.'))
 summary={'status':'passed','scope':'WHOLLY INVENTED DATA AND MODEL','same_plan_recovered':True,'new_layout_selected':False,'ledger_sha256_before':digest(before),'ledger_sha256_after':digest(entries[0].read_bytes()),'biological_evaluation':False,'complete_predictions':24,'one_missing_predictions':23,'commands':len(records)}
 (out/'DEMO_RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
 print('Synthetic software demonstration, not an accuracy evaluation.');return 0
if __name__=='__main__':raise SystemExit(main())

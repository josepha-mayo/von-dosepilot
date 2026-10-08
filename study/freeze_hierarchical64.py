from pathlib import Path
import hashlib,json,datetime,sys
root=Path(__file__).resolve().parents[1]
study=root/'study'
inputs=[Path('/mnt/d/von-dosepilot-data/reconstructed_train/train_curves.csv'),study/'TRAIN_CATALOG.json',Path('/mnt/d/von-dosepilot-data/bandwidth_replay_pc_20261004/predictions_private.npz'),Path('/mnt/d/von-dosepilot-data/orientation_specific_control_quality_rank1_20261006_run1/predictions_private.npz')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=list(study.rglob('*.py'))+[study/'HIERARCHICAL64_PROTOCOL_20261008.md']
freeze={'state':'FROZEN_BEFORE_FIRST_CANDIDATE_FIT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':{str(p):sha(p) for p in inputs},'source':{str(p.relative_to(root)).replace('\\','/'):sha(p) for p in sources},'python':sys.version}
with (study/'HIERARCHICAL64_FREEZE.json').open('x',encoding='utf-8') as f:json.dump(freeze,f,indent=2);f.write('\n')
print('FROZEN',len(sources),'source files',flush=True)

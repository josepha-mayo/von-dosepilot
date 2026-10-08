"""Aggregate-only research report. Never exports individual response arrays."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import datetime,hashlib,json
from pathlib import Path
import numpy as np
DATA=Path('D:/von-dosepilot-data');REPO=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_run(name):
    folder=DATA/name;r=json.loads((folder/'RESULT.json').read_text());v=json.loads((folder/'VERIFICATION.json').read_text())
    if v['status']!='PASS' or v['result_sha256']!=sha(folder/'RESULT.json'):raise ValueError('missing verified result '+name)
    return folder,r,v

def main():
    tierdir,tiers,tv=read_run('accuracy_tiers_20261008_run1')
    finitedir,finite,fv=read_run('finite_auc64_20261008_run1')
    studentdir,student,sv=read_run('privileged_student64_20261008_run1')
    deployment=tierdir/'deployment128_private';manifest=json.loads((deployment/'manifest.json').read_text());cli=json.loads((deployment/'CLI_VERIFICATION.json').read_text())
    if cli['status']!='PASS' or sha(deployment/'model.npz')!=manifest['model_sha256']:raise ValueError('deployment verification')
    z=np.load(tierdir/'predictions_private.npz',allow_pickle=False);y=z['y'];p=z['patients'].astype(str);ids=np.unique(p)
    def losses(a):return np.array([(((a[0]-y)**2+(a[1]-y)**2)/2)[p==g].mean() for g in ids])
    old=losses(z['scientific64']);new=losses(z['budget128']);rng=np.random.default_rng(2026100817)
    indices=rng.integers(len(ids),size=(100000,len(ids)));ratios=old[indices].mean(1)/new[indices].mean(1)
    interval=np.quantile(ratios,[.025,.975]).tolist()
    ratio_note={'point':float(old.mean()/new.mean()),'descriptive_patient_bootstrap95ci':interval,'seed':2026100817,'replicates':100000,'selection_adjusted':False,'independent_biological_confirmation':False,'two_x_inside_interval':bool(interval [0]<=2<=interval [1])}
    def compact_arms(record):
        return {a:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'beats_retained_gate':v['gate'],'same_budget_2x':v.get('same_budget_2x',v.get('two_x',False))} for a,v in record['arms'].items()}
    compact_tiers={b:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'treatment_wells':v['treatment_wells'],'added_wells_vs64':v['additional_treatment_wells'],'error_reduction_factor_vs64':v['mse_improvement_factor_vs64'],'error_reduction_factor_vs72':v['mse_improvement_factor_vs72'],'accuracy_only_2x':v['accuracy_only_half_error_met'],'same_budget_2x':v['same_budget_half_error_met'],'patient_wins':v['accuracy_only_comparison_vs_scientific64']['patient_wins'],'fold_wins':v['accuracy_only_comparison_vs_scientific64']['fold_wins'],'target_mean_wins':v['accuracy_only_comparison_vs_scientific64']['targets_better']} for b,v in tiers['tiers'].items()}
    bundle={'schema':'dosepilot.research_progress_20261008.v1','as_of_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'population':{'samples':119,'whole_patients':59,'targets':24,'outer_patient_folds':5},'retained_scientific64':{'mse':0.001042745722096212,'p90':0.037419695944064885,'treatment_wells':64,'unchanged_by_this_work':True},'same_budget_half_error_target':0.000521372861048106,'same_budget_2x_achieved':False,'tiers':compact_tiers,'accuracy128_ratio_uncertainty':ratio_note,'finite_auc64':compact_arms(finite),'privileged_student64':compact_arms(student),'verifications':{'finite_auc64':fv,'accuracy_tiers':tv,'privileged_student64':sv,'deployment_cli':cli},'frozen_scientific_commits':{'finite_auc64':'a4e9899','accuracy_tiers':'fa5b154','privileged_student64':'18ff3e2'},'research_model':{'name':manifest['name'],'private_directory':str(deployment),'required_treatment_wells':128,'model_sha256':manifest['model_sha256'],'deployment_option':manifest['deployment_option'],'synthetic_inference_passed':True,'retained64_replaced':False},'submission_changed':False,'independent_biological_validation':False,'official_competition_score':None,'source_runs':{'finite_auc64':str(finitedir),'accuracy_tiers':str(tierdir),'privileged_student64':str(studentdir)}}
    report=REPO/'docs'/'ACCURACY_TIER_PROGRESS_20261008.md';evidence=REPO/'evidence'/'accuracy_tier_progress_20261008.json'
    with evidence.open('x',encoding='utf-8') as f:json.dump(bundle,f,indent=2);f.write('\n')
    lines=['# von DosePilot: measured accuracy gain and remaining 64-well gap','',
      '**Result:** The new 128-well research tier scores 0.0005102658031862283 MSE, a 2.0435-fold reduction versus the retained 64-well MSE 0.001042745722096212. It requires 128, not 64, treatment wells. **The original same-budget 2x goal remains unmet.**','',
      '## Cost and accuracy','',
      '| Procedure | Treatment wells | Added wells vs64 | Patient-balanced MSE | p90 patient RMSE | MSE reduction factor vs retained 64 |',
      '|---|---:|---:|---:|---:|---:|',
      '| Retained scientific model |64|0|0.001042745722|0.037419696|1.000x|']
    for B in ('80','96','112','128'):
        v=compact_tiers[B];lines.append(f"| New research tier |{B}|{v['added_wells_vs64']}|{v['mse']:.12f}|{v['p90']:.9f}|{v['error_reduction_factor_vs64']:.4f}x|")
    lines+=['',
      'The 128-well tier improves 59/59 patient-average errors, 5/5 outer-fold errors and 24/24 target-average errors relative to retained 64. This does not mean every individual sample-target prediction improves. Against the recorded 72-well research MSE 0.0009326007417880046, the 128-well tier is 1.8277x, not 2x. These are different measurement budgets.',
      '',f"The 2.0435x ratio is a development point estimate. A descriptive, selection-unadjusted whole-patient bootstrap gives 95% interval [{interval [0]:.4f},{interval [1]:.4f}]. This is not independent confirmation of a 2x generalization claim.",
      '',
      'All comparisons preserve 119 Lib1 samples, 59 whole patients, 24 original raw AUCs and patient-separated model selection. A/B are scored as alternative measured layouts; their prediction vectors are never combined into a free ensemble. The 128-well tier uses 64 wells from each source plate. Treatment counts do not establish monetary, material or elapsed-time savings.',
      '',
      '## Same-budget attempts and protection of the incumbent','',
      'The finite-AUC anchored/smooth-prior trial and cross-fitted richer-teacher-to 64-well-student trial were fully run and rejected. Their primary MSEs were'+f" {finite['arms']['nested_primary']['metrics']['mse']:.12f} and {student['arms']['nested_primary']['metrics']['mse']:.12f}, respectively. Neither replaced the retained 64 model or changed the Kaggle entry.",
      '',
      '## Verification and runnable artifact','',
      'Independent saved-model checks reconstructed 34,272 finite-AUC predictions, 28,560 cost-tier predictions and 28,560 student predictions, each with maximum difference 2.22e-16. Whole-patient weighting, physical budgets and excluded-patient mutation checks passed. Teacher fitting/soft-label groups were audited for nested separation. These are numerical integrity checks, not independent biological validation.',
      '',
      'A separately named all-training 128-well research model is saved privately at:',
      '',f'`{deployment}`','',
      'Its source inference CLI is `study/predict_research_tier.py`. The model uses the predeclared mode of outer training-selected spectral options: fraction 0.1, kernel ridge10. A fictional-data smoke test and valid A/valid B, missing, 64-only, duplicate, unpurchased, nonfinite and wrong-layout checks passed. The model refuses incomplete inputs instead of silently pretending 128 measurements cost 64. Model arrays contain training coordinates and must not be published as aggregate-only evidence.',
      '',
      'The private model is research-only, not clinically validated. All-training fitting is not another validation result. The retained 64 model, public submission and original scientific score remain unchanged.',
      '',
      '## Frozen sources','',
      '- Finite-AUC experiment: a4e9899; D:/von-dosepilot-finite-auc64-20261008.',
      '- Accuracy tiers: fa5b154; D:/von-dosepilot-accuracy-tiers-20261008.',
      '- Privileged student:18ff3e2; D:/von-dosepilot-privileged-student64-20261008.',
      '',f"Private128 model SHA256: `{manifest['model_sha256']}`.",
      '',
      'The companion aggregate JSON contains precise metrics, experiment paths, result hashes and verification receipts. No individual assay responses or trained kernel-coordinate arrays are included in that JSON.']
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    handoff=DATA/'DOSEPILOT_2X_HANDOFF_20261008.md'
    marker='## Verified128-well tier and failed64-well transfer, current addendum'
    if marker not in handoff.read_text():
        with handoff.open('a',encoding='utf-8') as f:f.write('\n\n'+marker+'\n\n128-well tier MSE 0.0005102658031862283,2.0435x lower than retained 64 but twice the treatment measurements. All59 patient means/5 folds/24 target means improve. Same-budget64 goal NOT met. Distilled64 student rejected; retained scientific64 MSE 0.001042745722096212 unchanged. Runnable model: '+str(deployment)+'. Current report: '+str(report)+'. Aggregate evidence: '+str(evidence)+'. All three new families independently replayed. No Kaggle change.\n')
    print(json.dumps({'report':str(report),'evidence':str(evidence),'report_sha256':sha(report),'evidence_sha256':sha(evidence),'ratio_uncertainty':ratio_note,'private_model':str(deployment),'same_budget_2x':False},indent=2),flush=True)
if __name__=='__main__':main()

"""Save aggregate experiment receipts; retain every incumbent model unchanged."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=Path('D:/von-dosepilot-data')
local_dir=data/'local_response_tiers_20261008_run1';control_dir=data/'control_transfer_tiers_20261008_run1'
L=json.loads((local_dir/'RESULT.json').read_text());LV=json.loads((local_dir/'VERIFICATION.json').read_text())
C=json.loads((control_dir/'RESULT.json').read_text());CV=json.loads((control_dir/'VERIFICATION.json').read_text())
assert LV['status']==CV['status']=='PASS'
with (root/'evidence/control_transfer_tiers_20261008.json').open('x') as f:json.dump({'result':C,'independent_verification':CV,'source_commit':'9270dc1','promotion':'NONE'},f,indent=2);f.write('\n')
B64=.001042745722096212;B128=.0005102658031862283
fixed=L['tiers']['128']['own14_full'];local124=L['tiers']['124']['nested_primary']
summary={
 'schema':'dosepilot.followthrough_20261008_1423.v1','created_utc':datetime.now(timezone.utc).isoformat(),
 'scope':'Response to then keep going after the original128-well research result',
 'retained64':{'mse':B64,'p90':.037419695944064885,'treatment_wells':64,'unchanged':True},
 'retained128':{'mse':B128,'p90':.028122765834466153,'treatment_wells':128,'unchanged':True},
 'same_budget_half_error_target':B64/2,'same_budget_half_error_achieved':False,
 'primary64_local':{'mse':L['tiers']['64']['nested_primary']['metrics']['mse'],'decision':'REJECT'},
 'primary64_control_calibration':{'mse':C['tiers']['64']['full_common']['metrics']['mse'],'decision':'REJECT'},
 'legacy64_integration':{'mse':L['integration64']['metrics']['mse'],'decision':'REJECT','full_legacy_rebuild':False},
 '124_well_nested':{'mse':local124['metrics']['mse'],'p90':local124['metrics']['p90'],'treatment_wells':124,'added_wells_vs64':60,'fewer_wells_vs128':4,'mse_reduction_factor_vs64':B64/local124['metrics']['mse'],'half_error_threshold_reached':False,'status':'DIFFERENT_COST_RESEARCH_ONLY'},
 '128_well_nested':{'mse':L['tiers']['128']['nested_primary']['metrics']['mse'],'p90':L['tiers']['128']['nested_primary']['metrics']['p90'],'comparison_to_retained128':L['tiers']['128']['nested_primary']['vs_reference128'],'status':'NOT_PROMOTED'},
 '128_well_best_fixed_secondary':{'name':'own14_full','role':'PRESPECIFIED_SECONDARY_NOT_NESTED_PRIMARY','mse':fixed['metrics']['mse'],'p90':fixed['metrics']['p90'],'treatment_wells':128,'added_wells_vs64':64,'mse_reduction_factor_vs64':B64/fixed['metrics']['mse'],'relative_mse_gain_vs_retained128':1-fixed['metrics']['mse']/B128,'comparison_to_retained128':fixed['vs_reference128'],'status':'NOT_PROMOTED_4_OF_5_FOLDS_IMPROVE'},
 'independent_replay':{'local':LV,'control_calibration':CV,'combined_predictions':LV['predictions_reconstructed']+CV['predictions_reconstructed']},
 'source_commits':{'local_frozen':'eaf33c0','local_outcome':'5951cb9','control_frozen':'9270dc1'},
 'run_paths':{'local':str(local_dir),'control':str(control_dir)},
 'raw_result_sha256':{'local':LV['result_sha256'],'control':CV['result_sha256']},
 'independent_biological_confirmation':False,'selection_adjusted':False,'submission_changed':False,'retained_models_replaced':False,
 'limitations':['Repeated adaptive development on the same119 samples and59 whole patients.','The128-well improvement is a secondary point estimate, not a new2x gain relative to the existing128-well model.','The124-well point estimate must not be rounded up to claim2x.','Standard-control calibrated variants require ten quality summaries in addition to the declared treatment values.','No new fitted model was promoted or submitted.']}
with (root/'evidence/response_followthrough_20261008_1423.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
report=f'''# DosePilot research follow-through, 8 October 2026

## Decision
No new model replaces the retained64-well or128-well versions. The original same64-budget half-error goal remains unmet.

## Measured outcomes

| Procedure | Treatment wells | Patient-balanced full24 MSE | Interpretation |
|---|---:|---:|---|
| Retained scientific model | 64 | {B64:.15f} | Unchanged |
| Required same64 half-error target | 64 | {B64/2:.15f} | Not achieved |
| New query-local primary | 64 | {summary['primary64_local']['mse']:.15f} | Rejected |
| New standard-control primary | 64 | {summary['primary64_control_calibration']['mse']:.15f} | Rejected |
| New query-local nested procedure | 124 | {local124['metrics']['mse']:.15f} | {B64/local124['metrics']['mse']:.6f}x vs retained64; still below2x |
| Retained higher-cost research tier | 128 | {B128:.15f} | Unchanged |
| New query-local nested procedure | 128 | {summary['128_well_nested']['mse']:.15f} | Slightly lower point estimate; not promoted |
| New fixed local secondary | 128 | {fixed['metrics']['mse']:.15f} | {(1-fixed['metrics']['mse']/B128)*100:.4f}% lower mean than retained128; not promoted |

The best fixed128-well secondary improved37/59 patient means and4/5 fold means, with nonworse p90. It was specified before its outcomes but is not the primary70-option nested selector. It remains a research candidate rather than a replacement under the campaign's consistency requirement. Its{B64/fixed['metrics']['mse']:.6f}x comparison is against retained64, with twice the treatment measurements; it is not another2x improvement over retained128.

The124-well procedure uses60 more measurements than the64-well model and four fewer than128. Its1.99049x point estimate does not meet the literal half-error threshold. Standard-control transfer did not rescue that shortfall.

## Work completed
The first new family adapts own-drug ridge coefficients to query-specific neighborhoods using only purchased response features. It preserves the global additive spectral residual. The second family applies measured plate-control quality summaries to cross-fitted residuals through a shared scalar correction and rank1 target deviations. Both keep patients separated throughout model/panel selection, preserve the original24 endpoints, and account separately for each A/B layout and cost tier.

Independent numerical verifiers reconstructed{summary['independent_replay']['combined_predictions']:,} predictions. The local verifier used a separately implemented augmented weighted-regression solver; the control verifier also rebuilt the quality-feature algebra. Maximum numerical differences were{LV['maximum_prediction_difference']:.3g} and{CV['maximum_prediction_difference']:.3g}. The original controls reproduced and all excluded-label/full-curve/control mutation sentinels were zero.

These are repeated-development results on119 samples from59 patients, not independent biological confirmation, clinical validation, or official competition scores. Numerical replay checks software integrity, not biological generalization.

## Locations and provenance
Local worktree: D:/von-dosepilot-local-response-tiers-20261008/
Control worktree: D:/von-dosepilot-control-transfer-tiers-20261008/
Local immutable run: {local_dir}
Control immutable run: {control_dir}
Frozen code commits: eaf33c0 and9270dc1.
Local result SHA256: {LV['result_sha256']}
Control result SHA256: {CV['result_sha256']}

No public push, Kaggle update, or replacement of either retained model was performed.
'''
for old_word,new_word in [('retained64','retained 64-well'),('retained128','retained 128-well'),('same64','same 64-well'),('below2x','below 2x'),('another2x','another 2x'),('best fixed128-well','best fixed 128-well'),('primary70-option','primary 70-option'),('improved37/59','improved 37/59'),('and4/5','and 4/5'),('The124-well','The 124-well'),('uses60','uses 60'),('the64-well','the 64-well'),('than128','than 128'),('Its1.99049x','Its 1.99049x'),('original24','original 24'),('through59','through 59'),('on119','on 119'),('from59','from 59'),('and9270dc1','and 9270dc1')]: report=report.replace(old_word,new_word)
(root/'docs/RESPONSE_FOLLOWTHROUGH_20261008_1423.md').write_text(report,encoding='utf-8')
# A separate handoff preserves the older campaign handoff and all source outcomes.
(data/'RESPONSE_FOLLOWTHROUGH_20261008_1423.md').write_text(report,encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)

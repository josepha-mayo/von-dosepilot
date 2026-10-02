# Multioutput covariance acquisition, 2 October 2026

This is a new, repeatedly reused Lib1 development study, not independent confirmation.
The new question concerns acquisition, not another kernel grid: can a deterministic
multioutput covariance search improve the current additive model's physical dose plan?

The control is the independently reproduced additive method, full24 MSE
0.001060552730112811. S2 and the original R13/R18 thresholds remain immutable references.
The current public base was read at87e7a686875d05b636d80d12a98466d17616f80c and the
protected-data ledger still marks all Lib2 records exposed. No Lib2 is permitted.

## Fixed acquisition
Inside EVERY fitting slice, first build the exact R13 64-dose plan. Preserve all24
head ownerships, the exact16 upgraded targets, each target's2/3dose count and the
original complementary32/32plate pattern. Form equal-patient, half-A/B weighted
moments of the two-plate native input universe and all24 original targets. Standardize
fitting inputs with the original0.05floor and fitting weighted means.

For selected columns S, the proxy is
(trace(Cyy)-trace(Cxy[S].T@(Cxx[S,S]+0.1I)^-1@Cxy[S]))/24.
It is the minimized regularized LINEAR training loss proxy, not a calibrated test-risk
estimate. For each target, in lexicographic target-ID order, enumerate every same-size
native-dose subset. Evaluate each replacement holding all other current selections
fixed, using a Schur-complement calculation. Keep the current block unless proxy drops
by more than1e-12. Perform exactly ONE sweep, no revisit or expanded search.

This differs from the earlier S16 proposal: the starting plan and every change are
learned without the current inner validation patients. It is not an outer-fitted plan
reused as an input to its inner validation and is not217explicitplans tuned on outcomes.

## Two arms, fixed before fitting
1. Forced covariance-sweep plan with the unchanged additive residual-kernel family.
2. Inner-only plan selector choosing old R13 or covariance-sweep acquisition jointly
with the spectral option. This contains the original additive control as a candidate.

Each plan uses identity/no correction plus fraction{0.1,0.3,0.6} x lambda{0.1,1,10};
one common configuration across all24outputs and both orientations. Tie order favors
original acquisition, then the original spectral option order. No target-splicing,
output clipping, outer-outcome scalar tuning or missing-data imputation.

Original119samples/59wholepatients/24fixed unclippedtargets,5outer/3innerpatientfolds,
64distincttreatmentwells perdeployment,32perplate. Average A/B squared LOSSES, never
predictions. Changing acquisition requires a newly fitted model and new commitment;
old fitted weights do not transfer to new dose identities.

## Success and verification
Against additive and S2, require lower meanMSE,>=30/59patientwins,>=3/5foldwins and
nonworsep90patientRMSE. Also require all original R13/R18 clauses:>=5%mean reduction,
>=40/59wins,>=4/5foldwins,p90nonworse,bothcandidateorientationmeans below each
reference's expectedMSE. A failed clause prevents promotion. Retain both arms,
regressing patients/targets and zero-change plans. Paired bootstrap10000seed20261002
is descriptive, not selection-corrected, and cannot turn adaptive search into confirmation.

Before fitting: nine synthetic tests cover full-vs-Schur calculations, cached moments,
whole-patient weights, cost, monotonicity, zero-signal ties, no mutation and paid-value masks.
After prediction files are committed: verify all controls, native/well identities,
metrics/gates separately and reload selected models. No raw workbook or external cohort
will be opened. Inputs in the current working container are a hash-checked copy of the
historical private TRAIN kit; public-CSV replays are a separate reproduction activity.

Related primary-source lead: Longi et al., Sensor Placement for Spatial Gaussian
Processes with Integral Observations, PMLR124:1009-1018,2020. This is a different
physical application and only motivates evaluating acquisition; the present greedy
ridge-proxy heuristic and its test data are not validated by that paper.

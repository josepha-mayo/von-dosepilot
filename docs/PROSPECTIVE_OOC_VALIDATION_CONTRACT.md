# Prospective organ-on-chip validation contract

**Status: prospective protocol skeleton only. No experiment described here has been run.**

DosePilot's current predictive evidence is retrospective Lib1 development on ordinary organoid-plate data. The organ-on-chip compiler proves only logical compatibility with caller-declared resources. A future biological study must therefore be designed as a genuinely new experiment rather than reusing exposed Lib2/Protected22 material.

## 1. Frozen objects before the first response

Before collecting any response used for validation, archive and hash:

- the bandwidth-0.7 model source and constructed model receipt;
- the exact 64-treatment acquisition plan and its A/B alternative layouts;
- the organ-on-chip inventory schema and compiled execution manifest;
- the endpoint definition, normalization, timepoint, and full-profile reference procedure;
- the biological-unit definition and exclusion criteria;
- the plate/control QC rules;
- the statistical analysis plan and success criterion.

The current development model may not be retuned after this freeze using prospective-study outcomes.

## 2. Biological unit and independence

The intended domain is the same colorectal patient-derived organoid setting that motivated the retrospective work, implemented on a reviewed chip/device system.

The exact tissue preparation, chip platform, material, flow conditions, readout, and sampling time remain **TBD and must be fixed before response collection**.

The confirmatory unit should be an independent patient-level biological unit. Multiple technical samples from one patient remain grouped and cannot be split across training/validation roles.

Previously exposed Lib2/Protected22 records are ineligible as untouched confirmation.

## 3. Treatment budget and orientation

For each prospective deployment:

- schedule exactly **64 treatment measurements**;
- map exactly **32 treatment measurements to each of two source plates**;
- choose **one** frozen orientation, A or B, before responses are observed;
- do **not** run both A and B and combine them as one 128-well prediction;
- vehicle and viability controls remain separate declared resources and are not hidden inside the 64-treatment budget.

If both orientations are studied across the cohort, randomize or otherwise prespecify orientation assignment before outcomes and report orientation-stratified results.

## 4. Chip execution manifest

Every requested treatment must be bound before dosing to:

- drug identity;
- exact concentration and units;
- physical source well;
- chip compartment;
- channel / circuit / reservoir identity;
- dosing route;
- exposure duration;
- readout timepoint.

The existing compiler must reject missing/substituted doses, duplicated identities, incompatible shared-flow exposures, missing controls, and plan-budget tampering.

A compiler PASS is not evidence that the physical protocol is scientifically adequate. Device-specific constraints must be added before the real run.

## 5. Plate-level calibration and QC

The frozen synthetic robustness audit shows that coherent ±5% single-plate scaling is much more damaging than small independent input noise. Therefore a future wet-lab study must have a prespecified plate-calibration/QC rule.

Required before collection:

- define the actual plate-level control measurements;
- define how drift is estimated from those controls;
- define an acceptance/rejection rule or correction rule;
- freeze that rule before any confirmatory target is revealed.

**No numeric QC threshold is established by the current simulation.** Choosing one after looking at prospective model outcomes would invalidate the confirmatory interpretation.

## 6. Prediction commitment

For each biological unit:

1. verify the compiled treatment manifest and controls;
2. acquire the one assigned 64-well treatment deployment;
3. commit the identified measurement file and model hash;
4. run the primary predictor;
5. seal the prediction/evidence record;
6. only then reveal or compute the full-profile reference targets used for scoring.

A required missing treatment reading causes the primary bandwidth prediction to be withheld. No silent imputation or free replacement treatment well is allowed.

Any rerun policy must be declared beforehand and its additional resource cost reported separately.

## 7. Reference targets

The 24 validation targets must be computed from a prespecified reference assay/profile that is independent of the model's 64 purchased input values except where the scientific endpoint inherently reuses the same measurement.

Before collection, document:

- the dose grid used for each target;
- interpolation/integration rule;
- viability normalization;
- endpoint units;
- handling of failed/nonnumeric measurements;
- whether any purchased input also contributes to the scored reference target.

The scoring denominator and target-availability mask must be fixed across all compared methods.

## 8. Comparator fairness

At minimum score, on the **same prospective units and same scoring mask**:

- frozen bandwidth-0.7 successor;
- frozen previous additive model;
- frozen R13 own-drug model.

Where the models use the same acquisition plan, they must consume exactly the same 64 measured values. If a comparator requires a different physical plan, that difference must be explicit and its cost cannot be hidden.

## 9. Primary and secondary analyses

The primary confirmatory analysis should be paired at the patient level.

Recommended frozen primary question:

> Does the bandwidth-0.7 procedure have lower patient-balanced full-24 MSE than the frozen R13 procedure on genuinely new biological units?

Before collection, choose and freeze the confidence procedure and sample-size/power calculation. The current development folds are not independent replications and should not be used as the confirmatory sample.

Secondary analyses should include:

- paired patient loss distribution and patient win count;
- p90 patient RMSE;
- all 24 target mean errors, including regressions;
- A/B orientation-stratified performance if both orientations are represented;
- failed/withheld prediction count;
- plate-QC failures and exclusions with reasons.

The study should report adverse target results even if the primary endpoint passes.

## 10. Evidence levels after the study

A future report must keep these claims separate:

- **software execution:** identity, budget, manifest, and evidence-ledger checks;
- **prospective predictive validation:** only if the frozen model is scored on genuinely new biological units under this protocol;
- **laboratory efficiency:** only from actual measured resource use, not retrospective extrapolation;
- **clinical utility:** not established by a model/assay validation study alone.

## Unresolved fields that must be closed before data collection

- chip/device platform;
- tissue preparation and passage criteria;
- exposure duration and assay timepoint;
- readout technology and normalization;
- exact control layout and resource count;
- plate-QC drift estimator and acceptance/correction rule;
- full-profile reference assay;
- prospective cohort size and power analysis;
- predeclared statistical confidence procedure;
- rerun policy and cost accounting.

Leaving these fields visible is intentional. The current project is ready to define a real prospective study; it has not already performed one.

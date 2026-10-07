# Routine-control affine transport at the original 64-treatment-well budget

## Question and objective
Can spatial information from the SAME routine positive/negative controls improve reconstruction by accounting for sample-specific affine plate distortion? This is a new measured assay-QC channel, not another sweep of the existing response-only kernel. The half-error objective remains MSE <=0.000521372861048106 and retained p90 <=0.037419695944064885, on the original 24 outputs and 64 treatment wells. It has not been achieved.

The completed empirical shape mixture and matched Gaussian control were worse than the retained model. Those outcomes are preserved and neither model is used here. The existing rank-1 QC candidate uses median/range/CV summaries but no physical control positions or explicit mapping of control-derived fields through complete curves. This trial does not inherit the historical 49-stage fitted residual chain.

## Resource audit before candidate evaluation
A guarded XML extractor decoded 5,236 control signals: 13 negative and 9 positive controls on each of 238 authorized Lib1 TRAIN plates. They have the same scattered physical geometry on all samples and reproduce the previous control log-median/range/CV resource exactly. Zero treatment signals, viability cells or Lib2 numerical responses were semantically decoded by that extractor. Parsing the workbook traverses uninterpreted XML bytes and shared strings; this is not a claim of zero raw-byte access. Seven synthetic access-guard tests passed.

The inventory was inspected before defining the candidate; no candidate errors were computed from it. It is NOT an independent validation set. Controls remain separately required assay resources, not zero-cost or zero-well experiments. The candidate does not purchase any extra treatment or control well compared with the retained control-aware research model. Spatial coordinates and the full plate layout are known assay metadata.

## Fixed field estimator and three separately reported arms
The 16-by-24 plate coordinates are scaled to [-1,1]. Let N and P be the median negative- and positive-control raw signals, and R=N-P. Require a positive finite R; otherwise record failure, with no sample deletion or outcome-dependent repair.

For each control type separately regress (signal - its median)/R on an intercept and centered row/column coordinates. The intercept is the control mean residual. Spatial slopes minimize mean squared error plus 0.1*||slope||^2; an unvarying control coordinate produces zero slope, not an invented gradient. Fit these fields from that sample's own controls only, never treatment responses or labels. Report geometry rank.

Arms, fixed before candidate outcomes:
1. identity benchmark: offset=0 and gain=1; no control adjustment.
2. flat-control mechanistic control: the two fitted intercepts only, no spatial slopes.
3. PRIMARY spatial-control transport: both intercept and row/column slopes.

Given negative-control residual field fN and positive-control field fP, use offset=fP and gain=clip(1+fN-fP, 0.25, 4). Report all gain clipping. This is a prespecified nuisance model; it is NOT a proven biological correction or an inferred noise floor.

## Raw endpoint preservation
Transform a normalized measurement v to latent coordinate (v-offset)/gain. On FITTING patients only, transform all 416 historical full-curve cells and fit a ridge head (penalty 0.01) for every target's full two-plate curve from that target's own purchased 2/3 transformed values. The two alternative layouts are stacked as separate training views with equal-patient weighting, exactly as the existing own-drug family. Input scale floor remains 0.05.

For a query, infer its full latent curve using ONLY the selected 64 treatment measurements plus routine controls/known positions. Then transform the inferred full curve back via raw=offset+gain*latent and integrate the exact original AUC quadrature. The endpoint remains the original raw normalized log-dose AUC, not a denoised or relabelled target. No unmeasured query response is supplied. The identity arm's linear operations commute with quadrature and must reproduce the existing own-drug predictor.

For each arm add the unchanged bandwidth-0.7 cross-drug residual kernel, using that arm's standardized purchased latent values and raw-AUC training residuals. Select one global option from the existing ten options (identity; fraction 0.1/0.3/0.6 crossed with ridge 0.1/1/10) by 3 fully regenerated whole-patient inner folds. Do NOT choose among the three arms on a target, fold or orientation basis. Report all three separately regardless of direction.

## Evaluation and invariant task
Original 119 Lib1 samples, 59 whole patients, 24 outputs and 5 outer whole-patient folds. The original R13 acquisition is rebuilt inside every fitting split using only its patients. Exactly 64 distinct eligible native doses, eight 2-dose and sixteen 3-dose targets, 32 cells per source plate. Average A/B LOSSES only, never their prediction vectors. No Protected22/Lib2, new genotype, clinical outcome or external response data. Every regression, template, mean, scale, kernel and inner selection excludes the outer test patient and all their organoids. Sample-local control fields at inference are permitted measured covariates, not outcome fitting.

The identity benchmark must match operating MSE 0.0010582750420801538 within 1e-12. Each other arm independently requires lower MSE, >=30 patient wins, 5/5 favorable folds and nonworse p90 versus BOTH retained64 (0.001042745722096212) and operating64 before eligibility for fresh independent replay. Preserve R13/R18 gates before any promotion. Half-error is a separate absolute threshold, not a name for a smaller gain. No automatic promotion or submission edit.

Prespecified descriptive paired bootstrap: 100,000 patient resamples, seed 202610072227. All results are repeatedly reused adaptive development, not independent biological validation or selection-adjusted inference. Complete all folds; no early stopping on bad outcomes, post-outcome parameter changes, target/fold splicing or silent retries.

## Checks
Before freeze: synthetic affine roundtrip, constant-coordinate behavior, exact identity-to-ridge equivalence, patient weighting, missing-input rejection, query-location bounds and raw endpoint restoration. Authenticate control inventory, source, prior quality resource, current curve/catalog and reference bytes. On biological evaluation poison every unpurchased query cell; rebuild outer fold zero after altering only its training-ineligible responses while preserving actual query values and routine controls. Save numeric states and independently recompute raw-space predictions and metrics. Publish aggregates only, not patient arrays or control signals.

## Primary method references checked 7 October 2026
Mpindi et al., Impact of normalization methods on high-throughput screening data with high hit rates and drug testing with dose-response data, Bioinformatics (2015), DOI 10.1093/bioinformatics/btv455. Controls scattered across the plate can support spatial assessment; inappropriate normalization can also damage results.
Mazoure et al., Identification and Correction of Additive and Multiplicative Spatial Biases in Experimental High-Throughput Screening (2018), DOI 10.1177/2472555217750377. Additive and multiplicative spatial bias are established concepts, not inventions of this project.
These papers motivate the hypothesis, not the chosen numeric coefficients or a DosePilot gain. The new estimator is a deliberately fixed experimental application, not a validated assay correction.

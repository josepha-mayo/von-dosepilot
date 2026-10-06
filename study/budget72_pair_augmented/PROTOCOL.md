# 72-well pair-augmented bandwidth kernel

The current frontier is additive across the 24 drug groups. This study adds a controlled cross-drug interaction kernel while keeping the exact same acquisition, base ridge, patient folds, and bandwidth-0.7 group geometry.

For each target group j, build its Gaussian kernel at bandwidth multiplier 0.7 and center that group kernel using fitting-row patient weights. Let C_j be the centered group kernel scaled by group width 3. The pair kernel is sum_{j<k} C_j ⊙ C_k. By the Schur product theorem, products of PSD group kernels remain PSD. The pair term is energy-normalized on fitting rows by weighted diagonal energy.

Candidate kernel = current bandwidth-0.7 kernel + pair_strength × normalized_pair_kernel.

Frozen pair strengths are {0, 0.1, 0.25, 0.5}; strength 0 is exactly the incumbent kernel. Each strength uses the same ten residual spectral options. One global (strength, residual option) pair is selected by 3 whole-patient inner folds for each outer fold.

No target- or orientation-specific strength. No outer splicing. 72 treatment wells remain fixed.

Primary comparator: current 72-well frontier MSE 0.0009326007417880046. Successor gate: lower MSE, >=30 patient wins, 5/5 favorable folds, and p90 nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction.

# 72-well three-dose shape geometry

Every target in the 72-well acquisition has exactly three purchased doses. The current local Gaussian kernel treats those three standardized coordinates isotropically.

This study rotates each target's three coordinates into an orthonormal shape basis:

- level: (1,1,1)/sqrt(3)
- slope: (-1,0,1)/sqrt(2)
- curvature: (1,-2,1)/sqrt(6)

Coordinates inside each target are ordered by native concentration before the transform.

Candidate distance is the weighted squared distance in this shape basis. Frozen relative weight vectors are:
(1,1,1), (1,1,0.5), (1,1,0.25), (1,0.5,0.25), (2,1,0.5), (1,2,0.5). Each is rescaled to mean 1, so total local distance scale remains comparable. The first is exact incumbent geometry.

For each outer fold, 3 whole-patient inner folds choose one global (shape-weight-set, residual spectral option) pair. No target-specific or orientation-specific geometry. No outer splicing. Treatment budget remains 72 wells.

Primary comparator is the frozen 72-well bandwidth frontier MSE 0.0009326007417880046. Successor gate: lower MSE, >=30 patient wins, 5/5 favorable folds, p90 nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction.

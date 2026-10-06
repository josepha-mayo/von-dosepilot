# Public audit: 72-well bandwidth-0.7 residual frontier

This audit reconciles the completed `budget72-bandwidth07-transfer` branch without
promoting it over the 64-well scientific successor.

## Frozen lineage

The proposal, protocol, implementation and synthetic tests were frozen in commit
`b772b3e94a4747019ac06a8b5e7319523b11300d`. The result was added by its direct
child, `e3413b71958566abee4725892ebfe7dde42b4c31`. The frozen source files did not
change between those commits, and every source and dependency digest recorded in
`study/budget72_bandwidth07_residual/FREEZE.json` matches the public bytes.

This repository lineage establishes that the public protocol preceded the public
result commit. It is not an independent attestation of when private inputs were
first opened.

## Result and decision

The transferred 72-well bandwidth-0.7 residual procedure records MSE
`0.0009326007417880046`. Against the raw 72-well base it records 47/59 patient
wins, 5/5 favorable outer folds, 22/24 target-average wins, better p90 patient
RMSE and a descriptive bootstrap interval wholly below zero.

Against the current 64-well scientific successor it records 10.56298% lower mean
MSE, 48/59 patient wins and 5/5 favorable folds. It nevertheless fails the frozen
promotion requirement because its p90 patient RMSE is `0.03770730634910972`,
worse than the successor's `0.037419695944064885`. The result is therefore
**rejected for promotion and preserved as a measurement/accuracy frontier point**.
It does not replace the scientific successor or the bandwidth-0.7 operational
baseline.

## Publicly checkable scope

The standalone public verifier checks the aggregate receipt, exact metric
arithmetic, tail-gate rejection, artifact hashes, freeze hashes and claim
boundaries. The private `RESULT.json`, private OOF predictions and source response
workbooks are not published, so the 5,712-prediction numerical replay cannot be
rerun from public artifacts alone. The recorded zero-difference replay is not
presented as an independent public reproduction.

This remains repeated adaptive Lib1 development, not independent validation,
prospective cost-effectiveness evidence, clinical evidence, finalist status or an
official score. Protected22/Lib2 responses were not accessed.

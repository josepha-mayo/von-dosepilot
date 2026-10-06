# Scientific-reliability finalist-package preflight

Run the additive response-free package check with:

```bash
python3 study/audits/finalist_package_preflight_scientific_reliability.py \
  --output finalist_package_preflight_scientific_reliability.json
```

The command preserves every v1–v5 runner and receipt. It executes eight checks:
the unchanged canonical 14-stage/173-test preflight plus seven standalone
checks. The eighth check verifies the immutable r8 rubric successor, which binds
the r7 scientific-successor map, the grouped OOF reliability receipt and the
clean isolated v5 package execution.

The package records MSE `0.001042745722096212`, 40/59 patient wins, 5/5
favorable folds and 19/24 target-average wins versus bandwidth-0.7. It also
records aggregate grouped OOF coverage of `0.9194915254237288` at 90%, with all
24 targets at or above 90% coverage. These are repeated-development results;
the reliability diagnostic is post-hoc and selection-unadjusted. Bandwidth-0.7
remains the operational/demo baseline.

The runner makes no network request and refuses to overwrite an existing
output. Verify the published receipt with:

```bash
python3 study/audits/verify_finalist_package_preflight_scientific_reliability.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_package_preflight_scientific_reliability.py' -v
```

This is package verification, not independent validation, a new model fit, a
Kaggle edit, a Netlify deployment, finalist confirmation, a clinical claim or
an official score.

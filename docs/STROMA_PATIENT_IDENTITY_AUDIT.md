# Farin stromal split: response-free patient-identity audit

Checked 1 October 2026 from public primary-source article metadata. No raw drug-response value or supplementary response table was opened for this audit.

Farin et al. describe a colorectal-cancer organoid–stroma biobank built from **30 patients** and 30 tumors. Figure 1A is the source-identity key: patient-case suffixes `01` through `30` connect primary tumor `Tnn`, patient-derived tumor organoid `Onn`, and fibroblast `Fnn`. The paper describes the materials as matched. This establishes the shared numeric suffix as a patient-case identifier within this cohort.

The previously frozen split is:

| Role | Published organoid / patient-case suffixes | Count |
|---|---|---:|
| Development | 02, 03, 04, 09, 10, 12, 16, 18, 21, 23, 24, 28, 29 | 13 |
| Confirmation | 01, 05, 06, 07, 11, 13, 14, 15, 17, 19, 20, 22, 25, 26, 27 | 15 |
| Overlap | none | 0 |
| Unused cohort cases | 08, 30 | 2 |

The matched-CAF confirmation is therefore **patient-case-separated from development**, not merely organoid-ID-separated: 13 development cases and 15 confirmation cases, with zero shared patient-case identifiers.

This response-free clarification strengthens the grouping provenance of the existing saved result. It does not create a new outcome, rerun the confirmation, validate the original 24 R13 heads, establish independence from every other dataset, or establish prospective organ-on-chip or clinical performance.

Primary source: Farin et al., *Cancer Discovery* (2023), DOI `10.1158/2159-8290.CD-23-0050`, PMCID `PMC10551667`. The abstract, Methods, Results and [Figure 1 identity key](https://pmc.ncbi.nlm.nih.gov/articles/PMC10551667/bin/2192fig1.jpg) jointly support the mapping. The associated Mendeley dataset is DOI `10.17632/fypp6xhkjy.1`.

Machine-readable scope and the exact suffix-set intersection are recorded in `evidence/stroma_patient_identity_audit_20261001.json`.

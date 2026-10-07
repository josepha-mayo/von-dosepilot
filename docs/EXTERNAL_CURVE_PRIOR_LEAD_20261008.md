# External curve-prior lead, checked 7 October UTC / 8 October WAT

## Status
PUBLIC-SOURCE RESEARCH ONLY. No NCI response archive has been downloaded, no external-source model has been trained, and no improvement has been measured from this lead. It is a candidate next action, not a completed deliverable or permission to use restricted clinical records.

## Why this lead is different
The completed masked/pool/shape/kernel studies repeatedly reused the same 59 organoid patients. Generic pretrained TabPFN models did not improve this task. A curve-specific prior trained on genuinely external dose-response experiments could bring new shape information rather than create more correlated masks of the same patients. That is a hypothesis; assay/domain mismatch may erase any benefit.

## Verified primary sources
The National Cancer Institute's official DCTD data index offers bulk screening and dose-response resources for scientific use:
https://dctd.cancer.gov/data-tools-biospecimens/data
https://dctd.cancer.gov/data-tools-biospecimens/data/bulk-data-downloads

The official NCI-60 download-page search record lists a July 2026 concentration/response release as a 332 MB ZIP, expanding to approximately 2.37 GB. This size is an index description, not a checked downloaded archive. The official HTS384 page has an October 2026 update, but direct fetching of its wiki page returned HTTP 403 in this session; its archive schema and usable download path are therefore NOT verified here:
https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/147193864/NCI-60%2BGrowth%2BInhibition%2BData
https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/998965250/HTS384%2BGrowth%2BInhibition%2BData

NCI describes the newer HTS384 format as a 384-well CellTiter-Glo assay with 72-hour exposure, versus the classic 96-well sulforhodamine-B assay with 48-hour exposure. These are not interchangeable labels or a proof of organoid transferability:
https://dctd.cancer.gov/drug-discovery-development/assays/high-throughput-screening-services/nci60

The classic method's percent-growth endpoint can encode growth inhibition or lethality relative to both starting cell counts and untreated controls. It is NOT automatically the same quantity as DosePilot's normalized viability. A naive division by 100 or clipping would not establish correct endpoint alignment:
https://dtp.cancer.gov/discovery_development/nci-60/methodology.htm

The bulk index also links an official query interface accepting NSC, CAS, NCI plate, PubChem SID or chemical-name search, with HTML/XML output. No query was submitted and no endpoint parameters were guessed:
https://dtp.cancer.gov/dtpstandard/subsets/dose.jsp

NCI's text-reuse policy generally permits reuse of NCI text unless otherwise indicated and asks for source credit. That statement is NOT a blanket verified license for every third-party dataset, archive, image, or model derived from an archive. Check the actual selected data terms and preserve attribution before use or redistribution:
https://www.cancer.gov/policies/copyright-reuse

## Bounded next action, before any new biological model trial
1. Resolve one official public archive or small query output without accounts, payment, private authentication or access-control workarounds. Inspect file metadata/schema and archive-specific use terms, verify provenance, cap download size, and check D: disk capacity before transfer. Do not use a third-party mirror merely to evade a restriction.
2. Audit whether raw assay fields allow a valid mapping or a clearly disclosed shape-only transfer. Keep classic and HTS384 sources separate. Confirm drug/dose identities and independent biological units. Multiple drugs, replicates and masks are not additional independent cell lines or organoid patients.
3. Check the existing project data registry for prior use. Never convert an already reserved external validation set into fitting data without declaring that boundary lost. Protected22/Lib2 remains forbidden.
4. Only then specify and freeze ONE domain-transfer experiment and mechanistic control. All DosePilot-specific fitting/selection must remain inside outer-training patients; inference must still use the original 64 paid measurements. A new external prior does not authorize changing the AUC endpoint, denominators, physical budget or promotion gates.

A plausible model route is learning a shared dose-position/response reconstruction prior externally and adapting it using fitting-only organoid data, with a no-external-data control. The exact architecture and transfer normalization are intentionally not selected until source compatibility is known. This lead does not claim the prior will halve error, and it must not become another open-ended hyperparameter sweep.

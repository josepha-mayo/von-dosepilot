# Frozen bandwidth treatment schedule for prospective organ-on-chip binding

**Status: exact treatment schedule frozen; chip/device binding is intentionally unresolved. No organ-on-chip experiment has been executed.**

This artifact turns the current bandwidth-0.7 DosePilot model's final 64-treatment plan into an auditable prospective execution schedule. It closes the question **"which drug, which exact dose, and which source plate?"** without pretending the future device, circuit, exposure duration, or readout has already been chosen.

## What is frozen

The source model is `dosepilot.additive_kernel_bandwidth.v1`, bandwidth multiplier **0.7**. Its final construction pins the original acquisition plan SHA-256:

`25b14b67b2e5ab82394f1409ed72f68ae264278095c280df9e552d4f1bdff2ca`

For each alternative orientation:

- exactly **64 distinct treatment identities** are scheduled;
- exactly **32 treatments map to p1 and 32 to p2**;
- the same 64 drug+dose identities appear in A and B;
- every A source-plate assignment is complemented in B;
- 24 targets are represented: **8 use two doses and 16 use three doses**;
- vehicle and viability controls remain **separate resources**, outside the 64-treatment budget.

A and B remain alternative deployments. Running both physically would consume two independent 64-treatment deployments. They are not a hidden 128-well prediction ensemble.

## What remains unresolved

The public CSV binding templates deliberately contain `TBD_BEFORE_PROSPECTIVE_COLLECTION` for:

- chip device identity;
- chip compartment;
- circuit;
- reservoir;
- channel;
- dosing route;
- exposure duration;
- readout timepoint;
- readout type.

Those fields must be fixed, reviewed, and hashed before prospective response collection. The source `well` labels in the JSON plans are prospective logical slots, **not claims that those physical wells or chips already exist**.

## Frozen target schedule

| Target | Frozen doses (nM) | A source plates | B source plates |
|---|---|---|---|
| 5-FU | 1000, 3000 | p1, p2 | p2, p1 |
| AZD7762 | 100, 300 | p1, p2 | p2, p1 |
| Afatinib | 10, 100, 300 | p1, p2, p1 | p2, p1, p2 |
| Alisertib | 100, 1000, 10000 | p2, p1, p2 | p1, p2, p1 |
| Atorvastatin | 300, 1000, 3000 | p1, p2, p1 | p2, p1, p2 |
| Bemcentinib | 300, 3000 | p1, p2 | p2, p1 |
| Encorafenib | 30, 300 | p1, p2 | p2, p1 |
| Gedatolisib | 30, 100, 300 | p2, p1, p2 | p1, p2, p1 |
| Gemcitabine | 10, 100, 300 | p1, p2, p1 | p2, p1, p2 |
| Idasanutlin | 300, 1000, 3000 | p2, p1, p2 | p1, p2, p1 |
| LCL161 | 250, 750, 25000 | p1, p2, p1 | p2, p1, p2 |
| LGK974 | 10, 1000, 3000 | p2, p1, p2 | p1, p2, p1 |
| Lapatinib | 30, 100, 300 | p1, p2, p1 | p2, p1, p2 |
| Luminespib | 10, 30, 300 | p2, p1, p2 | p1, p2, p1 |
| Methotrexate | 150, 500, 1500 | p1, p2, p1 | p2, p1, p2 |
| Napabucasin | 600, 2000 | p1, p2 | p2, p1 |
| Palbociclib | 300, 1000, 3000 | p2, p1, p2 | p1, p2, p1 |
| Panobinostat | 10, 30, 100 | p1, p2, p1 | p2, p1, p2 |
| Pevonedistat | 300, 1000 | p1, p2 | p2, p1 |
| Regorafenib | 300, 3000 | p1, p2 | p2, p1 |
| SN-38 | 3, 100, 300 | p2, p1, p2 | p1, p2, p1 |
| TAS-102 | 100, 1000, 10000 | p1, p2, p1 | p2, p1, p2 |
| Trametinib | 2.5, 7.5, 75 | p2, p1, p2 | p1, p2, p1 |
| Volasertib | 10, 100 | p1, p2 | p2, p1 |

## Files

- `evidence/frozen_bandwidth_orientation_A_plan_20261003.json`: normalized 64-row A acquisition schedule.
- `evidence/frozen_bandwidth_orientation_B_plan_20261003.json`: normalized 64-row B acquisition schedule.
- `evidence/prospective_ooc_binding_template_A_20261003.csv`: exact A treatments plus unresolved device fields.
- `evidence/prospective_ooc_binding_template_B_20261003.csv`: exact B treatments plus unresolved device fields.
- `evidence/frozen_ooc_execution_schedule_20261003.json`: hashes and claim boundary.
- `study/audits/verify_frozen_ooc_schedule.py`: response-free verifier.

## Machine check

Run:

```bash
python study/audits/verify_frozen_ooc_schedule.py --root evidence --repo .
```

The verifier checks the bandwidth construction/plan hashes, 64-treatment counts, 32+32 plate counts, treatment identity parity across A/B, complementary A/B plate assignment, 24-target 2/3-dose allocation, every unresolved template field, and separate control policy.

The release preflight executes this verifier and five dedicated tamper tests. Those tests reject a drifted public JavaScript schedule, literal transport escapes in judge-facing text, a promoted biological claim, and a non-complementary A/B plan even when its plan and template hashes are updated together. The verified public map is therefore derived-equivalent to the frozen JSON plans rather than an unchecked visual copy.

It also runs each schedule through the existing organ-on-chip compiler using an explicitly **synthetic one-independent-circuit-per-treatment witness**. Both compile to 64 treatment actions plus two separate control resources. That compiler PASS proves only encoded logical consistency with the invented witness; it is not evidence of device availability, tissue compatibility, flow adequacy, or biological validation.

Synthetic witness manifest hashes recorded by this audit:

- A: `c9048cb5869c6469ea2d8c3df5caf93d8951c2f84b32aa19193b8c8613e1e52f`
- B: `f8982b7e0f844c3cc0f8049f9c7ca1cdce9809d3130da00e2e075ae304be4400`

## Why this matters for a future real study

The retrospective model evidence already answers whether the algorithm can reconstruct the 24 targets under its historical 64-treatment budget. A prospective chip study needs a stricter question: **can one reviewed physical system execute exactly the frozen treatment schedule without hidden resource sharing or post-outcome substitutions?**

This manifest is the handoff point. The treatment schedule is frozen. The device-specific fields remain visible rather than invented. Once a real platform is chosen, fill those fields, declare controls/QC, run the compiler, commit the resulting manifest, and only then collect responses under the prospective validation contract.

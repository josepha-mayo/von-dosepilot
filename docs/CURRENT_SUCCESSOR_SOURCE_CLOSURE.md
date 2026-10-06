# Current successor source closure

The 6 October DosePilot successor is the endpoint of a large adaptive-development history. This release publishes that history instead of hiding it.

The machine-readable closure at `evidence/current_successor_source_closure_20261006.json` recursively records **49 frozen stages**, **172 prediction-dependency edges**, and **251 frozen source-file hashes** leading to `orientation_specific_control_quality_rank1`.

Run:

```bash
python study/audits/verify_current_successor_source_closure.py --root .
```

The response-free verifier checks that every stage and consumer edge exists, every consumer freeze declares the recorded prediction hash, every source path stays inside the repository, and all 251 declared source SHA-256 values match the published bytes.

## Boundary

This is **source provenance closure, not a clean-room numerical replay**. The original closure builder mapped producer stages by hashing private saved prediction files without decoding their arrays. Those private files are not published. The public verifier therefore checks the frozen producer mapping for internal consistency but does not reconstruct that mapping from private prediction bytes.

It reads no Protected22 response, publishes no patient-level prediction array, creates no new accuracy metric, and does not turn repeatedly inspected Lib1 development into independent validation.

The point is narrower and useful: a reviewer can now trace the code/protocol/freeze chain behind the current development result instead of receiving only the final four-stage model directory.

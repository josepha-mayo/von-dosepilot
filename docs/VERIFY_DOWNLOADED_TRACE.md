# Verify a downloaded demo trace

The live fictional demo exports a six-field JSON record from **Inspect full evidence record**. A reviewer can validate that downloaded file offline, without running the site or sending its contents anywhere:

```bash
python3 demo/verify_downloaded_trace.py ~/Downloads/dosepilot-trace-complete.json
```

The verifier requires the exact six fields, checks the filename against the recorded state, rejects duplicate or extra fields, enforces lowercase SHA-256 syntax, and matches the state-specific null/digest contract and four independently reconstructed public-demo digests. It recognizes `fresh`, `committed`, `missing`, `recovered`, and `complete` exports.

The verifier itself has a response-free self-test covering all five valid states and twelve malformed or tampered cases:

```bash
python3 demo/verify_downloaded_trace.py --self-test
python3 study/audits/verify_downloaded_trace_verifier.py
```

For a trace supplied on standard input, provide the expected downloaded filename so filename/state binding is still checked:

```bash
python3 demo/verify_downloaded_trace.py - \
  --expected-filename dosepilot-trace-complete.json < dosepilot-trace-complete.json
```

## Scope

A pass means the file has the exact public fictional-demo trace shape and the expected state-bound digest values. It does **not** authenticate who created the file, prove when it was created, recompute the hashes from raw readings or outputs (which the six-field export intentionally omits), or establish signed/WORM evidence, physical provenance, assay-control adequacy, biological validation, clinical suitability, or prospective organ-on-chip performance.

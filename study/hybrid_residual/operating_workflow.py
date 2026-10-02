#!/usr/bin/env python3
"""Use the existing commitment ledger with an explicitly selected hybrid backend.

Only this private imported module instance is rebound. The historical S2 source,
CLI and operating contract are unchanged. Both commands require an externally
recorded construction hash and retain the existing create-exclusive records.
"""
from pathlib import Path
import hashlib,importlib.util
from hybrid_inference import HybridModel
BACKEND_SHA256 = 'e0faa7dc3c30094b6b1ce96c6eab8157f5c3ce7183608f9f5110dce3f09c2aa7'

def load_backend():
    path=Path(__file__).resolve().parents[1]/'spectral_residual'/'operating_workflow.py'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BACKEND_SHA256:raise ValueError('Operating contract source changed; review before using this adapter')
    spec=importlib.util.spec_from_file_location('_dosepilot_hybrid_workflow_backend',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.SpectralModel=HybridModel
    return module

if __name__=='__main__':raise SystemExit(load_backend().main())

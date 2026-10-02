#!/usr/bin/env python3
"""POSIX durable-evidence workflow using compiled additive prediction.

This is an explicit runtime choice, not a silent replacement of old ledger
records. Pending staging names are not authoritative evidence. Guarantees
still depend on the OS/filesystem/device honoring synchronization requests.
"""
from pathlib import Path
import importlib.util
import sys
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(HERE),str(STUDY/'hybrid_residual')]
from compiled_inference import CompiledAdditiveModel
from durable_json import write_new


def load_backend():
    path=STUDY/'hybrid_residual/additive_workflow.py'
    spec=importlib.util.spec_from_file_location('_dosepilot_durable_additive_adapter',path)
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    backend=adapter.load_backend()
    backend.SpectralModel=CompiledAdditiveModel
    backend.write_new=write_new
    previous=backend.model_receipt
    paths={
        'workflow':HERE/'durable_workflow.py',
        'publication':HERE/'durable_json.py',
        'compiled_inference':HERE/'compiled_inference.py',
        'compiled_correction':HERE/'compiled_kernel.py',
        'original_workflow':STUDY/'spectral_residual/operating_workflow.py',
        'original_identity_checks':STUDY/'spectral_residual/inference.py',
        'original_additive_backend':STUDY/'hybrid_residual/additive_inference.py',
        'original_hybrid_backend':STUDY/'hybrid_residual/hybrid_inference.py',
        'original_kernel':STUDY/'hybrid_residual/kernel_spectral.py',
    }
    code={key:backend.digest(path) for key,path in paths.items()}
    def receipt(model_dir,construction_sha256):
        return dict(previous(model_dir,construction_sha256),
                    runtime_implementation=CompiledAdditiveModel.IMPLEMENTATION,
                    evidence_writer='posix.fsync-exclusive-link.v1',
                    runtime_code_sha256=code)
    backend.model_receipt=receipt
    return backend


if __name__=='__main__':raise SystemExit(load_backend().main())

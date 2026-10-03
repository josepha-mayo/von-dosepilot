#!/usr/bin/env python3
"""Durable commit/predict backend for the verified bandwidth-0.7 model.

This is a new explicit runtime adapter. It does not reinterpret commitments
created for the predecessor additive-1.0 lifecycle.
"""
from pathlib import Path
import importlib.util
import sys

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(HERE),str(STUDY/'hybrid_residual')]
from bandwidth_inference import BandwidthAdditiveModel
from durable_json import write_new

IMPLEMENTATION='dosepilot.bandwidth_durable.v1'

def load_backend():
    path=STUDY/'hybrid_residual/additive_workflow.py'
    spec=importlib.util.spec_from_file_location('_dosepilot_bandwidth_durable_adapter',path)
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    backend=adapter.load_backend()
    backend.SpectralModel=BandwidthAdditiveModel
    backend.write_new=write_new
    previous=backend.model_receipt
    paths={
      'bandwidth_workflow':HERE/'bandwidth_durable_workflow.py',
      'publication':HERE/'durable_json.py',
      'original_workflow':STUDY/'spectral_residual/operating_workflow.py',
      'additive_workflow':STUDY/'hybrid_residual/additive_workflow.py',
      'bandwidth_inference':STUDY/'hybrid_residual/bandwidth_inference.py',
      'bandwidth_kernel':STUDY/'hybrid_residual/bandwidth_additive.py',
      'additive_backend':STUDY/'hybrid_residual/additive_inference.py',
      'hybrid_backend':STUDY/'hybrid_residual/hybrid_inference.py',
    }
    code={key:backend.digest(value) for key,value in paths.items()}
    def receipt(model_dir,construction_sha256):
        return dict(previous(model_dir,construction_sha256),
                    runtime_implementation=IMPLEMENTATION,
                    evidence_writer='posix.fsync-exclusive-link.v1',
                    runtime_code_sha256=code)
    backend.model_receipt=receipt
    return backend

if __name__=='__main__':
    raise SystemExit(load_backend().main())

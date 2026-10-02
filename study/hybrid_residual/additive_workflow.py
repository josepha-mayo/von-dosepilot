#!/usr/bin/env python3
"""The unchanged append-only inventory workflow with the additive kernel backend."""
from pathlib import Path
import importlib.util
from additive_inference import AdditiveModel

def load_backend():
    path=Path(__file__).with_name('operating_workflow.py')
    spec=importlib.util.spec_from_file_location('_dosepilot_kernel_contract_adapter',path)
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    backend=adapter.load_backend();backend.SpectralModel=AdditiveModel
    return backend

if __name__=='__main__':raise SystemExit(load_backend().main())

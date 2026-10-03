#!/usr/bin/env python3
"""Durable-evidence workflow for the verified bandwidth-0.7 successor.

This is a new, explicit backend choice.  It does not migrate or reinterpret
commitments made by the historical additive-1.0 lifecycle.
"""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY / "hybrid_residual")]

from bandwidth_inference import BandwidthAdditiveModel
from durable_json import write_new

IMPLEMENTATION = "dosepilot.bandwidth07_identity_checked.v1"


def load_backend():
    path = STUDY / "spectral_residual" / "operating_workflow.py"
    spec = importlib.util.spec_from_file_location(
        "_dosepilot_bandwidth_durable_adapter", path
    )
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    backend.SpectralModel = BandwidthAdditiveModel
    backend.write_new = write_new
    previous = backend.model_receipt
    paths = {
        "workflow": HERE / "bandwidth_workflow.py",
        "publication": HERE / "durable_json.py",
        "operating_contract": STUDY / "spectral_residual" / "operating_workflow.py",
        "identity_checks": STUDY / "spectral_residual" / "inference.py",
        "bandwidth_inference": STUDY / "hybrid_residual" / "bandwidth_inference.py",
        "additive_inference": STUDY / "hybrid_residual" / "additive_inference.py",
        "hybrid_inference": STUDY / "hybrid_residual" / "hybrid_inference.py",
    }
    code = {key: backend.digest(source) for key, source in paths.items()}

    def receipt(model_dir, construction_sha256):
        return dict(
            previous(model_dir, construction_sha256),
            model_kind=BandwidthAdditiveModel.MODEL_KIND,
            bandwidth_multiplier=BandwidthAdditiveModel.EXPECTED_MULTIPLIER,
            runtime_implementation=IMPLEMENTATION,
            evidence_writer="posix.fsync-exclusive-link.v1",
            runtime_code_sha256=code,
        )

    backend.model_receipt = receipt
    return backend


if __name__ == "__main__":
    raise SystemExit(load_backend().main())

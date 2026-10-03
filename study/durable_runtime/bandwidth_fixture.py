"""Seeded fictional bandwidth-0.7 fixture used only by public software tests."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np

from bandwidth_inference import BandwidthAdditiveModel
from bandwidth_additive import BandwidthAdditive


def upgrade_fixture(fixture):
    destination = fixture.d / "bandwidth_model"
    destination.mkdir()
    shutil.copy2(fixture.modeldir / "plan.json", destination / "plan.json")
    with np.load(fixture.modeldir / "model_private.npz", allow_pickle=False) as source:
        arrays = {key: source[key].copy() for key in source.files}
    arrays["kernel_bandwidth_multiplier"] = np.asarray(0.7)
    training = arrays["z_training"]
    weights = arrays["weights"]
    owner = arrays["kernel_owner"]
    kernel = BandwidthAdditive(
        training,
        np.zeros((len(training), 24)),
        weights,
        owner,
        0.7,
    ).raw_cross(training)
    arrays["train_kernel_mean"] = weights @ kernel
    arrays["kernel_grand"] = np.asarray(arrays["train_kernel_mean"] @ weights)
    np.savez_compressed(destination / "model_private.npz", **arrays)
    receipt = json.loads((fixture.modeldir / "CONSTRUCTION.json").read_text())
    receipt.update(
        model_kind=BandwidthAdditiveModel.MODEL_KIND,
        bandwidth_multiplier=0.7,
        plan_sha256=hashlib.sha256((destination / "plan.json").read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(
            (destination / "model_private.npz").read_bytes()
        ).hexdigest(),
        fictional_fixture=True,
        biological_accuracy_claim=False,
    )
    construction = destination / "CONSTRUCTION.json"
    construction.write_text(json.dumps(receipt, sort_keys=True) + "\n")
    anchor = hashlib.sha256(construction.read_bytes()).hexdigest()
    model = BandwidthAdditiveModel.load(destination)
    return destination, anchor, model

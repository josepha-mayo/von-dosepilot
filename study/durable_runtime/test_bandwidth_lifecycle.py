import copy
import json
from pathlib import Path
import unittest

import numpy as np

import bandwidth_lifecycle
from bandwidth_fixture import upgrade_fixture
from bandwidth_inference import BandwidthAdditiveModel
import test_recover_baseline as fixtures


class BandwidthLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Tests("test_record_order")
        self.fixture.setUp()
        self.modeldir, self.anchor, self.model = upgrade_fixture(self.fixture)
        self.root = self.fixture.d / "bandwidth_lifecycle"
        self.root.mkdir()
        self.ledger = self.root / "ledger"
        self.ledger.mkdir()
        self.commitment = self.root / "commitment.json"
        self.template = self.root / "template.json"
        self.kw = dict(
            model_dir=self.modeldir,
            construction_sha256=self.anchor,
            ledger_dir=self.ledger,
            commitment=self.commitment,
        )

    def tearDown(self):
        self.fixture.tearDown()

    def commit(self):
        return bandwidth_lifecycle.execute(
            "commit",
            **self.kw,
            inventory=self.fixture.d / "inventory.json",
            template=self.template,
        )

    def measurements(self, missing=(), name="measurements.json"):
        if not self.commitment.exists():
            self.commit()
        value = json.loads(self.template.read_text())
        for row, observed in zip(value["measurements"], self.fixture.values):
            row["value"] = float(observed)
        for index in missing:
            value["measurements"][index]["value"] = None
        path = self.root / name
        path.write_text(json.dumps(value))
        return path, value

    def predict(self, path, name="primary.json"):
        return bandwidth_lifecycle.execute(
            "predict", **self.kw, measurements=path, output=self.root / name
        )

    def recover(self, path, name="baseline.json"):
        return bandwidth_lifecycle.execute(
            "recover",
            **self.kw,
            measurements=path,
            output=self.root / name,
            acknowledge_baseline_only=True,
        )

    def test_complete_prediction_matches_bandwidth_backend(self):
        path, _ = self.measurements()
        got = self.predict(path)
        want = self.model.predict(self.fixture.request)
        np.testing.assert_allclose(
            list(got["predictions"].values()),
            list(want["predictions"].values()),
            atol=1e-13,
            rtol=0,
        )
        self.assertEqual(got["model_kind"], BandwidthAdditiveModel.MODEL_KIND)

    def test_receipt_binds_current_model_and_runtime(self):
        receipt = self.commit()["model_receipt"]
        self.assertEqual(receipt["model_kind"], BandwidthAdditiveModel.MODEL_KIND)
        self.assertEqual(receipt["bandwidth_multiplier"], 0.7)
        self.assertEqual(receipt["lifecycle_policy"], bandwidth_lifecycle.POLICY)
        self.assertEqual(receipt["runtime_implementation"], "dosepilot.bandwidth07_identity_checked.v1")
        self.assertEqual(len(receipt["runtime_code_sha256"]), 7)
        self.assertEqual(len(receipt["lifecycle_code_sha256"]), 4)

    def test_historical_additive_model_is_rejected(self):
        bad = dict(self.kw, model_dir=self.fixture.modeldir, construction_sha256=self.fixture.anchor)
        with self.assertRaisesRegex(ValueError, "Wrong model family"):
            bandwidth_lifecycle.execute(
                "commit",
                **bad,
                inventory=self.fixture.d / "inventory.json",
                template=self.template,
            )

    def test_wrong_bandwidth_metadata_is_rejected(self):
        model = self.modeldir / "model_private.npz"
        with np.load(model, allow_pickle=False) as source:
            arrays = {key: source[key].copy() for key in source.files}
        arrays["kernel_bandwidth_multiplier"] = np.asarray(0.8)
        np.savez_compressed(model, **arrays)
        receipt = json.loads((self.modeldir / "CONSTRUCTION.json").read_text())
        import hashlib
        receipt["model_sha256"] = hashlib.sha256(model.read_bytes()).hexdigest()
        (self.modeldir / "CONSTRUCTION.json").write_text(json.dumps(receipt))
        anchor = hashlib.sha256((self.modeldir / "CONSTRUCTION.json").read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "Unexpected.*bandwidth"):
            bandwidth_lifecycle.execute(
                "commit",
                **dict(self.kw, construction_sha256=anchor),
                inventory=self.fixture.d / "inventory.json",
                template=self.template,
            )

    def test_missing_primary_is_withheld_and_recovery_is_labelled(self):
        path, _ = self.measurements((0,))
        with self.assertRaises(ValueError):
            self.predict(path)
        recovered = self.recover(path)
        self.assertEqual(len(recovered["baseline_predictions"]), 23)
        self.assertEqual(recovered["primary_predictions"], {})
        self.assertEqual(recovered["source_model_kind"], BandwidthAdditiveModel.MODEL_KIND)
        self.assertFalse(recovered["kernel_prediction_called"])

    def test_recovery_history_blocks_changed_reading(self):
        missing, _ = self.measurements((0,))
        self.recover(missing)
        changed, value = self.measurements(name="changed.json")
        value["measurements"][1]["value"] += 0.01
        changed.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "OBSERVATION_CHANGED"):
            self.predict(changed)

    def test_recovered_frame_completes_to_bandwidth_primary(self):
        missing, _ = self.measurements((0,))
        self.recover(missing)
        complete, _ = self.measurements(name="complete.json")
        got = self.predict(complete)
        want = self.model.predict(self.fixture.request)
        np.testing.assert_allclose(
            list(got["predictions"].values()), list(want["predictions"].values()),
            atol=1e-13, rtol=0,
        )

    def test_prediction_export_recovers_byte_identically(self):
        complete, _ = self.measurements()
        first = self.predict(complete)
        output = self.root / "primary.json"
        before = output.read_bytes()
        output.unlink()
        self.assertEqual(first, self.predict(complete))
        self.assertEqual(before, output.read_bytes())

    def test_all_single_missing_positions_withhold_primary(self):
        for index in range(64):
            request = copy.deepcopy(self.fixture.request)
            request["measurements"][index]["value"] = None
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.model.predict(request)

    def test_old_additive_lifecycle_module_is_unmodified(self):
        import lifecycle
        from compiled_inference import CompiledAdditiveModel
        self.assertIs(lifecycle.load_backend().SpectralModel, CompiledAdditiveModel)
        self.assertIs(bandwidth_lifecycle.load_backend().SpectralModel, BandwidthAdditiveModel)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
import json, tempfile, unittest
from pathlib import Path
import verify_current_successor_source_closure as v

class ClosureVerifierTests(unittest.TestCase):
    def test_current_checkout_passes(self):
        root=Path(__file__).resolve().parents[2]
        out=v.verify(root)
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(out["stages"],49)
        self.assertEqual(out["prediction_edges"],172)
        self.assertEqual(out["source_files_checked"],251)
        self.assertFalse(out["private_prediction_arrays_read"])

    def test_tampered_source_fails(self):
        root=Path(__file__).resolve().parents[2]
        receipt=json.loads((root/"evidence/current_successor_source_closure_20261006.json").read_text(encoding="utf-8"))
        first=receipt["stages"][0]["stage"]
        fr=json.loads((root/"study"/first/"FREEZE.json").read_text(encoding="utf-8"))
        rel=next(iter(fr["source_sha256"]))
        original=(root/rel).read_bytes()
        with tempfile.TemporaryDirectory() as td:
            # This is a focused hash primitive test, avoiding a full repo copy.
            p=Path(td)/"x"
            p.write_bytes(original+b"tamper")
            self.assertNotEqual(v.sha(p),fr["source_sha256"][rel])

if __name__=="__main__":
    unittest.main()

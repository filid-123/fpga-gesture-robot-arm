import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


MODULE_PATH = Path(__file__).with_name("phase2_l2_live_view.py")
SPEC = importlib.util.spec_from_file_location("phase2_l2_live_view_tested", MODULE_PATH)
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)


class _Result:
    def __init__(self, returncode):
        self.returncode = returncode


class LiveViewHelperTests(unittest.TestCase):
    def test_roi_mapping_matches_floor_rule(self):
        frame = np.arange(128 * 128, dtype=np.uint16).reshape(128, 128).astype(np.uint8)
        box = (11, 17, 76, 82)
        actual = live.reconstruct_same_frame_roi(frame, box)
        offsets = (np.arange(32) * 65) // 32
        expected = frame[17 + offsets[:, None], 11 + offsets[None, :]]
        np.testing.assert_array_equal(actual, expected)

    def test_roi_rejects_invalid_geometry(self):
        frame = np.zeros((128, 128), dtype=np.uint8)
        for box in ((0, 0, 10, 9), (-1, 0, 4, 5), (0, 0, 129, 129)):
            with self.assertRaises(ValueError):
                live.reconstruct_same_frame_roi(frame, box)

    def test_light_metrics_ignore_fixed_letterbox_padding(self):
        frame = np.full((128, 128), 255, dtype=np.uint8)
        frame[16:112, :] = 80
        metrics = live.frame_light_metrics(frame)
        self.assertEqual(metrics["mean"], 80.0)
        self.assertEqual(metrics["std"], 0.0)
        self.assertEqual(metrics["bright_pct"], 0.0)

    def test_artifact_hash_lock_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bit = root / "pair.bit"
            hwh = root / "pair.hwh"
            bit.write_bytes(b"bit")
            hwh.write_bytes(b"hwh")
            with self.assertRaises(RuntimeError):
                live.validate_artifact_pair(bit, hwh)
            actual = live.validate_artifact_pair(bit, hwh, allow_unverified=True)
            self.assertEqual(actual["bit"], hashlib.sha256(b"bit").hexdigest())

    def test_artifacts_require_same_basename(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bit, hwh = root / "a.bit", root / "b.hwh"
            bit.write_bytes(b"bit")
            hwh.write_bytes(b"hwh")
            with self.assertRaises(ValueError):
                live.validate_artifact_pair(bit, hwh, allow_unverified=True)

    def test_service_guard_rejects_current_autostart(self):
        def runner(command, **_kwargs):
            return _Result(0 if command[-1] == "gesture-demo-sameframe128.service" else 3)

        with self.assertRaisesRegex(RuntimeError, "sameframe128"):
            live.require_services_stopped(runner)

    def test_service_guard_accepts_inactive_services(self):
        live.require_services_stopped(lambda *_args, **_kwargs: _Result(3))

    def test_cli_validation(self):
        with self.assertRaises(SystemExit):
            live.parse_args(["--deploy-dir", ".", "--jpeg-quality", "0"])
        with self.assertRaises(SystemExit):
            live.parse_args(["--deploy-dir", ".", "--no-save", "--result-dir", "x"])

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV unavailable")
    def test_preview_geometry(self):
        import cv2

        frame = np.zeros((128, 128), dtype=np.uint8)
        roi = np.zeros((32, 32), dtype=np.uint8)
        preview = live.compose_preview(
            cv2, frame, roi,
            raw_box=(1, 2, 20, 30), stable_box=(2, 3, 21, 31),
            crop_box=(0, 0, 40, 40), lines=("ok",),
        )
        self.assertEqual(preview.shape, (660, 900, 3))
        self.assertEqual(preview.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()

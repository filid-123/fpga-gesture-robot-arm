import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

import phase2_l1_failure_capture as capture


class FailureCaptureTests(unittest.TestCase):
    def test_selection_rules_keep_locator_and_classifier_failures_separate(self):
        self.assertEqual(
            capture.decide_sample_type(
                truth="no_hand",
                threshold_passed=True,
                locator_usable=True,
                raw_class_id=0,
                correct_ordinal=0,
                correct_control_every=20,
            ),
            "locator_false_positive",
        )
        self.assertIsNone(
            capture.decide_sample_type(
                truth="no_hand",
                threshold_passed=False,
                locator_usable=False,
                raw_class_id=None,
                correct_ordinal=0,
                correct_control_every=20,
            )
        )
        self.assertEqual(
            capture.decide_sample_type(
                truth="mute",
                threshold_passed=False,
                locator_usable=False,
                raw_class_id=None,
                correct_ordinal=0,
                correct_control_every=20,
            ),
            "locator_false_negative",
        )
        self.assertEqual(
            capture.decide_sample_type(
                truth="fist",
                threshold_passed=True,
                locator_usable=True,
                raw_class_id=3,
                correct_ordinal=0,
                correct_control_every=20,
            ),
            "classifier_misclassification",
        )
        self.assertEqual(
            capture.decide_sample_type(
                truth="palm",
                threshold_passed=True,
                locator_usable=True,
                raw_class_id=3,
                correct_ordinal=20,
                correct_control_every=20,
            ),
            "correct_control",
        )
        self.assertIsNone(
            capture.decide_sample_type(
                truth="palm",
                threshold_passed=True,
                locator_usable=True,
                raw_class_id=3,
                correct_ordinal=21,
                correct_control_every=20,
            )
        )

    def test_safe_component_rejects_empty_and_normalizes_path_characters(self):
        self.assertEqual(capture.safe_component("mute far/left 01"), "mute_far_left_01")
        with self.assertRaises(ValueError):
            capture.safe_component("中文会话")

    def test_sample_artifacts_are_lossless_and_raw_map_is_exact(self):
        class PillowCv2:
            IMWRITE_JPEG_QUALITY = 1

            @staticmethod
            def imwrite(path, array, params=None):
                del params
                Image.fromarray(np.asarray(array, dtype=np.uint8)).save(path)
                return True

        with tempfile.TemporaryDirectory() as temporary:
            sample_dir = Path(temporary) / "sample"
            source = np.arange(48, dtype=np.uint8).reshape(6, 8)
            locator_input = np.arange(128 * 128, dtype=np.uint16).astype(np.uint8).reshape(128, 128)
            raw = np.arange(5 * 16 * 16, dtype=np.int32).reshape(5, 16, 16) - 640
            roi = np.arange(32 * 32, dtype=np.uint16).astype(np.uint8).reshape(32, 32)
            preview = np.zeros((6, 8, 3), dtype=np.uint8)
            metadata = capture.save_sample_artifacts(
                cv2=PillowCv2,
                sample_dir=sample_dir,
                source_gray_u8=source,
                locator_input_u8=locator_input,
                conv5_raw_i32=raw,
                classifier_roi_u8=roi,
                preview_bgr=preview,
                metadata={"failure_type": "classifier_misclassification"},
            )
            np.testing.assert_array_equal(
                np.asarray(Image.open(sample_dir / "source_gray.png")),
                source,
            )
            np.testing.assert_array_equal(
                np.asarray(Image.open(sample_dir / "locator_input_128x128.png")),
                locator_input,
            )
            np.testing.assert_array_equal(
                np.asarray(Image.open(sample_dir / "classifier_roi_32x32.png")),
                roi,
            )
            self.assertEqual((sample_dir / "conv5_raw_i32.bin").stat().st_size, 5120)
            np.testing.assert_array_equal(
                np.fromfile(sample_dir / "conv5_raw_i32.bin", dtype="<i4").reshape(5, 16, 16),
                raw,
            )
            self.assertEqual(metadata["artifacts"]["conv5_raw_i32.bin"]["bytes"], 5120)
            self.assertEqual(
                metadata["artifacts"]["preview.jpg"]["training_use"],
                "forbidden_annotated_review_only",
            )

    def test_package_contains_manifest_and_passes_zip_crc(self):
        with tempfile.TemporaryDirectory() as temporary:
            session_dir = Path(temporary) / "session_test"
            session_dir.mkdir()
            (session_dir / "payload.bin").write_bytes(b"hard-sample")
            capture.write_json(session_dir / "session.json", {"status": "COMPLETE"})
            result = capture.package_session(session_dir, create_zip=True)

            manifest = json.loads(
                (session_dir / "sha256_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["format"], capture.FORMAT_VERSION)
            self.assertEqual(manifest["file_count"], 2)
            self.assertEqual(result["manifest_entries"], 2)
            self.assertEqual(result["zip_sha256"], capture.sha256_file(Path(result["zip"])))
            with zipfile.ZipFile(result["zip"], "r") as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn(
                    "session_test/sha256_manifest.json", archive.namelist()
                )
                self.assertIn("session_test/payload.bin", archive.namelist())


if __name__ == "__main__":
    unittest.main()

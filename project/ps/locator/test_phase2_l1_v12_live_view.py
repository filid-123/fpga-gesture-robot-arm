import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import phase2_l1_v12_live_view as live
import phase2_l1_v16_v3_live_view as live_v16_v3


class LiveViewHelperTests(unittest.TestCase):
    def test_nearest_rank_p95(self):
        summary = live.summarize(range(20))
        self.assertEqual(summary["min"], 0.0)
        self.assertEqual(summary["p95"], 18.0)
        self.assertEqual(summary["max"], 19.0)

    def test_rounded_draw_box_clips_and_rejects_invalid_geometry(self):
        self.assertEqual(
            live.rounded_draw_box((-5.2, 3.4, 700.0, 500.0), 640, 480),
            ((0, 3), (639, 479)),
        )
        self.assertIsNone(live.rounded_draw_box((5, 5, 5, 20), 640, 480))
        self.assertIsNone(live.rounded_draw_box(None, 640, 480))

    def test_status_lines_expose_decision_and_timing(self):
        line1, line2 = live.make_status_lines(
            "HOLD", -4252, -3336, "mute", "mute", 1, 133.4, 7.2
        )
        self.assertIn("HOLD", line1)
        self.assertIn("raw=-4252", line1)
        self.assertIn("cls=mute->mute", line1)
        self.assertIn("miss=1", line1)
        self.assertIn("pipeline=133.4 ms", line2)
        self.assertIn("live=7.2 FPS", line2)

    def test_v16_v3_status_lines_use_delivered_threshold(self):
        line1, _ = live_v16_v3.make_status_lines(
            "DETECT", -226, -1901, "fist", "fist", 0, 100.0, 5.0
        )
        self.assertIn("raw=-226", line1)
        self.assertIn("threshold=-1901", line1)
        self.assertIn("cls=fist->fist", line1)

    def test_v16_v3_no_save_mode_has_no_result_paths(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(
                live_v16_v3.resolve_result_paths(
                    "", Path(directory), "20260819_000000", True
                ),
                (None, None),
            )
            with self.assertRaisesRegex(ValueError, "cannot be combined"):
                live_v16_v3.resolve_result_paths(
                    "result.json", Path(directory), "20260819_000000", True
                )

    def test_v16_v3_recording_mode_retains_json_and_preview_paths(self):
        with TemporaryDirectory() as directory:
            result, preview = live_v16_v3.resolve_result_paths(
                "", Path(directory), "20260819_000000", False
            )
            self.assertEqual(result.name, "phase2_l1_v16_v3_live_view_20260819_000000.json")
            self.assertEqual(
                preview.name,
                "phase2_l1_v16_v3_live_view_20260819_000000_last.png",
            )


if __name__ == "__main__":
    unittest.main()

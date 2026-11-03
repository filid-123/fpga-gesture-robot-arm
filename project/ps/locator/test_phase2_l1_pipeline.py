import unittest
from pathlib import Path

import numpy as np

import phase2_l1_pipeline as pipeline


class Phase2L1PipelineTests(unittest.TestCase):
    @staticmethod
    def _official_package():
        return (
            Path(__file__).resolve().parents[2]
            / "quantized_locator_v12"
            / "quantized_locator_v12"
        )

    @staticmethod
    def _official_v16_package():
        return (
            Path(__file__).resolve().parents[2]
            / "quantized_locator_v16_failure_adaptation"
        )

    def test_letterbox_geometry_for_640x480(self):
        spec = pipeline.LetterboxSpec(
            target_width=128,
            target_height=128,
            pad_value=0,
            interpolation="nearest",
            resize_rounding="half_up",
            odd_padding="top_left_floor",
        )
        transform = pipeline.compute_letterbox_transform(640, 480, spec)
        self.assertEqual((transform.resized_width, transform.resized_height), (128, 96))
        self.assertEqual(
            (transform.pad_left, transform.pad_top, transform.pad_right, transform.pad_bottom),
            (0, 16, 0, 16),
        )

    def test_little_endian_chw_parse(self):
        words = np.arange(pipeline.LOCATOR_OUTPUT_WORDS, dtype=np.int32)
        parsed = pipeline.parse_raw_output_i32(words.astype("<i4").tobytes())
        self.assertEqual(parsed.shape, (5, 16, 16))
        self.assertEqual(int(parsed[4, 15, 15]), pipeline.LOCATOR_OUTPUT_WORDS - 1)

    def test_uint32_words_are_reinterpreted_as_signed(self):
        words = np.zeros(pipeline.LOCATOR_OUTPUT_WORDS, dtype=np.uint32)
        words[0] = np.uint32(0xFFFF_FFFF)
        parsed = pipeline.parse_raw_output_i32(words)
        self.assertEqual(int(parsed[0, 0, 0]), -1)

    def test_top1_decode_and_inverse_letterbox(self):
        raw = np.zeros((5, 16, 16), dtype=np.int32)
        raw[0].fill(-1000)
        raw[0, 5, 7] = 300
        raw[1, 5, 7] = 25
        raw[2, 5, 7] = -25
        raw[3, 5, 7] = 50
        raw[4, 5, 7] = 25
        decode_spec = pipeline.RawDecodeSpec(
            accumulator_scales=(0.01, 0.01, 0.01, 0.01, 0.01),
            confidence_threshold_i32=200,
            clamp_to_locator=False,
        )
        detection = pipeline.decode_top1_raw_map(raw, decode_spec)
        self.assertEqual((detection.cell_x, detection.cell_y), (7, 5))
        self.assertTrue(detection.passed_threshold)
        self.assertTrue(detection.valid_geometry)
        np.testing.assert_allclose(detection.bbox_locator_xyxy, (30.0, 26.0, 94.0, 58.0))

        letterbox_spec = pipeline.LetterboxSpec(128, 128, 0, "nearest", "half_up", "top_left_floor")
        transform = pipeline.compute_letterbox_transform(640, 480, letterbox_spec)
        source_box = pipeline.locator_bbox_to_source(
            detection.bbox_locator_xyxy, transform, clip_to_source=True
        )
        np.testing.assert_allclose(source_box, (150.0, 50.0, 470.0, 210.0))

    def test_official_v12_manifest_and_positive_negative_goldens(self):
        package = self._official_package()
        spec = pipeline.raw_decode_spec_from_manifest(
            package / "locator_quantization_manifest.json", clamp_to_locator=True
        )
        self.assertEqual(spec.confidence_threshold_i32, -3336)
        golden = package / "golden_vectors_v1"
        hand = np.fromfile(
            golden / "dataset_test_hand_index_000000" / "conv5_acc_i32.bin",
            dtype="<i4",
        )
        no_hand = np.fromfile(
            golden / "dataset_test_no_hand_index_011084" / "conv5_acc_i32.bin",
            dtype="<i4",
        )
        hand_detection = pipeline.decode_top1_raw_map(hand, spec)
        no_hand_detection = pipeline.decode_top1_raw_map(no_hand, spec)
        self.assertEqual((hand_detection.cell_x, hand_detection.cell_y), (5, 5))
        self.assertEqual(hand_detection.confidence_i32, 271)
        self.assertTrue(hand_detection.passed_threshold)
        self.assertEqual((no_hand_detection.cell_x, no_hand_detection.cell_y), (15, 8))
        self.assertEqual(no_hand_detection.confidence_i32, -10566)
        self.assertFalse(no_hand_detection.passed_threshold)

    def test_official_v16_manifest_and_positive_negative_goldens(self):
        package = self._official_v16_package()
        spec = pipeline.raw_decode_spec_from_manifest(
            package / "locator_quantization_manifest.json", clamp_to_locator=True
        )
        self.assertEqual(spec.confidence_threshold_i32, -1901)
        golden = package / "golden_vectors_v16"
        hand = np.fromfile(
            golden / "dataset_test_hand_index_000000" / "conv5_acc_i32.bin",
            dtype="<i4",
        )
        no_hand = np.fromfile(
            golden / "dataset_test_no_hand_index_011084" / "conv5_acc_i32.bin",
            dtype="<i4",
        )
        hand_detection = pipeline.decode_top1_raw_map(hand, spec)
        no_hand_detection = pipeline.decode_top1_raw_map(no_hand, spec)
        self.assertEqual((hand_detection.cell_x, hand_detection.cell_y), (5, 5))
        self.assertEqual(hand_detection.confidence_i32, -226)
        self.assertTrue(hand_detection.passed_threshold)
        self.assertEqual((no_hand_detection.cell_x, no_hand_detection.cell_y), (15, 8))
        self.assertEqual(no_hand_detection.confidence_i32, -11115)
        self.assertFalse(no_hand_detection.passed_threshold)
        for raw_map, decoded in ((hand, hand_detection), (no_hand, no_hand_detection)):
            raw_map = raw_map.reshape(5, 16, 16)
            flat_index = int(np.argmax(raw_map[0]))
            cell_y, cell_x = divmod(flat_index, 16)
            summary = pipeline.decode_top1_raw_values(
                cell_x,
                cell_y,
                tuple(
                    int(raw_map[channel, cell_y, cell_x]) for channel in range(5)
                ),
                spec,
            )
            self.assertEqual(summary, decoded)

    def test_invalid_regression_geometry_is_not_a_box(self):
        raw = np.zeros((5, 16, 16), dtype=np.int32)
        raw[0, 2, 3] = 10
        raw[3, 2, 3] = -1
        raw[4, 2, 3] = 5
        spec = pipeline.RawDecodeSpec(
            accumulator_scales=(1.0, 1.0, 1.0, 1.0, 1.0),
            confidence_threshold_i32=0,
            clamp_to_locator=True,
        )
        detection = pipeline.decode_top1_raw_map(raw, spec)
        self.assertFalse(detection.valid_geometry)
        self.assertIsNone(detection.bbox_locator_xyxy)

    def test_center_square_matches_existing_phase1_rule(self):
        self.assertEqual(
            pipeline.center_square_box(640, 480, scale=0.45),
            (212, 132, 428, 348),
        )

    def test_explicit_bbox_expansion_without_square(self):
        self.assertEqual(
            pipeline.prepare_source_crop_box(
                (150.0, 50.0, 470.0, 210.0),
                640,
                480,
                expansion_ratio=0.1,
                make_square=False,
                clip_to_source=True,
            ),
            (118, 34, 502, 226),
        )

    def test_square_bbox_is_shifted_inside_without_changing_side(self):
        with self.assertRaises(ValueError):
            pipeline.prepare_source_crop_box(
                (150.0, 50.0, 470.0, 210.0),
                640,
                480,
                expansion_ratio=0.0,
                make_square=True,
                clip_to_source=False,
            )
        self.assertEqual(
            pipeline.prepare_source_crop_box(
                (150.0, 50.0, 470.0, 210.0),
                640,
                480,
                expansion_ratio=0.0,
                make_square=True,
                clip_to_source=True,
            ),
            (150, 0, 470, 320),
        )

    def test_frozen_18_percent_roi_uses_round_and_bottom_shift(self):
        box = pipeline.prepare_source_crop_box(
            (335.39892594173494, 227.6723649983433, 486.9114793435881, 456.31702763671814),
            640,
            480,
            expansion_ratio=0.18,
            make_square=True,
            clip_to_source=True,
        )
        self.assertEqual(box, (256, 169, 567, 480))
        self.assertEqual(box[2] - box[0], box[3] - box[1])

    def test_square_side_is_limited_by_short_image_dimension(self):
        box = pipeline.prepare_source_crop_box(
            (0.0, 0.0, 1000.0, 900.0),
            640,
            480,
            expansion_ratio=0.18,
            make_square=True,
            clip_to_source=True,
        )
        self.assertEqual(box, (160, 0, 640, 480))

    def test_square_contract_uses_python_ties_to_even_rounding(self):
        # 25 * 1.06 = 26.5. Python round selects the even side 26; a
        # half-up implementation would incorrectly select 27.
        box = pipeline.prepare_source_crop_box(
            (100.0, 100.0, 125.0, 110.0),
            640,
            480,
            expansion_ratio=0.03,
            make_square=True,
            clip_to_source=True,
        )
        self.assertEqual(box, (100, 92, 126, 118))
        self.assertEqual(box[2] - box[0], 26)

    def test_bbox_ema_and_three_frame_hold(self):
        spec = pipeline.TemporalFilterSpec(bbox_ema_alpha=0.25, miss_hold_frames=3)
        tracker = pipeline.BboxEmaHold(spec)
        first = tracker.update((0.0, 0.0, 10.0, 10.0))
        self.assertEqual(first.bbox_xyxy, (0.0, 0.0, 10.0, 10.0))
        filtered = tracker.update((4.0, 8.0, 14.0, 18.0))
        self.assertEqual(filtered.bbox_xyxy, (1.0, 2.0, 11.0, 12.0))
        for expected_miss in (1, 2, 3):
            held = tracker.update(None)
            self.assertTrue(held.held)
            self.assertEqual(held.miss_count, expected_miss)
            self.assertEqual(held.bbox_xyxy, filtered.bbox_xyxy)
        expired = tracker.update(None)
        self.assertFalse(expired.held)
        self.assertIsNone(expired.bbox_xyxy)
        self.assertEqual(expired.miss_count, 4)

    def test_class_vote_requires_two_confirmed_vote_results(self):
        spec = pipeline.TemporalFilterSpec(class_vote_window=5, class_switch_frames=2)
        voter = pipeline.ClassVoteSwitch(spec)
        first = voter.update(2)
        self.assertEqual(first.voted_class, 2)
        self.assertIsNone(first.output_class)
        second = voter.update(2)
        self.assertEqual(second.output_class, 2)

        self.assertEqual(voter.update(3).output_class, 2)
        self.assertEqual(voter.update(3).output_class, 2)
        pending = voter.update(3)
        self.assertEqual(pending.voted_class, 3)
        self.assertEqual(pending.output_class, 2)
        switched = voter.update(3)
        self.assertEqual(switched.output_class, 3)

        voter.reset()
        self.assertIsNone(voter.output_class)

    def test_l2_class_confirm_uses_gesture_2_background_3_none_3(self):
        switch = pipeline.ClassConfirmSwitch(pipeline.TemporalFilterSpec())

        first_fist = switch.update(1)
        self.assertIsNone(first_fist.output_class)
        self.assertEqual((first_fist.pending_count, first_fist.required_count), (1, 2))
        self.assertEqual(switch.update(1).output_class, 1)

        self.assertEqual(switch.update(3).output_class, 1)
        self.assertEqual(switch.update(3).output_class, 3)

        self.assertEqual(switch.update(0).output_class, 3)
        second_background = switch.update(0)
        self.assertEqual(second_background.output_class, 3)
        self.assertEqual((second_background.pending_count, second_background.required_count), (2, 3))
        self.assertEqual(switch.update(0).output_class, 0)

        self.assertEqual(switch.update(None).output_class, 0)
        self.assertEqual(switch.update(None).output_class, 0)
        self.assertIsNone(switch.update(None).output_class)

    def test_l2_class_confirm_requires_consecutive_candidates(self):
        switch = pipeline.ClassConfirmSwitch(pipeline.TemporalFilterSpec())
        self.assertIsNone(switch.update(1).output_class)
        interrupted = switch.update(2)
        self.assertIsNone(interrupted.output_class)
        self.assertEqual((interrupted.pending_class, interrupted.pending_count), (2, 1))
        self.assertEqual(switch.update(2).output_class, 2)


if __name__ == "__main__":
    unittest.main()

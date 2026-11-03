"""Meaningful metric-derivation checks; no camera, board, GPU or private data needed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'metrics/scripts/recover_recorded_metrics.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveredMetrics(unittest.TestCase):
    def review(self):
        return json.loads((ROOT / 'report/acceptance/task_outcomes_review_20261101.json').read_bytes())

    def acceptance(self):
        return json.loads((ROOT / 'report/acceptance/board_test_20261101.json').read_bytes())

    def test_operator_counts_give_16_of_17_not_program_counter_100_percent(self):
        result = recovery.task_summary(self.review(), self.acceptance())
        self.assertEqual((result['successes'], result['failures'], result['attempts']), (16, 1, 17))
        self.assertAlmostEqual(result['success_rate_pct'], 1600 / 17)

    def test_wrong_operator_denominator_rejected(self):
        review = self.review()
        review['groups'][2].update(attempts=7, successes=6)
        with self.assertRaises(ValueError):
            recovery.task_summary(review, self.acceptance())

    def test_close_excluded_but_failure_latency_retained(self):
        rows = [{'operation': 'R', 'ok': True, 'roundtrip_ms': 1.},
                {'operation': 'R', 'ok': True, 'roundtrip_ms': 3.},
                {'operation': 'R', 'ok': False, 'roundtrip_ms': 1000.},
                {'operation': 'CLOSE', 'ok': True, 'roundtrip_ms': .1}]
        result = recovery.rpc_summary(rows)
        self.assertEqual(result['attempts'], 3)
        self.assertEqual(result['excluded_close_records'], 1)
        self.assertAlmostEqual(result['command_error_rate_pct'], 100 / 3)
        self.assertEqual(result['all_attempts_rtt_ms']['max'], 1000.)
        self.assertEqual(result['successful_rtt_ms']['max'], 3.)

    def test_nonfinite_rtt_rejected(self):
        with self.assertRaises(ValueError):
            recovery.stats([1., float('nan')])

    def test_frozen_550_predictions_reproduce_confusions_and_quality(self):
        rows = recovery.model_predictions(ROOT)
        result = recovery.quality_summary(rows)
        self.assertEqual((result['samples'], result['correct']), (550, 503))
        self.assertEqual((result['hands'], result['correct_hands']), (490, 443))
        self.assertAlmostEqual(result['macro_f1'], .9230474275302606)
        # A rejected "one" must not become a correct accepted gesture just because top-1 was one.
        self.assertTrue(any(r['truth'] == 'one' and not r['detected'] and r['integer_class'] == 'one'
                            and r['predicted_action'] == 'background' for r in rows))

    def test_macro_f1_with_gate_rejection_differs_from_accuracy(self):
        rows = [{'group': 'synthetic', 'truth': name, 'predicted_action': name, 'detected': name != 'background'}
                for name in recovery.CLASSES]
        rows[1].update(predicted_action='background', detected=False)
        result = recovery.quality_summary(rows)
        self.assertAlmostEqual(result['accuracy_pct'], 500 / 6)
        self.assertAlmostEqual(result['macro_f1'], (2 / 3 + 4) / 6)

    def test_board_cycles_convert_to_ms_and_zero_class_counter_is_not_inference(self):
        rows = [{'locator_cycles': 1647640, 'classifier_cycles': 0, 'observations': 135},
                {'locator_cycles': 1647640, 'classifier_cycles': 468486, 'observations': 24311}]
        result = recovery.fpga_summary(rows, 100_000_000)
        self.assertEqual(result['telemetry_observations'], 24446)
        self.assertEqual(result['classifier_zero_observations'], 135)
        self.assertAlmostEqual(result['cnn_service_sum_ms'], 21.16126)

    def test_variable_execution_cycles_cannot_be_silently_reported_as_constant(self):
        rows = [{'locator_cycles': 1, 'classifier_cycles': 1, 'observations': 1},
                {'locator_cycles': 2, 'classifier_cycles': 1, 'observations': 1}]
        with self.assertRaises(ValueError):
            recovery.fpga_summary(rows, 100_000_000)

    def test_wrong_private_telemetry_hash_stops_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'report/acceptance').mkdir(parents=True)
            for name in ('task_outcomes_review_20261101.json', 'board_test_20261101.json'):
                (base / 'report/acceptance' / name).write_bytes((ROOT / 'report/acceptance' / name).read_bytes())
            folder = base / 'runs' / self.acceptance()['sessions'][0]['run']
            folder.mkdir(parents=True)
            (folder / 'telemetry.jsonl').write_text('{}\n')
            with self.assertRaises(ValueError):
                recovery.recover(base, base / 'runs', base / 'out')
            self.assertFalse((base / 'out').exists())

    def test_changed_public_evidence_csv_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'rpc_samples.csv').write_bytes(b'changed')
            (folder / 'summary.json').write_text(json.dumps({'public_csv_sha256': {
                'rpc_samples.csv': hashlib.sha256(b'original').hexdigest()}}))
            with self.assertRaises(ValueError):
                recovery.verify_public(ROOT, folder)


if __name__ == '__main__':
    unittest.main()

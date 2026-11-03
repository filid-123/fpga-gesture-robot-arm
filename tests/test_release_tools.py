"""Offline behavioural checks for reusable tools. All hardware examples here are synthetic."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


environment = load('skill/amd-pc-deploy/scripts/probe_environment.py', 'environment_probe')
artifacts = load('skill/fpga-artifact-check/scripts/verify_artifacts.py', 'artifact_probe')
metrics = load('skill/robotics-metrics/scripts/summarize.py', 'metric_probe')
restore = load('tools/restore_assets.py', 'asset_restore')


def sha(content):
    return hashlib.sha256(content).hexdigest()


class Temporary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path


class Environment(Temporary):
    def test_empty_probe_labels_gpu_and_inference_not_run(self):
        result = environment.inspect()
        self.assertTrue(result['passed'])
        self.assertEqual(result['hip']['status'], 'NOT_RUN')
        self.assertEqual(result['model_inference'], 'NOT_RUN')

    def test_dependency_exact_version(self):
        req = self.write('lock.txt', '# explicit lock\nexample_pkg==1.2.3\n')
        with patch.object(environment.importlib.metadata, 'version', return_value='1.2.3'):
            self.assertTrue(environment.inspect([req])['passed'])

    def test_dependency_mismatch_is_not_pass(self):
        req = self.write('lock.txt', 'example_pkg==1.2.3\n')
        with patch.object(environment.importlib.metadata, 'version', return_value='2.0.0'):
            self.assertFalse(environment.inspect([req])['passed'])

    def test_pip_options_require_explicit_handling(self):
        req = self.write('lock.txt', '--extra-index-url https://example.invalid\n')
        with self.assertRaises(ValueError):
            environment.inspect([req])

    def model(self, name='model.bin', expected=None):
        content = b'opaque synthetic model, not inference weights'
        (self.root / 'model.bin').write_bytes(content)
        return self.write('model.json', json.dumps({'onnx': {'file': name, 'sha256': expected or sha(content)}}))

    def test_declared_model_hash(self):
        self.assertTrue(environment.inspect(models=[self.model()])['passed'])

    def test_changed_model_rejected(self):
        self.assertFalse(environment.inspect(models=[self.model(expected='0' * 64)])['passed'])

    def test_model_directory_escape_rejected(self):
        with self.assertRaises(ValueError):
            environment.inspect(models=[self.model(name='../outside.bin')])

    def test_skill_script_has_no_repository_import_dependency(self):
        path = self.root / 'standalone.py'
        shutil.copyfile(ROOT / 'skill/amd-pc-deploy/scripts/probe_environment.py', path)
        spec = importlib.util.spec_from_file_location('standalone_probe', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(module.inspect()['passed'])


class Artifacts(Temporary):
    def setUp(self):
        super().setUp()
        self.write('src/design.v', '// synthetic design for manifest testing\n')
        self.write('hardware/demo.bit', 'synthetic BIT; never program this\n')
        self.write('hardware/demo.hwh', '<synthetic/>\n')
        with zipfile.ZipFile(self.root / 'hardware/demo.xsa', 'w') as archive:
            for name in ('demo.bit', 'demo.hwh'):
                archive.write(self.root / 'hardware' / name, name)
        sources = {'files': {'src/design.v': sha((self.root / 'src/design.v').read_bytes())}}
        self.write('sources.json', json.dumps(sources))
        self.summary = {'source_binding_sha256': sha((self.root / 'sources.json').read_bytes()),
                        'timing_ns': {'WNS': .1, 'WHS': .1, 'TNS': 0, 'THS': 0},
                        'drc_errors': 0, 'cdc_endpoints': 2, 'cdc_safe': 2,
                        'cdc_unsafe': 0, 'cdc_unknown': 0, 'artifacts': {}}
        self.rebind_artifacts()

    def rebind_artifacts(self):
        for path in (self.root / 'hardware').iterdir():
            self.summary['artifacts'][path.name] = {'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}
        self.write('summary.json', json.dumps(self.summary))

    def check(self):
        self.write('summary.json', json.dumps(self.summary))
        return artifacts.verify(self.root, 'summary.json', 'sources.json')

    def test_second_synthetic_project_schema_passes(self):
        self.assertTrue(self.check()['passed'])

    def test_source_tamper_rejected(self):
        self.write('src/design.v', '// altered')
        with self.assertRaises(ValueError):
            self.check()

    def test_unbound_source_manifest_rejected(self):
        self.summary['source_binding_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.check()

    def test_hold_failure_rejected(self):
        self.summary['timing_ns']['WHS'] = -.001
        with self.assertRaises(ValueError):
            self.check()

    def test_nan_not_accepted_as_timing(self):
        self.summary['timing_ns']['WNS'] = float('nan')
        with self.assertRaises(ValueError):
            self.check()

    def test_unknown_cdc_rejected(self):
        self.summary['cdc_unknown'] = 1
        with self.assertRaises(ValueError):
            self.check()

    def test_explicit_no_cdc_design_supported(self):
        self.summary.update(cdc_endpoints=0, cdc_safe=0)
        self.assertTrue(self.check()['passed'])

    def test_fractional_cdc_count_rejected(self):
        self.summary.update(cdc_endpoints=1.5, cdc_safe=1.5)
        with self.assertRaises(ValueError):
            self.check()

    def test_drc_error_rejected(self):
        self.summary['drc_errors'] = 1
        with self.assertRaises(ValueError):
            self.check()

    def test_xsa_from_different_build_rejected_even_with_new_outer_hash(self):
        with zipfile.ZipFile(self.root / 'hardware/demo.xsa', 'w') as archive:
            archive.writestr('demo.bit', 'different build')
            archive.write(self.root / 'hardware/demo.hwh', 'demo.hwh')
        self.rebind_artifacts()
        with self.assertRaises(ValueError):
            self.check()

    def test_directory_escape_rejected(self):
        with self.assertRaises(ValueError):
            artifacts.local(self.root, '../other')


class Metrics(Temporary):
    def run_metric(self, content, kind='latency', **kwargs):
        path = self.write('observations.csv', content)
        return metrics.summarize(path, kind, 'synthetic test only', 'synthetic', **kwargs)

    def test_known_linear_percentiles(self):
        result = self.run_metric('duration_ms\n0\n10\n20\n30\n', start='synthetic start', end='synthetic end')
        self.assertEqual(result['timing_ms']['duration_ms']['p50'], 15)
        self.assertAlmostEqual(result['timing_ms']['duration_ms']['p95'], 28.5)
        self.assertEqual(result['timing_ms']['duration_ms']['max'], 30)
        self.assertEqual(result['evidence_kind'], 'synthetic')

    def test_missing_physical_endpoints_rejected(self):
        with self.assertRaises(ValueError):
            self.run_metric('duration_ms\n1\n')

    def test_empty_input_is_not_zero_latency(self):
        with self.assertRaises(ValueError):
            self.run_metric('duration_ms\n', start='a', end='b')

    def test_nonfinite_timing_rejected(self):
        for value in ('nan', 'inf', '-1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_metric('duration_ms\n' + value + '\n', kind='rtt')

    def test_interventions_remain_in_denominator(self):
        result = self.run_metric('outcome\nsuccess\nfailure\nintervention\n', kind='task')
        self.assertEqual(result['samples'], 3)
        self.assertAlmostEqual(result['success_rate'], 1 / 3)

    def test_missing_task_outcome_rejected(self):
        with self.assertRaises(ValueError):
            self.run_metric('outcome\nsuccess\n\nunknown\n', kind='task')

    def test_batch_one_components(self):
        result = self.run_metric('batch,preprocess_ms,inference_ms,postprocess_ms,total_ms\n1,1,2,3,7\n', kind='inference')
        self.assertEqual(result['timing_ms']['inference_ms']['max'], 2)

    def test_wrong_batch_rejected(self):
        with self.assertRaises(ValueError):
            self.run_metric('batch,preprocess_ms,inference_ms,postprocess_ms,total_ms\n2,1,2,3,7\n', kind='inference')

    def test_inconsistent_total_rejected(self):
        with self.assertRaises(ValueError):
            self.run_metric('batch,preprocess_ms,inference_ms,postprocess_ms,total_ms\n1,1,2,3,5\n', kind='inference')


class Restore(Temporary):
    def fixture(self, name='images/synthetic.bin'):
        archive = self.root / 'baseline.zip'
        content = b'synthetic excluded asset'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr(name, content)
        inventory = {'archive_sha256': sha(archive.read_bytes()), 'members': [
            {'path': name, 'bytes': len(content), 'sha256': sha(content), 'git_included': False}]}
        self.write('report/provenance/source_archive_inventory.json', json.dumps(inventory))
        return archive

    def test_exact_archive_restores_and_is_idempotent(self):
        archive = self.fixture()
        self.assertEqual(restore.restore(self.root, archive)['restored_assets'], 1)
        self.assertEqual(restore.restore(self.root, archive)['restored_assets'], 0)

    def test_wrong_archive_hash_rejected_before_write(self):
        archive = self.fixture()
        archive.write_bytes(archive.read_bytes() + b'changed')
        with self.assertRaises(ValueError):
            restore.restore(self.root, archive)
        self.assertFalse((self.root / 'project').exists())

    def test_existing_different_asset_preserved(self):
        archive = self.fixture()
        path = self.write('project/images/synthetic.bin', 'local work')
        with self.assertRaises(ValueError):
            restore.restore(self.root, archive)
        self.assertEqual(path.read_text(), 'local work')

    def test_zip_traversal_rejected(self):
        archive = self.fixture('../../outside.bin')
        with self.assertRaises(ValueError):
            restore.restore(self.root, archive)


if __name__ == '__main__':
    unittest.main()

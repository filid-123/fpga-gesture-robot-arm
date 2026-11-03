"""Integration checks on the actual release, including independently extracted use."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'docs/phase3c/mode_b_teammate_handoff_20261028'
spec = importlib.util.spec_from_file_location('handoff_verifier', ROOT/'scripts/verify_mode_b_teammate_handoff.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class HandoffTests(unittest.TestCase):
    def test_independent_zip_cli_and_no_repository_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(PACKAGE.with_suffix('.zip')) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(tmp)
            folder = Path(tmp)/PACKAGE.name
            result = subprocess.run([sys.executable, '-B', str(folder/'verify.py')],
                                    cwd=tmp, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report['hardware_accessed'])
            self.assertEqual([x['requests'] for x in report['objects']], [1789, 1794, 1206])

    def test_good_board_exports_match(self):
        folder = PACKAGE/'objects/eraser'
        report = verifier.verify(PACKAGE, folder/'sequence.jsonl', 'eraser', folder/'motion_q16.mem')
        self.assertTrue(report['passed'])

    def test_truncated_board_motion_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'board.mem'
            lines = (PACKAGE/'objects/eraser/motion_q16.mem').read_text().splitlines()
            file.write_text('\n'.join(lines[:-1]))
            with self.assertRaisesRegex(ValueError, 'PL motion samples mismatch'):
                verifier.verify(PACKAGE, object_class='eraser', pl_samples=file)

    def test_missing_release_event_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'board.jsonl'
            rows = verifier.rows(PACKAGE/'objects/eraser/sequence.jsonl')
            file.write_text('\n'.join(json.dumps(x) for x in rows if x['label'] != 'RELEASE'))
            with self.assertRaisesRegex(ValueError, 'observed request count differs'):
                verifier.verify(PACKAGE, observed=file, object_class='eraser')

    def test_file_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'package'
            shutil.copytree(PACKAGE, folder)
            with (folder/'HOME.json').open('a') as stream:
                stream.write(' ')
            with self.assertRaisesRegex(ValueError, 'File hash/size mismatch'):
                verifier.verify(folder)

    def test_regenerated_manifest_cannot_hide_wrong_event_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'package'
            shutil.copytree(PACKAGE, folder)
            relative = 'objects/eraser/sequence.jsonl'
            file = folder/relative
            rows = verifier.rows(file)
            event = next(x for x in rows if x['label'] == 'CLOSE_SOURCE')
            event['wire_json'] = '{"T":106,"cmd":1.586,"spd":300,"acc":20}'
            file.write_text('\n'.join(json.dumps(x) for x in rows)+'\n', encoding='utf-8')
            manifest = verifier.read(folder/'MANIFEST.json')
            manifest['files'][relative] = {'sha256': verifier.digest(file), 'bytes': file.stat().st_size}
            (folder/'MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'gripper event differs'):
                verifier.verify(folder)

    def test_signed_q16_order_and_tie_rule(self):
        command = dict(zip(verifier.WIRE_NAMES, [-1, 1/65536, -.5, 0, 2, .5/65536]))
        self.assertEqual(verifier.q16_hex(command),
                         '000000000002000000000000ffff800000000001ffff0000')


if __name__ == '__main__':
    unittest.main()

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from prepare_mode_b_restock_session import compile_session, read

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/phase3c/mode_b_return_20261029/red_speed2_v1'


class RestockSessionTest(unittest.TestCase):
    def test_every_wire_matches_physically_accepted_result(self):
        packet = compile_session(BASE/'RESTOCK_PLAN.json', BASE/'COPPELIA_VERIFICATION.json', BASE/'ACCEPTED_SPEED2.json')
        accepted = read(BASE/'ACCEPTED_SPEED2.json')
        result = read(accepted['result_file'])
        self.assertEqual([w for op in packet['operations'] for w in op['wires']],
                         [r['wire_json'] for r in result['requests']])
        self.assertEqual(packet['requests'], 3835)
        self.assertEqual(packet['nominal_motion_seconds'], 76.62)
        self.assertEqual(hashlib.sha256(''.join(r['wire_json']+'\n' for r in result['requests']).encode()).hexdigest(),
                         packet['ordered_wire_lf_sha256'])

    def test_other_simulation_and_unaccepted_result_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'changed.json'
            sim = read(BASE/'COPPELIA_VERIFICATION.json')
            sim['route_sha256'] = '0'*64
            path.write_text(json.dumps(sim), 'utf8')
            with self.assertRaisesRegex(ValueError, 'mesh'):
                compile_session(BASE/'RESTOCK_PLAN.json', path, BASE/'ACCEPTED_SPEED2.json')
            acceptance = read(BASE/'ACCEPTED_SPEED2.json')
            acceptance['result_sha256'] = '0'*64
            path.write_text(json.dumps(acceptance), 'utf8')
            with self.assertRaisesRegex(ValueError, 'operator acceptance'):
                compile_session(BASE/'RESTOCK_PLAN.json', BASE/'COPPELIA_VERIFICATION.json', path)


if __name__ == '__main__':
    unittest.main()

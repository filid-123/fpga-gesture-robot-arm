"""Overlay hash verification and backup/reseal, using disposable fake packages."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from apply_mode_b_full_workspace import install
sha=lambda d:hashlib.sha256(d).hexdigest()


class Tests(unittest.TestCase):
    def fixture(self,root):
        target=root/'target';bundle=root/'bundle';target.mkdir();bundle.mkdir()
        old=b'old source\n';new=b'new source\n';config=b'{"maximum_additional_grasp_tilt_deg":10}\n'
        (target/'source.py').write_bytes(old)
        (target/'mode_ab_manifest.json').write_text(json.dumps(dict(patch_id='planning_ux_giao_p3',task_abi=0x340d,inputs={'source.py':sha(old)})))
        (target/'sha256sums.txt').write_text('original placeholder fixture')
        data={'source.py':new,'config/ai_pc/mode_b_full_workspace_20261030.json':config}
        files={}
        for n,d in data.items():
            p=bundle/'payload'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(d)
            files[n]=dict(sha256=sha(d),base_sha256=sha(old) if n=='source.py' else None,
                base_lf_sha256=sha(old) if n=='source.py' else None)
        (bundle/'patch_manifest.json').write_text(json.dumps(dict(files=files)))
        (bundle/'pc_tests.json').write_text('{"passed":true,"hardware_access":false}')
        return bundle,target

    def test_preflight_changes_nothing_apply_backs_up_and_reseals(self):
        with tempfile.TemporaryDirectory() as d:
            bundle,target=self.fixture(Path(d));before=(target/'mode_ab_manifest.json').read_bytes()
            r=install(bundle,target);self.assertFalse(r['applied']);self.assertEqual((target/'mode_ab_manifest.json').read_bytes(),before)
            r=install(bundle,target,apply=True,profile='strict');self.assertTrue(r['applied']);self.assertTrue(Path(r['backup']).exists())
            m=json.loads((target/'mode_ab_manifest.json').read_bytes());self.assertEqual(m['patch_id'],'full_workspace_policy_p4')
            for n,h in m['inputs'].items():self.assertEqual(sha((target/n).read_bytes()),h)
            c=json.loads((target/'config/ai_pc/mode_b_full_workspace_20261030.json').read_bytes())
            self.assertEqual(c['maximum_additional_grasp_tilt_deg'],10);self.assertEqual(c['maximum_grasp_tcp_raise_mm'],0)

    def test_changed_base_is_rejected_before_creating_backup_or_writing(self):
        with tempfile.TemporaryDirectory() as d:
            bundle,target=self.fixture(Path(d));(target/'source.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Base package changed'):install(bundle,target,apply=True)
            self.assertFalse((target/'backups').exists());self.assertEqual((target/'source.py').read_bytes(),b'changed')


if __name__=='__main__':unittest.main()

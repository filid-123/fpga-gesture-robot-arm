"""Transfer/packing/adapter regression using frozen collision-checked tasks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.export import load_package
from pc.mode_b.motion.fpga_review import (build_review, compare_samples, encode_sample,
    load_blocks, read_samples, verify_adapter, verify_review)

EXAMPLES = ROOT/"docs/phase3c/mode_b_motion_20261027/continuity_v2_260_160_30/examples"


class FpgaReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temp.name)/"handoff"
        cls.handoff = build_review(ROOT, EXAMPLES, cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_signed_channel_order_and_int32_edges(self):
        row = (1, -1, -(1 << 31), (1 << 31)-1, 0, -2)
        self.assertEqual(encode_sample(row), "FFFFFFFE000000007FFFFFFF80000000FFFFFFFF00000001")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"sample.mem"
            path.write_text("// comment\n"+encode_sample(row)+" // inline\n", encoding="ascii")
            self.assertEqual(read_samples(path), [row])
        for row in ([0]*5, [0]*5+[True], [0]*5+[1 << 31]):
            with self.assertRaises(ValueError):
                encode_sample(row)

    def test_all_twelve_routes_and_sample_totals_verified(self):
        result = verify_review(self.bundle)
        self.assertTrue(result["passed"])
        self.assertEqual(result["routes"], 12)
        self.assertEqual(result["samples"], 4234+6281)
        self.assertFalse(result["physical_execution_allowed"])
        self.assertEqual(self.handoff["destination"]["support_centre_mm"], [260, 160, 30])

    def test_blocks_keep_every_event_across_capacity_boundary(self):
        plan, _ = load_package(EXAMPLES/"eraser/complete_task.json")
        for route in (plan, *plan["cancel_branches"].values()):
            chunks = load_blocks(plan, route)
            self.assertTrue(all(1 <= len(c["segments"]) <= 32 for c in chunks))
            self.assertEqual([s for c in chunks for s in c["segments"]], route["segments"])
            for previous, following in zip(chunks, chunks[1:]):
                self.assertEqual(previous["segments"][-1]["target_q16"], following["start_q16"])
                self.assertTrue(following["requires_previous_chunk_done"])

    def test_adapter_route_tampering_rejected(self):
        plan, _ = load_package(EXAMPLES/"red_cube/complete_task.json")
        adapter = json.loads((EXAMPLES/"red_cube/fpga_adapter_draft.json").read_text())
        for mutate in (lambda a: a.update(physical_execution_allowed=True),
                       lambda a: a["chunks"][0]["segments"][0]["target_q16"].__setitem__(0, 123),
                       lambda a: a["cancel_branches"].pop("BUFFER")):
            broken = deepcopy(adapter)
            mutate(broken)
            with self.assertRaises(ValueError):
                verify_adapter(plan, broken)

    def test_sample_compare_rejects_missing_extra_and_changed_words(self):
        expected = self.bundle/"tasks/red_cube/normal_samples_192.mem"
        rows = read_samples(expected)
        with tempfile.TemporaryDirectory() as folder:
            actual = Path(folder)/"actual.mem"
            for altered in (rows[:-1], rows+[rows[-1]], [tuple([rows[0][0]+1, *rows[0][1:]]), *rows[1:]]):
                actual.write_text("\n".join(encode_sample(row) for row in altered)+"\n", encoding="ascii")
                self.assertFalse(compare_samples(expected, actual)["passed"])
            actual.write_text("x"*48, encoding="ascii")
            with self.assertRaises(ValueError):
                compare_samples(expected, actual)

    def test_manifest_detects_changed_or_extra_file(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder)/"copy"
            shutil.copytree(self.bundle, copy)
            (copy/"untracked_file.txt").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "hash set"):
                verify_review(copy)

    def test_rehashed_wrong_block_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder)/"copy"
            shutil.copytree(self.bundle, copy)
            rel = "tasks/red_cube/load_blocks.json"
            path = copy/rel
            data = json.loads(path.read_text())
            data["routes"]["normal"]["chunks"][1]["start_q16"][0] += 1
            path.write_text(json.dumps(data))
            manifest = json.loads((copy/"MANIFEST.json").read_text())
            manifest["files"][rel] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
            (copy/"MANIFEST.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Load blocks"):
                verify_review(copy)

    def test_transferred_checker_cli_is_self_contained(self):
        result = subprocess.run([sys.executable, "-B", str(self.bundle/"review_tools/scripts/build_mode_b_fpga_review.py"),
            "--verify", str(self.bundle)], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()

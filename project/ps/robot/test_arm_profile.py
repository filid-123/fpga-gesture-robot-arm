import copy
import tempfile
import unittest
from pathlib import Path

import yaml

import arm_profile as ap


CONFIG = ap.find_config_root()
PROFILES = CONFIG / "arm_profiles"


def load_raw(name):
    return yaml.safe_load((PROFILES / name).read_text(encoding="utf-8"))


class TempProfile:
    """Write a modified profile next to the real ones so relative paths work."""

    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", dir=PROFILES, delete=False, encoding="utf-8"
        )
        yaml.safe_dump(self.raw, handle, sort_keys=False)
        handle.close()
        self.path = Path(handle.name)
        return self.path

    def __exit__(self, *_exc):
        self.path.unlink(missing_ok=True)


class ShippedProfileTests(unittest.TestCase):
    def test_all_shipped_profiles_load(self):
        names = sorted(p.name for p in PROFILES.glob("*.yaml"))
        self.assertEqual(
            names,
            [
                "bench_loopback_roarm_json.yaml",
                "bench_loopback_so101.yaml",
                "roarm_m3_binary_bridge.yaml",
                "roarm_m3_pro.yaml",
                "so_arm101_follower.yaml",
            ],
        )
        for path in PROFILES.glob("*.yaml"):
            profile = ap.ArmProfile.load(path)
            self.assertEqual(len(profile.joints), 6)

    def test_real_profiles_default_to_blocked(self):
        for name in ("roarm_m3_pro.yaml", "so_arm101_follower.yaml", "roarm_m3_binary_bridge.yaml"):
            profile = ap.ArmProfile.load(PROFILES / name)
            self.assertFalse(profile.real_output_enabled)
            self.assertFalse(profile.mapping_complete())
            reasons = profile.missing_for_real_output()
            self.assertIn("real_output_enabled is false", reasons)
            self.assertIn("joints[0].zero_device is TBD", reasons)
            self.assertIn("calibration.source_files is empty (need measured data with SHA-256)", reasons)
            with self.assertRaises(ap.ProfileError):
                profile.channel_maps()

    def test_so101_requires_ids_and_half_duplex(self):
        reasons = ap.ArmProfile.load(PROFILES / "so_arm101_follower.yaml").missing_for_real_output()
        self.assertIn("joints[5].device_id is TBD", reasons)
        self.assertIn("transport.half_duplex.lead_us is TBD", reasons)
        self.assertIn("timeouts.response_timeout_ms is TBD", reasons)
        self.assertIn("transport.baudrate is TBD", reasons)

    def test_bench_profiles_are_complete_but_never_robot(self):
        for name in ("bench_loopback_roarm_json.yaml", "bench_loopback_so101.yaml"):
            profile = ap.ArmProfile.load(PROFILES / name)
            self.assertTrue(profile.bench_only)
            self.assertTrue(profile.mapping_complete())
            self.assertIn("bench_only profile can never drive a robot", profile.missing_for_real_output())
            self.assertEqual(profile.device_range_violations(), [])
            self.assertEqual(len(profile.channel_maps()), 6)

    def test_protocol_path_is_resolved_relative_to_profile(self):
        profile = ap.ArmProfile.load(PROFILES / "roarm_m3_pro.yaml")
        self.assertTrue(profile.protocol_file.exists())
        self.assertEqual(profile.protocol_file.name, "roarm_m3_json_protocol.yaml")


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.raw = load_raw("bench_loopback_so101.yaml")

    def load_modified(self, mutate):
        raw = copy.deepcopy(self.raw)
        mutate(raw)
        with TempProfile(raw) as path:
            return ap.ArmProfile.load(path)

    def test_unknown_and_missing_keys_rejected(self):
        with self.assertRaisesRegex(ap.ProfileError, "unknown keys"):
            self.load_modified(lambda r: r.__setitem__("extra", 1))
        with self.assertRaisesRegex(ap.ProfileError, "missing keys"):
            self.load_modified(lambda r: r["joints"][0].pop("zero_device"))

    def test_channel_order_and_roles_are_frozen(self):
        def swap(raw):
            raw["joints"][0], raw["joints"][1] = raw["joints"][1], raw["joints"][0]
        with self.assertRaisesRegex(ap.ProfileError, "fixed order"):
            self.load_modified(swap)
        with self.assertRaisesRegex(ap.ProfileError, "role"):
            self.load_modified(lambda r: r["joints"][2].__setitem__("role", "gripper"))

    def test_only_8n1_supported(self):
        with self.assertRaisesRegex(ap.ProfileError, "8N1"):
            self.load_modified(lambda r: r["transport"].__setitem__("parity", "E"))

    def test_duplicate_so101_ids_rejected(self):
        with self.assertRaisesRegex(ap.ProfileError, "unique"):
            self.load_modified(lambda r: r["joints"][1].__setitem__("device_id", 21))

    def test_sim_urdf_limits_are_rejected_as_physical_limits(self):
        def urdf(raw):
            for joint, (low, high) in zip(raw["joints"], ap.ROARM_SIM_URDF_LIMITS_RAD):
                joint["soft_min_rad"], joint["soft_max_rad"] = low, high
            raw["device_encoding"]["device_min"] = -100000
            raw["device_encoding"]["device_max"] = 100000
        profile = self.load_modified(urdf)
        self.assertTrue(profile.uses_sim_urdf_limits())
        self.assertTrue(any("URDF" in r for r in profile.missing_for_real_output()))

    def test_simulation_is_not_a_calibration_method(self):
        with self.assertRaisesRegex(ap.ProfileError, "calibration.method"):
            self.load_modified(lambda r: r["calibration"].__setitem__("method", "urdf"))

    def test_device_range_violation_reported(self):
        profile = self.load_modified(lambda r: r["device_encoding"].__setitem__("device_max", 3000))
        problems = profile.device_range_violations()
        self.assertTrue(problems)
        self.assertTrue(any("outside [0, 3000]" in p for p in problems))

    def test_unit_scale_below_one_rejected(self):
        with self.assertRaisesRegex(ap.ProfileError, ">= 1.0"):
            self.load_modified(lambda r: r["joints"][0].__setitem__("device_units_per_rad", 0.5))

    def test_calibration_hash_checked(self):
        with tempfile.NamedTemporaryFile("wb", dir=PROFILES, suffix=".csv", delete=False) as data:
            data.write(b"measured\n")
        source = Path(data.name)
        try:
            def calibrated(raw):
                raw["calibration"]["source_files"] = [{"path": source.name, "sha256": "00" * 32}]
            reasons = self.load_modified(calibrated).missing_for_real_output()
            self.assertIn(f"calibration source SHA-256 mismatch: {source.name}", reasons)

            def good(raw):
                raw["calibration"]["source_files"] = [{"path": source.name, "sha256": ap.sha256_file(source)}]
            reasons = self.load_modified(good).missing_for_real_output()
            self.assertFalse(any("calibration source" in r for r in reasons))
        finally:
            source.unlink()


if __name__ == "__main__":
    unittest.main()

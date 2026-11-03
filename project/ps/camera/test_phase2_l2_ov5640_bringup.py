import importlib
import sys
import types
import unittest
from unittest import mock


fake_pynq = types.ModuleType("pynq")
fake_pynq.Overlay = object
with mock.patch.dict(sys.modules, {"pynq": fake_pynq}):
    bringup = importlib.import_module("phase2_l2_ov5640_bringup")


class BringupGuardTests(unittest.TestCase):
    def test_rejects_active_legacy_service(self):
        results = [
            types.SimpleNamespace(stdout="active\n"),
            types.SimpleNamespace(stdout="enabled\n"),
        ]
        with mock.patch.object(bringup.subprocess, "run", side_effect=results):
            with self.assertRaisesRegex(RuntimeError, "stopped and disabled"):
                bringup.require_autostart_stopped()

    def test_accepts_inactive_legacy_service(self):
        results = [
            types.SimpleNamespace(stdout="inactive\n"),
            types.SimpleNamespace(stdout="disabled\n"),
        ]
        with mock.patch.object(bringup.subprocess, "run", side_effect=results):
            bringup.require_autostart_stopped()

    def test_rejects_inactive_but_enabled_service(self):
        results = [
            types.SimpleNamespace(stdout="inactive\n"),
            types.SimpleNamespace(stdout="enabled\n"),
        ]
        with mock.patch.object(bringup.subprocess, "run", side_effect=results):
            with self.assertRaisesRegex(RuntimeError, "stopped and disabled"):
                bringup.require_autostart_stopped()


if __name__ == "__main__":
    unittest.main(verbosity=2)

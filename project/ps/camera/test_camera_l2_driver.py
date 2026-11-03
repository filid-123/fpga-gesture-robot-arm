import tempfile
import unittest
from pathlib import Path

import numpy as np

import camera_l2_driver as cd
import phase2_l2_headless as headless


class FakeCameraMMIO:
    def __init__(self):
        self.array = np.zeros(cd.CAMERA_CTRL_SIZE // 4, dtype=np.uint32)
        self.array[cd.ABI_VERSION // 4] = cd.CAMERA_ABI_VERSION
        self.array[cd.STATUS // 4] = cd.STATUS_XCLK_LOCKED | cd.STATUS_PWDN
        self.registers = {0x300A: 0x56, 0x300B: 0x40}
        self.debug_words = np.zeros(cd.FRAME_WORDS * 2, dtype=np.uint32)

    def read(self, offset):
        if offset == cd.DEBUG_WORD_DATA:
            address = int(self.array[cd.DEBUG_WORD_ADDRESS // 4])
            return int(self.debug_words[address])
        return int(self.array[offset // 4])

    def write(self, offset, value):
        value &= 0xFFFF_FFFF
        if offset == cd.CONTROL:
            self.array[offset // 4] = value
            status = int(self.array[cd.STATUS // 4]) & ~(
                cd.STATUS_CAPTURE_ENABLE | cd.STATUS_SOURCE_CAMERA |
                cd.STATUS_RESET_N | cd.STATUS_PWDN
            )
            status |= value & 0x3
            status |= cd.STATUS_RESET_N if value & cd.CTRL_RESET_N else 0
            status |= cd.STATUS_PWDN if value & cd.CTRL_PWDN else 0
            self.array[cd.STATUS // 4] = status
        elif offset == cd.CLEAR_STATUS:
            status = int(self.array[cd.STATUS // 4])
            status &= ~(
                cd.STATUS_SCCB_DONE | cd.STATUS_SCCB_ACK_ERROR | cd.STATUS_SCCB_READ_VALID
            ) & 0xFFFF_FFFF
            self.array[cd.STATUS // 4] = status
        elif offset == cd.SCCB_START:
            address = int(self.array[cd.SCCB_ADDRESS // 4]) & 0xFFFF
            if value == 3:
                self.array[cd.SCCB_DATA // 4] = self.registers.get(address, 0)
                self.array[cd.STATUS // 4] |= cd.STATUS_SCCB_READ_VALID
            else:
                self.registers[address] = int(self.array[cd.SCCB_DATA // 4]) & 0xFF
            self.array[cd.STATUS // 4] |= cd.STATUS_SCCB_DONE
        elif offset == cd.BUFFER_RELEASE:
            status = int(self.array[cd.STATUS // 4])
            status &= ~((value & 0x3) << cd.STATUS_BUFFER_VALID_SHIFT) & 0xFFFF_FFFF
            self.array[cd.STATUS // 4] = status
        else:
            self.array[offset // 4] = value


class FlakyCameraInitialization:
    def __init__(self, failures):
        self.failures = failures
        self.power_on_calls = 0
        self.configure_calls = 0
        self.shutdown_calls = 0

    def power_on(self):
        self.power_on_calls += 1

    def assert_chip_id(self):
        return cd.OV5640_CHIP_ID

    def configure_vga_yuyv(self):
        self.configure_calls += 1
        if self.failures:
            self.failures -= 1
            raise OSError("OV5640 did not acknowledge the SCCB transaction")

    def shutdown(self):
        self.shutdown_calls += 1


class CameraL2DriverTests(unittest.TestCase):
    def setUp(self):
        self.mmio = FakeCameraMMIO()
        self.delays = []
        self.driver = cd.CameraL2Driver(self.mmio, sleeper=self.delays.append)

    def test_safe_power_sequence_and_chip_id_read(self):
        self.driver.power_on()
        self.assertEqual(self.delays, [0.005, 0.001, 0.020])
        self.assertEqual(self.mmio.read(cd.CONTROL), cd.CTRL_RESET_N)
        self.assertEqual(self.driver.assert_chip_id(), 0x5640)

    def test_vga_profile_matches_rtl_byte_phase_and_geometry(self):
        self.driver.power_on()
        self.driver.configure_vga_yuyv()
        self.assertEqual(self.mmio.registers[0x4740], 0x00)
        self.assertEqual(self.mmio.registers[0x4300], 0x30)
        self.assertEqual(self.mmio.registers[0x3808], 0x02)
        self.assertEqual(self.mmio.registers[0x3809], 0x80)
        self.assertEqual(self.mmio.registers[0x380A], 0x01)
        self.assertEqual(self.mmio.registers[0x380B], 0xE0)
        self.assertEqual(self.mmio.registers[0x3008], 0x02)

    def test_headless_camera_init_recovers_one_sccb_nack(self):
        camera = FlakyCameraInitialization(failures=1)
        delays = []
        retries = []
        chip_id = headless.initialize_camera_with_retry(
            camera, sleeper=delays.append, on_retry=retries.append
        )
        self.assertEqual(chip_id, cd.OV5640_CHIP_ID)
        self.assertEqual(camera.power_on_calls, 2)
        self.assertEqual(camera.configure_calls, 2)
        self.assertEqual(camera.shutdown_calls, 1)
        self.assertEqual(delays, [headless.CAMERA_INIT_RETRY_DELAY_S])
        self.assertEqual(len(retries), 1)

    def test_headless_camera_init_rejects_persistent_sccb_nack(self):
        camera = FlakyCameraInitialization(failures=3)
        delays = []
        with self.assertRaisesRegex(OSError, "did not acknowledge"):
            headless.initialize_camera_with_retry(
                camera, sleeper=delays.append, on_retry=lambda _message: None
            )
        self.assertEqual(camera.power_on_calls, 3)
        self.assertEqual(camera.configure_calls, 3)
        self.assertEqual(camera.shutdown_calls, 3)
        self.assertEqual(
            delays,
            [headless.CAMERA_INIT_RETRY_DELAY_S] * 2,
        )

    def test_frame_readback_and_release(self):
        pixels = np.arange(cd.FRAME_PIXELS, dtype=np.uint8).reshape(128, 128)
        self.mmio.debug_words[: cd.FRAME_WORDS] = np.frombuffer(
            pixels.tobytes(), dtype="<u4"
        )
        self.mmio.array[cd.FRAME_ID_0 // 4] = 7
        self.mmio.array[cd.STATUS // 4] |= (
            1 << cd.STATUS_BUFFER_VALID_SHIFT
        ) | cd.STATUS_FRAME_PUBLISHED

        frame = self.driver.acquire()
        self.assertEqual((frame.buffer_id, frame.frame_id), (0, 7))
        np.testing.assert_array_equal(frame.image_u8, pixels)
        self.driver.release_buffer(0)
        self.assertEqual(self.driver.status()["buffer_valid_mask"], 0)

        with tempfile.TemporaryDirectory() as directory:
            path = cd.write_pgm(Path(directory) / "frame.pgm", pixels)
            self.assertTrue(path.read_bytes().startswith(b"P5\n128 128\n255\n"))

    def test_fresh_capture_and_shutdown_release_ownership(self):
        self.driver.power_on()
        self.mmio.array[cd.STATUS // 4] |= (
            0x3 << cd.STATUS_BUFFER_VALID_SHIFT
        ) | cd.STATUS_FRAME_PUBLISHED
        self.driver.prepare_capture(camera_source=True)
        state = self.driver.status()
        self.assertTrue(state["capture_enabled"])
        self.assertTrue(state["source_camera"])
        self.assertEqual(state["buffer_valid_mask"], 0)

        self.mmio.array[cd.STATUS // 4] |= 1 << cd.STATUS_BUFFER_VALID_SHIFT
        self.driver.shutdown()
        state = self.driver.status()
        self.assertFalse(state["capture_enabled"])
        self.assertFalse(state["reset_n"])
        self.assertTrue(state["pwdn"])
        self.assertEqual(state["buffer_valid_mask"], 0)

    def test_next_frame_roi_descriptor_and_completion(self):
        self.driver.power_on()
        self.driver.enable_capture(camera_source=True)
        self.driver.arm_roi((73, 41, 196, 164), descriptor_tag=0x1122_3344)
        self.assertEqual(self.mmio.read(cd.ROI_XY), 0x0029_0049)
        self.assertEqual(self.mmio.read(cd.ROI_SIZE), 123)
        self.assertEqual(self.mmio.read(cd.ROI_TAG), 0x1122_3344)
        self.assertEqual(
            self.mmio.read(cd.ROI_CONTROL),
            cd.ROI_CTRL_ARM | cd.ROI_CTRL_CLASSIFIER_SOURCE,
        )

        self.mmio.array[cd.ROI_STATUS // 4] = (
            cd.ROI_STATUS_CLASSIFIER_SOURCE | cd.ROI_STATUS_DONE
        )
        self.mmio.array[cd.ROI_DONE_TAG // 4] = 0x1122_3344
        self.mmio.array[cd.ROI_SOURCE_FRAME_ID // 4] = 9
        result = self.driver.wait_roi(descriptor_tag=0x1122_3344)
        self.assertEqual(
            (result.descriptor_tag, result.source_frame_id),
            (0x1122_3344, 9),
        )

    def test_roi_rejects_nonstreamable_geometry(self):
        with self.assertRaises(ValueError):
            self.driver.arm_roi((0, 0, 31, 31), descriptor_tag=1)
        with self.assertRaises(ValueError):
            self.driver.arm_roi((610, 440, 650, 480), descriptor_tag=2)

    def test_same_frame_roi_holds_selected_buffer_identity(self):
        self.driver.power_on()
        self.driver.enable_capture(camera_source=True)
        self.mmio.array[cd.STATUS // 4] |= 2 << cd.STATUS_BUFFER_VALID_SHIFT
        self.mmio.array[cd.FRAME_ID_1 // 4] = 42

        self.driver.arm_same_frame_roi(
            1, (11, 9, 84, 82), descriptor_tag=0x55AA_0080
        )
        self.assertEqual(self.mmio.read(cd.ROI_XY), 0x0009_000B)
        self.assertEqual(self.mmio.read(cd.ROI_SIZE), 73)
        self.assertEqual(
            self.mmio.read(cd.ROI_CONTROL),
            cd.ROI_CTRL_ARM
            | cd.ROI_CTRL_CLASSIFIER_SOURCE
            | cd.ROI_CTRL_SAME_FRAME
            | cd.ROI_CTRL_BUFFER_ID,
        )

        self.mmio.array[cd.ROI_STATUS // 4] = (
            cd.ROI_STATUS_CLASSIFIER_SOURCE | cd.ROI_STATUS_DONE
        )
        self.mmio.array[cd.ROI_DONE_TAG // 4] = 0x55AA_0080
        self.mmio.array[cd.ROI_SOURCE_FRAME_ID // 4] = 42
        result = self.driver.wait_roi(
            descriptor_tag=0x55AA_0080, source_frame_id=42
        )
        self.assertEqual(result.source_frame_id, 42)
        with self.assertRaisesRegex(RuntimeError, "source frame mismatch"):
            self.driver.wait_roi(
                descriptor_tag=0x55AA_0080, source_frame_id=41
            )

    def test_same_frame_roi_rejects_invalid_buffer_or_geometry(self):
        with self.assertRaisesRegex(RuntimeError, "not valid"):
            self.driver.arm_same_frame_roi(0, (0, 0, 16, 16), descriptor_tag=1)
        with self.assertRaises(ValueError):
            self.driver.arm_same_frame_roi(1, (120, 120, 129, 129), descriptor_tag=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import unittest
import zlib
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

import numpy as np

import locator_driver as ld


class FakeMMIO:
    def __init__(self, words):
        self.array = np.zeros(words, dtype=np.uint32)

    def read(self, offset):
        return int(self.array[offset // 4])

    def write(self, offset, value):
        self.array[offset // 4] = np.uint32(value)


class FakeLocatorControl(FakeMMIO):
    def __init__(self, input_mmio, output_mmio):
        super().__init__(ld.LOCATOR_CTRL_SIZE // 4)
        self.input = input_mmio
        self.output = output_mmio
        self.array[ld.ABI_VERSION // 4] = ld.LOCATOR_ABI_VERSION
        self.array[ld.STATUS // 4] = ld.STATUS_IDLE
        self.array[ld.INPUT_FREE_MASK // 4] = 0x3
        self.array[ld.TOP1_CAPABILITY // 4] = ld.TOP1_CAPABILITY_MAGIC

    def write(self, offset, value):
        value &= 0xFFFF_FFFF
        if offset == ld.CONTROL:
            self._command(value)
        elif offset == ld.OUTPUT_RELEASE:
            valid = int(self.array[ld.OUTPUT_VALID_MASK // 4])
            if value & ~valid:
                self.array[ld.STATUS // 4] |= ld.STATUS_ERROR
                self.array[ld.ERROR_CODE // 4] = 0x06
            else:
                self.array[ld.OUTPUT_VALID_MASK // 4] = valid & ~value
                if not (valid & ~value):
                    self.array[ld.STATUS // 4] = (
                        int(self.array[ld.STATUS // 4]) & ~ld.STATUS_DONE & 0xFFFF_FFFF
                    )
        else:
            super().write(offset, value)

    def _command(self, command):
        if command == ld.CMD_MODEL_COMMIT:
            model_count = self.read(ld.MODEL_WORD_COUNT)
            desc_count = self.read(ld.DESC_WORD_COUNT)
            model = self.array[ld.MODEL_WINDOW // 4 : ld.MODEL_WINDOW // 4 + model_count]
            desc = self.array[ld.DESC_WINDOW // 4 : ld.DESC_WINDOW // 4 + desc_count]
            model_crc = ld.crc32_words(model)
            desc_crc = ld.crc32_words(desc)
            self.array[ld.COMPUTED_MODEL_CRC // 4] = model_crc
            self.array[ld.COMPUTED_DESC_CRC // 4] = desc_crc
            if (
                model_count == ld.MODEL_WORDS
                and 1 <= desc_count <= ld.MAX_DESC_WORDS
                and model_crc == self.read(ld.EXPECTED_MODEL_CRC)
                and desc_crc == self.read(ld.EXPECTED_DESC_CRC)
            ):
                self.array[ld.STATUS // 4] = ld.STATUS_IDLE | ld.STATUS_MODEL_VALID
            else:
                self.array[ld.STATUS // 4] = ld.STATUS_IDLE | ld.STATUS_MODEL_ERROR
                self.array[ld.ERROR_CODE // 4] = 0x0C
        elif command == ld.CMD_START:
            input_id = self.read(ld.INPUT_BUFFER_ID)
            frame_id = self.read(ld.INPUT_FRAME_ID)
            valid = self.read(ld.OUTPUT_VALID_MASK) & 0x3
            if valid == 0x3:
                self.array[ld.STATUS // 4] |= ld.STATUS_ERROR
                self.array[ld.ERROR_CODE // 4] = 0x05
                return
            output_id = 0 if not valid & 1 else 1
            input_start = input_id * ld.INPUT_BUFFER_STRIDE_WORDS
            input_words = self.input.array[
                input_start : input_start + ld.INPUT_WORDS_PER_BUFFER
            ]
            checksum = int(np.bitwise_xor.reduce(input_words, dtype=np.uint32))
            output_words = (
                np.arange(ld.OUTPUT_WORDS, dtype=np.uint32)
                ^ np.uint32(checksum)
                ^ np.uint32(frame_id)
            )
            output_start = output_id * ld.OUTPUT_BUFFER_STRIDE_WORDS
            self.output.array[output_start : output_start + ld.OUTPUT_WORDS] = output_words
            raw_map = output_words.view(np.int32).reshape(5, 16, 16)
            flat_index = int(np.argmax(raw_map[0]))
            cell_y, cell_x = divmod(flat_index, 16)
            top1_base = ld.TOP1_CELL_0 if output_id == 0 else ld.TOP1_CELL_1
            self.array[top1_base // 4] = flat_index
            for channel in range(5):
                self.array[top1_base // 4 + 1 + channel] = (
                    int(raw_map[channel, cell_y, cell_x]) & 0xFFFF_FFFF
                )
            self.array[(ld.OUTPUT_FRAME_ID_0 if output_id == 0 else ld.OUTPUT_FRAME_ID_1) // 4] = frame_id
            self.array[ld.OUTPUT_BUFFER_ID // 4] = output_id
            self.array[ld.OUTPUT_VALID_MASK // 4] = valid | (1 << output_id)
            self.array[ld.INPUT_FREE_MASK // 4] = 0x3
            self.array[ld.STATUS // 4] = (
                ld.STATUS_IDLE | ld.STATUS_DONE | ld.STATUS_MODEL_VALID
            )
        elif command == ld.CMD_CLEAR_ERROR:
            self.array[ld.STATUS // 4] = (
                int(self.array[ld.STATUS // 4]) & ~ld.STATUS_ERROR & 0xFFFF_FFFF
            )
            self.array[ld.ERROR_CODE // 4] = 0
        elif command == ld.CMD_CLEAR_IRQ:
            self.array[ld.IRQ_STATUS // 4] = 0
        elif command == ld.CMD_SOFT_RESET:
            model = self.read(ld.STATUS) & ld.STATUS_MODEL_VALID
            self.array[ld.STATUS // 4] = ld.STATUS_IDLE | model
            self.array[ld.INPUT_FREE_MASK // 4] = 0x3
            self.array[ld.OUTPUT_VALID_MASK // 4] = 0


class LocatorDriverTests(unittest.TestCase):
    def setUp(self):
        self.input = FakeMMIO(ld.LOCATOR_INPUT_SIZE // 4)
        self.output = FakeMMIO(ld.LOCATOR_OUTPUT_SIZE // 4)
        self.ctrl = FakeLocatorControl(self.input, self.output)
        self.driver = ld.LocatorDriver(self.ctrl, self.input, self.output)

    def test_crc_standard_vector_and_little_endian_words(self):
        data = b"123456789\0\0\0"
        words = np.frombuffer(data, dtype="<u4")
        self.assertEqual(ld.crc32_words(words), zlib.crc32(data) & 0xFFFF_FFFF)
        self.assertEqual(ld.crc32_words([0x34333231, 0x38373635]), zlib.crc32(b"12345678"))

    def test_pack_input_is_little_endian_and_exact_size(self):
        image = np.arange(ld.INPUT_PIXELS, dtype=np.uint8).reshape(128, 128)
        words = ld.pack_input_u8(image)
        self.assertEqual(words.size, ld.INPUT_WORDS_PER_BUFFER)
        self.assertEqual(int(words[0]), 0x03020100)
        self.assertEqual(int(words[-1]), 0xFFFEFDFC)
        with self.assertRaises(ValueError):
            ld.pack_input_u8(np.zeros((32, 32), dtype=np.uint8))
        with self.assertRaises(TypeError):
            ld.pack_input_u8(np.zeros((128, 128), dtype=np.float32))

    def test_model_commit_two_buffers_frame_id_and_bit_exact_stub(self):
        self.driver.assert_abi()
        model, desc = ld.make_stub_payload()
        self.driver.load_model(model, desc, model_version=1, desc_version=1)
        self.assertTrue(self.driver.read(ld.STATUS) & ld.STATUS_MODEL_VALID)

        image0 = np.arange(ld.INPUT_PIXELS, dtype=np.uint8).reshape(128, 128)
        image1 = np.full((128, 128), 0x5A, dtype=np.uint8)
        result0 = self.driver.run_stub(image0, 0xFFFF_FFFF)
        result1 = self.driver.run_stub(image1, 0x0000_0000)
        self.assertEqual(result0.buffer_id, 0)
        self.assertEqual(result1.buffer_id, 1)
        self.assertEqual(result0.frame_id, 0xFFFF_FFFF)
        self.assertEqual(result1.frame_id, 0)
        self.assertEqual(self.driver.read(ld.OUTPUT_VALID_MASK), 0x3)

        self.driver.release_output(0x3)
        self.assertEqual(self.driver.read(ld.OUTPUT_VALID_MASK), 0)

    def test_submit_preloaded_starts_without_overwriting_input(self):
        model, desc = ld.make_stub_payload()
        self.driver.load_model(model, desc, model_version=1, desc_version=1)
        start = ld.INPUT_BUFFER_STRIDE_WORDS
        sentinel = np.arange(ld.INPUT_WORDS_PER_BUFFER, dtype=np.uint32) ^ np.uint32(0x5A5A0000)
        self.input.array[start : start + ld.INPUT_WORDS_PER_BUFFER] = sentinel

        selected = self.driver.submit_preloaded(1, 0x12345678)

        self.assertEqual(selected, 1)
        np.testing.assert_array_equal(
            self.input.array[start : start + ld.INPUT_WORDS_PER_BUFFER], sentinel
        )
        result = self.driver.wait_output(frame_id=0x12345678)
        expected = (
            np.arange(ld.OUTPUT_WORDS, dtype=np.uint32)
            ^ np.bitwise_xor.reduce(sentinel, dtype=np.uint32)
            ^ np.uint32(0x12345678)
        ).view(np.int32).reshape(5, 16, 16)
        np.testing.assert_array_equal(result.raw_map_i32, expected)
        summary = self.driver.wait_top1(frame_id=0x12345678)
        flat_index = int(np.argmax(expected[0]))
        cell_y, cell_x = divmod(flat_index, 16)
        self.assertEqual((summary.cell_x, summary.cell_y), (cell_x, cell_y))
        self.assertEqual(
            summary.raw_values_i32,
            tuple(int(expected[channel, cell_y, cell_x]) for channel in range(5)),
        )

    def test_official_v12_package_crc_and_hardware_descriptor(self):
        package = (
            Path(__file__).resolve().parents[2]
            / "quantized_locator_v12"
            / "quantized_locator_v12"
        )
        words, manifest = ld.read_locator_v12_package(package)
        self.assertEqual(words.size, 1904)
        self.assertEqual(ld.crc32_words(words), 0x63F19DDB)
        self.assertEqual(
            ld.crc32_words(ld.LOCATOR_V12_DESC_WORDS), ld.LOCATOR_V12_DESC_CRC32
        )
        loaded = self.driver.load_v12_package(package)
        self.assertEqual(loaded["architecture"], manifest["architecture"])
        self.assertTrue(self.driver.read(ld.STATUS) & ld.STATUS_MODEL_VALID)

    def test_official_v16_package_crc_and_hardware_descriptor(self):
        package = (
            Path(__file__).resolve().parents[2]
            / "quantized_locator_v16_failure_adaptation"
        )
        words, manifest = ld.read_locator_v16_package(package)
        self.assertEqual(words.size, 1904)
        self.assertEqual(ld.crc32_words(words), 0x21FC0351)
        self.assertEqual(
            ld.crc32_words(ld.LOCATOR_V16_DESC_WORDS), ld.LOCATOR_V16_DESC_CRC32
        )
        loaded = self.driver.load_v16_package(package)
        self.assertEqual(loaded["architecture"], manifest["architecture"])
        self.assertTrue(self.driver.read(ld.STATUS) & ld.STATUS_MODEL_VALID)

    def test_rejects_wrong_model_length_and_invalid_release(self):
        _, desc = ld.make_stub_payload()
        with self.assertRaises(ValueError):
            self.driver.load_model(np.zeros(1, dtype=np.uint32), desc, model_version=1, desc_version=1)
        with self.assertRaises(RuntimeError):
            self.driver.release_output(1)

    def test_from_pynq_enables_fclk1_before_mmio_mapping(self):
        events = []

        class ClockMeta(type):
            def __setattr__(cls, name, value):
                events.append(("clock", name, value))
                super().__setattr__(name, value)

        class FakeClocks(metaclass=ClockMeta):
            pass

        class RecordingMMIO(FakeMMIO):
            def __init__(self, base, size):
                events.append(("mmio", base, size))
                super().__init__(size // 4)

        fake_pynq = types.ModuleType("pynq")
        fake_pynq.Clocks = FakeClocks
        fake_pynq.MMIO = RecordingMMIO
        with mock.patch.dict(sys.modules, {"pynq": fake_pynq}):
            driver = ld.LocatorDriver.from_pynq()

        self.assertIsInstance(driver, ld.LocatorDriver)
        self.assertEqual(events[0], ("clock", "fclk0_mhz", 50.0))
        self.assertEqual(events[1], ("clock", "fclk1_mhz", 100.0))
        self.assertEqual(
            events[2:],
            [
                ("mmio", ld.LOCATOR_CTRL_BASE, ld.LOCATOR_CTRL_SIZE),
                ("mmio", ld.LOCATOR_INPUT_BASE, ld.LOCATOR_INPUT_SIZE),
                ("mmio", ld.LOCATOR_OUTPUT_BASE, ld.LOCATOR_OUTPUT_SIZE),
            ],
        )

    def test_hwh_clock_contract_accepts_enabled_fclk1(self):
        xml = """<SYSTEM><MODULE INSTANCE="processing_system7_0"><PARAMETERS>
        <PARAMETER NAME="PCW_EN_CLK1_PORT" VALUE="1"/>
        <PARAMETER NAME="PCW_FCLK_CLK1_BUF" VALUE="TRUE"/>
        <PARAMETER NAME="PCW_FPGA1_PERIPHERAL_FREQMHZ" VALUE="100"/>
        </PARAMETERS></MODULE>
        <MODULE INSTANCE="rst_ps_50m"><PARAMETERS>
        <PARAMETER NAME="C_EXT_RESET_HIGH" VALUE="0"/>
        <PARAMETER NAME="C_AUX_RESET_HIGH" VALUE="1"/>
        </PARAMETERS></MODULE>
        <MODULE INSTANCE="rst_locator_100m"><PARAMETERS>
        <PARAMETER NAME="C_EXT_RESET_HIGH" VALUE="0"/>
        <PARAMETER NAME="C_AUX_RESET_HIGH" VALUE="1"/>
        </PARAMETERS></MODULE></SYSTEM>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "safe.hwh"
            path.write_text(xml, encoding="utf-8")
            values = ld.validate_hwh_clock_contract(path)
        self.assertEqual(values["clocks"]["PCW_FCLK_CLK1_BUF"], "TRUE")
        self.assertEqual(values["resets"]["rst_locator_100m"]["C_AUX_RESET_HIGH"], "1")

    def test_hwh_clock_contract_rejects_stopped_fclk1(self):
        xml = """<SYSTEM><MODULE><PARAMETERS>
        <PARAMETER NAME="PCW_EN_CLK1_PORT" VALUE="1"/>
        <PARAMETER NAME="PCW_FCLK_CLK1_BUF" VALUE="FALSE"/>
        <PARAMETER NAME="PCW_FPGA1_PERIPHERAL_FREQMHZ" VALUE="100"/>
        </PARAMETERS></MODULE></SYSTEM>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.hwh"
            path.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PCW_FCLK_CLK1_BUF"):
                ld.validate_hwh_clock_contract(path)

    def test_hwh_clock_contract_rejects_active_low_constant_zero_aux_reset(self):
        xml = """<SYSTEM><MODULE INSTANCE="processing_system7_0"><PARAMETERS>
        <PARAMETER NAME="PCW_EN_CLK1_PORT" VALUE="1"/>
        <PARAMETER NAME="PCW_FCLK_CLK1_BUF" VALUE="TRUE"/>
        <PARAMETER NAME="PCW_FPGA1_PERIPHERAL_FREQMHZ" VALUE="100"/>
        </PARAMETERS></MODULE>
        <MODULE INSTANCE="rst_ps_50m"><PARAMETERS>
        <PARAMETER NAME="C_EXT_RESET_HIGH" VALUE="0"/>
        <PARAMETER NAME="C_AUX_RESET_HIGH" VALUE="0"/>
        </PARAMETERS></MODULE>
        <MODULE INSTANCE="rst_locator_100m"><PARAMETERS>
        <PARAMETER NAME="C_EXT_RESET_HIGH" VALUE="0"/>
        <PARAMETER NAME="C_AUX_RESET_HIGH" VALUE="1"/>
        </PARAMETERS></MODULE></SYSTEM>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe_reset.hwh"
            path.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "rst_ps_50m C_AUX_RESET_HIGH"):
                ld.validate_hwh_clock_contract(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

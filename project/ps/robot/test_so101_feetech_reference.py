import unittest

import arm_frame_template as aft
import so101_feetech_reference as ft
from arm_profile import ProfileError, find_config_root
from roarm_json_reference import ProtocolFieldMissing


CONFIG = find_config_root()
OFFICIAL = ft.FeetechProtocol.load(CONFIG / "protocols" / "feetech_sts_protocol.yaml")
FIXTURE = ft.FeetechProtocol.load(CONFIG / "protocols" / "fixtures" / "feetech_FIXTURE_NOT_OFFICIAL.yaml")
IDS = (21, 22, 23, 24, 25, 26)


class OfficialProtocolTests(unittest.TestCase):
    def test_no_numeric_constant_is_shipped(self):
        self.assertEqual(OFFICIAL.header, (None, None))
        self.assertIsNone(OFFICIAL.broadcast_id)
        self.assertTrue(all(code is None for code in OFFICIAL.instructions.values()))
        self.assertTrue(all(r.address is None for r in OFFICIAL.registers.values()))
        self.assertFalse(OFFICIAL.structure_verified)
        reasons = OFFICIAL.missing_fields()
        self.assertIn("frame structure assumption is not verified against official Feetech docs", reasons)
        self.assertIn("instructions.sync_write is TBD", reasons)
        with self.assertRaises(ProtocolFieldMissing):
            ft.ping(OFFICIAL, 1)
        with self.assertRaises(ProtocolFieldMissing):
            ft.compile_sync_write_template(OFFICIAL)


class FixtureCodecTests(unittest.TestCase):
    def test_packet_structure(self):
        packet = ft.read(FIXTURE, 21, "present_position")
        body = bytes([21, 4, 0x12, 0x50, 2])
        self.assertEqual(packet, b"\xe1\xe2" + body + bytes([(~sum(body)) & 0xFF]))
        self.assertEqual(ft.ping(FIXTURE, 3), b"\xe1\xe2\x03\x02\x11" + bytes([(~(3 + 2 + 0x11)) & 0xFF]))

    def test_sync_write_equals_template_engine(self):
        values = (2700, 2374, 0, 4095, 1, -5)
        direct, sat = ft.sync_write_positions(FIXTURE, IDS, values)
        self.assertFalse(sat)
        image = aft.TemplateImage.build(ft.compile_sync_write_template(FIXTURE),
                                        ft.compile_read_request_template(FIXTURE))
        engine = aft.run_program(image.ram, image.cmd_base, device_values=values, device_ids=IDS)
        self.assertEqual(engine.data, direct)
        self.assertEqual(direct[3], 22)       # LEN = 20 params + 2
        self.assertEqual(direct[-3:-1], b"\x05\x80")  # -5 sign-magnitude LE
        for channel in range(6):
            request = aft.run_program(image.ram, image.req_base, device_values=(0,) * 6,
                                      device_ids=IDS, rr_channel=channel).data
            self.assertEqual(request, ft.read(FIXTURE, IDS[channel], "present_position"))

    def test_status_round_trip(self):
        frame = ft.encode_status_packet(FIXTURE, 23, 0x04, b"\x10\x88")
        packet = ft.parse_status_packet(FIXTURE, frame)
        self.assertEqual((packet.device_id, packet.error, packet.params), (23, 4, b"\x10\x88"))
        self.assertEqual(ft.decode_position(FIXTURE, packet.params), -0x0810)
        with self.assertRaises(ValueError):
            ft.parse_status_packet(FIXTURE, frame[:-1] + bytes([frame[-1] ^ 1]))

    def test_invalid_protocol_values(self):
        raw = {
            "schema": ft.PROTOCOL_SCHEMA, "protocol_id": "x", "status": "BLOCKED_EXTERNAL_INPUT",
            "fixture": False, "servo_model": "x", "firmware_version": None, "sources": [],
            "structure_assumption": "", "structure_verified": False, "header": [0x100, 1],
            "broadcast_id": None,
            "instructions": {"ping": None, "read": None, "write": None, "sync_write": None},
            "registers": {k: {"address": None, "size": None} for k in ft.FeetechProtocol.REGISTERS},
            "position_encoding": None, "endian": None, "checksum": None, "notes": [],
        }
        with self.assertRaises(ProfileError):
            ft.FeetechProtocol.from_mapping(raw)


class StreamParserTests(unittest.TestCase):
    def setUp(self):
        self.config = ft.StatusParserConfig.from_protocol(FIXTURE)

    def parse(self, data, expected_id=22, config=None):
        model = ft.StatusStreamParserModel(config or self.config, expected_id=expected_id)
        return [(e.kind, e.device_id, e.error, e.value) for e in model.feed(data)]

    def test_valid_and_garbage_prefix(self):
        frame = ft.encode_status_packet(FIXTURE, 22, 0, b"\x46\x09")
        self.assertEqual(self.parse(b"\x00\xe1\x55" + frame), [("packet", 22, 0, 0x0946)])
        self.assertEqual(self.parse(b"\xe1\xe1" + frame), [("packet", 22, 0, 0x0946)])

    def test_error_kinds(self):
        frame = ft.encode_status_packet(FIXTURE, 22, 0, b"\x46\x09")
        self.assertEqual(self.parse(frame[:-1] + b"\x00")[0][0], "checksum_error")
        self.assertEqual(self.parse(frame, expected_id=21)[0][0], "protocol_error")
        short = ft.encode_status_packet(FIXTURE, 22, 0, b"\x46")
        self.assertEqual(self.parse(short)[0][0], "protocol_error")
        self.assertEqual(self.parse(b"\xe1\xe2\x16\x07")[0][0], "protocol_error")
        self.assertEqual(self.parse(b"\xe1\xe2\x16\x01"), [("protocol_error", 22, 0, 0)])

    def test_back_to_back_packets(self):
        a = ft.encode_status_packet(FIXTURE, 22, 0x20, b"\x00\x80")
        b = ft.encode_status_packet(FIXTURE, 22, 0, b"\xff\x7f")
        self.assertEqual(self.parse(a + b), [("packet", 22, 0x20, 0), ("packet", 22, 0, 0x7FFF)])

    def test_equal_header_bytes_skip_repeats(self):
        config = ft.StatusParserConfig(0xAA, 0xAA, 2, aft.ENC_TWOS, False, True)
        body = bytes([5, 4, 0, 0x34, 0x12])
        frame = b"\xaa\xaa\xaa" + body + bytes([(~sum(body)) & 0xFF])
        self.assertEqual(self.parse(frame, expected_id=5, config=config), [("packet", 5, 0, 0x1234)])


if __name__ == "__main__":
    unittest.main()

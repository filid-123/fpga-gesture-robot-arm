import unittest

import arm_backend as ab
import so101_feetech_reference as ft
from arm_profile import ArmProfile, RealOutputBlocked, find_config_root
from roarm_json_reference import RoArmJsonProtocol
from roarm_serial_transport import RoArmSerialTransport
from so101_serial_transport import FeetechSerialTransport


CONFIG = find_config_root()
RJ_FIXTURE = RoArmJsonProtocol.load(CONFIG / "protocols/fixtures/roarm_json_FIXTURE_NOT_OFFICIAL.yaml")
FT_FIXTURE = ft.FeetechProtocol.load(CONFIG / "protocols/fixtures/feetech_FIXTURE_NOT_OFFICIAL.yaml")
BENCH_RJ = ArmProfile.load(CONFIG / "arm_profiles/bench_loopback_roarm_json.yaml")
BENCH_FT = ArmProfile.load(CONFIG / "arm_profiles/bench_loopback_so101.yaml")


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        self.now += 1000
        return self.now


class FakeSerial:
    def __init__(self, replies=b"", echo=False):
        self.replies = bytearray(replies)
        self.echo = echo
        self.written = bytearray()
        self.closed = False

    def write(self, data):
        self.written += data
        if self.echo:
            self.replies[0:0] = data
        return len(data)

    def read(self, size=1):
        data = bytes(self.replies[:size])
        del self.replies[:size]
        return data

    def close(self):
        self.closed = True

    def reset_input_buffer(self):
        pass


class RoArmTransportTests(unittest.TestCase):
    def test_dry_run_never_opens_a_port(self):
        opened = []
        transport = RoArmSerialTransport(
            "COM_TEST", 115200, serial_factory=lambda *a: opened.append(a) or FakeSerial()
        )
        with transport:
            record = transport.send_line(b'{"type":7}\n')
        self.assertEqual(opened, [])
        self.assertFalse(record.transmitted)
        self.assertEqual(transport.dry_run_log[0].data, b'{"type":7}\n')

    def test_real_port_requires_permit(self):
        transport = RoArmSerialTransport("COM_TEST", 115200, dry_run=False,
                                         serial_factory=lambda *a: FakeSerial())
        with self.assertRaises(RealOutputBlocked):
            transport.open()

    def test_line_framing_and_queue_limit(self):
        transport = RoArmSerialTransport(None, 115200, max_queue=2, clock_ns=FakeClock())
        transport.feed_for_test(b'{"a":1}\n{"a":2}\n{"a":3}\n')
        self.assertEqual(transport.stats.rx_dropped, 1)
        self.assertEqual(transport.read_line(0).data, b'{"a":2}\n')
        self.assertEqual(transport.read_line(0).data, b'{"a":3}\n')
        self.assertIsNone(transport.read_line(0))
        with self.assertRaises(ValueError):
            transport.send_line(b"no newline")
        with self.assertRaises(ValueError):
            transport.send_line(b"a\nb\n")

    def test_bench_permit_transmits(self):
        fake = FakeSerial()
        permit = ab.require_real_output(BENCH_RJ, RJ_FIXTURE, purpose="bench_loopback", confirm_no_robot=True)
        transport = RoArmSerialTransport("COM_TEST", 115200, permit=permit, dry_run=False,
                                         serial_factory=lambda *a: fake)
        transport.open()
        try:
            self.assertTrue(transport.send_line(b'{"type":7}\n').transmitted)
        finally:
            transport.close()
        self.assertEqual(bytes(fake.written), b'{"type":7}\n')
        self.assertTrue(fake.closed)


class FeetechTransportTests(unittest.TestCase):
    def permit(self):
        return ab.require_real_output(BENCH_FT, FT_FIXTURE, purpose="bench_loopback", confirm_no_robot=True)

    def test_dry_run(self):
        transport = FeetechSerialTransport("COM_TEST", 1_000_000, FT_FIXTURE)
        packet = ft.ping(FT_FIXTURE, 21)
        result = transport.transact(packet, expect_reply=True, expected_id=21)
        self.assertEqual(result.error, "dry_run")
        self.assertEqual(transport.dry_run_log[0].data, packet)

    def test_reply_with_echo_discard(self):
        reply = ft.encode_status_packet(FT_FIXTURE, 21, 0, b"\x8c\x0a")
        fake = FakeSerial(replies=reply, echo=True)
        transport = FeetechSerialTransport("COM_TEST", 1_000_000, FT_FIXTURE, permit=self.permit(),
                                           dry_run=False, echo="discard", serial_factory=lambda *a: fake,
                                           clock_ns=FakeClock())
        transport.open()
        result = transport.transact(ft.read(FT_FIXTURE, 21, "present_position"),
                                    expect_reply=True, expected_id=21, timeout_s=1.0)
        self.assertIsNone(result.error)
        self.assertEqual(result.reply.value, 2700)

    def test_timeout_and_wrong_id(self):
        transport = FeetechSerialTransport("COM_TEST", 1_000_000, FT_FIXTURE, permit=self.permit(),
                                           dry_run=False, serial_factory=lambda *a: FakeSerial(),
                                           clock_ns=FakeClock())
        transport.open()
        result = transport.transact(ft.ping(FT_FIXTURE, 21), expect_reply=True, expected_id=21,
                                    timeout_s=0.00005)
        self.assertEqual(result.error, "response_timeout")
        wrong = ft.encode_status_packet(FT_FIXTURE, 22, 0, b"\x00\x00")
        transport._serial = FakeSerial(replies=wrong)
        result = transport.transact(ft.ping(FT_FIXTURE, 21), expect_reply=True, expected_id=21,
                                    timeout_s=1.0)
        self.assertEqual(result.error, "protocol_error")

    def test_readonly_permit_cannot_write_motion(self):
        permit = ab.RealOutputPermit("robot_readonly", "p", "x")
        transport = FeetechSerialTransport("COM_TEST", 1_000_000, FT_FIXTURE, permit=permit,
                                           dry_run=False, serial_factory=lambda *a: FakeSerial())
        transport.open()
        with self.assertRaises(RealOutputBlocked):
            transport.transact(b"\x00", expect_reply=False, writes_motion=True)


if __name__ == "__main__":
    unittest.main()

import unittest

import arm_frame_template as aft
import roarm_binary_bridge_reference as bridge


class BridgeTests(unittest.TestCase):
    def test_template_engine_matches_reference(self):
        values = (100, -100, 32767, -32768, 0, 12345)
        frame, sat = bridge.encode_command(values, seq=0x5C)
        self.assertFalse(sat)
        self.assertEqual(len(frame), bridge.COMMAND_FRAME_BYTES)
        image = aft.TemplateImage.build(bridge.compile_command_template())
        engine = aft.run_program(image.ram, 0, device_values=values, seq_byte=0x5C)
        self.assertEqual(engine.data, frame)
        self.assertEqual(frame[:5], b"\xa5\x5a\x0e\x01\x5c")
        self.assertEqual(frame[-1], (~sum(frame[2:-1])) & 0xFF)

    def test_saturation_reported(self):
        _, sat = bridge.encode_command((40000, 0, 0, 0, 0, 0), seq=0)
        self.assertTrue(sat)

    def test_state_round_trip_and_stream_resync(self):
        state = bridge.BridgeState(7, 0x81, (1, -2, 3, -4, 5, -6))
        frame = bridge.encode_state(state)
        self.assertEqual(bridge.decode_state(frame), state)
        parser = bridge.BridgeStateStreamParser()
        corrupted = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        states = parser.feed(b"\x00\xa5" + corrupted + frame[:10])
        self.assertEqual(states, [])
        states = parser.feed(frame[10:])
        self.assertEqual(states, [state])
        self.assertGreaterEqual(parser.errors, 1)


if __name__ == "__main__":
    unittest.main()

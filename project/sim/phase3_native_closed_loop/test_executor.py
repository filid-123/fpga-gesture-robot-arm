import unittest
import bootstrap
from executor import FixtureCodec, FixtureEndpoint
from arm_backend import ArmBackendPlModel


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.codec = FixtureCodec()
        self.commands = []
        self.measured = (0.0, 0.1, 0.2, -0.1, 0.0, 1.5)
        def actuator(positions, blocked):
            self.commands.append(positions)
            return {"joints": self.measured}
        self.endpoint = FixtureEndpoint(actuator, self.codec)

    def frame(self, pose):
        return ArmBackendPlModel(self.codec.config).process_sample(
            tuple(round(x*65536) for x in pose)).cmd

    def test_fragmented_frame_and_offset_direction(self):
        pose = (0.2,-0.2,0.4,0.1,-0.1,1.5)
        data = self.frame(pose)
        self.assertEqual(self.endpoint.feed(data[:17]), b"")
        reply = self.endpoint.feed(data[17:])
        for actual, expected in zip(self.commands[-1], pose):
            self.assertAlmostEqual(actual, expected, delta=0.0001)
        self.assertTrue(reply.endswith(b"\n"))

    def test_feedback_uses_measurement_not_target(self):
        reply = self.endpoint.feed(self.frame((0.4,0.4,0.4,0.4,0.4,0)))
        measured = self.codec.logical_feedback(reply)
        for a,b in zip(measured,self.measured):
            self.assertAlmostEqual(a,b,delta=0.0001)
        self.assertNotEqual(measured, self.commands[-1])

    def test_bad_or_partial_command_cannot_move(self):
        for data in (b'{"type":101,"j0":1}\n', b'not JSON\n', b'{"type":9}\n'):
            self.assertEqual(self.endpoint.feed(data),b"")
        self.assertEqual(self.commands,[])
        self.assertEqual(self.endpoint.rejected,3)

    def test_overlong_line_recovers_at_newline(self):
        self.assertEqual(self.endpoint.feed(b'x'*2000+b'\n'),b"")
        self.assertTrue(self.endpoint.feed(b'{"type":7}\n'))
        self.assertEqual(len(self.commands),1)
        self.assertEqual(len(self.endpoint.buffer),0)

    def test_out_of_scene_limit_cannot_move(self):
        self.assertEqual(self.endpoint.feed(self.frame((0,0,-1.1,0,0,1.5))),b"")
        self.assertEqual(self.commands,[])

    def test_silent_feedback_does_not_fake_position(self):
        self.endpoint.suppress_feedback=True
        self.assertEqual(self.endpoint.feed(b'{"type":7}\n'),b"")
        self.assertEqual(self.endpoint.replies,0)
        self.assertEqual(len(self.endpoint.observations),1)


if __name__ == "__main__":
    unittest.main()

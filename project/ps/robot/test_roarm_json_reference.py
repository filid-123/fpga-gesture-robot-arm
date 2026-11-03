import json
import random
import unittest

import arm_frame_template as aft
import roarm_json_reference as rj
from arm_profile import ProfileError, find_config_root


CONFIG = find_config_root()
OFFICIAL = rj.RoArmJsonProtocol.load(CONFIG / "protocols" / "roarm_m3_json_protocol.yaml")
FIXTURE = rj.RoArmJsonProtocol.load(CONFIG / "protocols" / "fixtures" / "roarm_json_FIXTURE_NOT_OFFICIAL.yaml")


def fixture_with(**changes):
    raw = {
        "schema": rj.PROTOCOL_SCHEMA, "protocol_id": "t", "status": "FIXTURE_NOT_OFFICIAL",
        "fixture": True, "firmware_version": None, "sources": [], "line_terminator": "\n",
        "fraction_digits": 3, "commands": {"set_joints": '{"a":${ch0}}'},
        "feedback": {"discriminator_key": None, "discriminator_value": None,
                     "position_keys": ["a", None, None, None, None, None],
                     "fraction_digits": 3, "max_line_length": 64},
        "notes": [],
    }
    for key, value in changes.items():
        raw[key] = value
    return rj.RoArmJsonProtocol.from_mapping(raw)


class OfficialProtocolTests(unittest.TestCase):
    def test_official_file_has_no_invented_fields(self):
        self.assertEqual(OFFICIAL.status, "BLOCKED_EXTERNAL_INPUT")
        self.assertIsNone(OFFICIAL.commands["set_joints"])
        self.assertEqual(OFFICIAL.position_keys, (None,) * 6)
        self.assertIsNone(OFFICIAL.discriminator_key)
        reasons = OFFICIAL.missing_fields()
        self.assertIn("commands.set_joints template is TBD", reasons)
        self.assertIn("feedback.position_keys[3] is TBD", reasons)

    def test_encoding_refuses_tbd_but_preview_works(self):
        with self.assertRaises(rj.ProtocolFieldMissing):
            rj.encode_command(OFFICIAL, "set_joints", (0,) * 6)
        preview = rj.preview_command(OFFICIAL, "set_joints", (1, 2, 3, 4, 5, 6))
        self.assertFalse(preview.sendable)
        self.assertIsNone(preview.data)
        self.assertIn("TBD", preview.text)


class FixtureEncodingTests(unittest.TestCase):
    def test_exact_line(self):
        data = rj.encode_command(FIXTURE, "set_joints", (10000, -5000, -15109, -74, 0, 15000))
        self.assertEqual(
            data,
            b'{"type":101,"j0":1.0000,"j1":-0.5000,"j2":-1.5109,"j3":-0.0074,"j4":0.0000,"j5":1.5000}\n',
        )
        self.assertIsInstance(json.loads(data), dict)

    def test_fixture_is_never_verified(self):
        self.assertIn("synthetic FIXTURE_NOT_OFFICIAL", FIXTURE.missing_fields()[0])

    def test_preview_with_incomplete_mapping(self):
        preview = rj.preview_command(FIXTURE, "set_joints", (1, None, 3, 4, 5, 6))
        self.assertFalse(preview.sendable)
        self.assertIn("<TBD:ch1>", preview.text)

    def test_template_rules(self):
        bad = [
            '{"a":${ch0}}\n', '{"a":${ch6}}', '{"a":${ch0},"b":${ch0}}', '{"a":${x}}',
            '{"a":${ch0}', '["${ch0}"]',
        ]
        for template in bad:
            with self.assertRaises(ProfileError, msg=template):
                fixture_with(commands={"set_joints": template})
        with self.assertRaises(ProfileError):
            fixture_with(line_terminator="\r\n")

    def test_compiled_words_are_valid_for_pl(self):
        words = rj.compile_template(FIXTURE, "set_joints")
        image = aft.TemplateImage.build(words)
        self.assertEqual(aft.validate_program(image.ram, 0), len(words))


class ScaleDecimalTests(unittest.TestCase):
    def test_first_dropped_digit_rounding(self):
        self.assertEqual(rj.scale_decimal_text("0.12349", 3), 123)
        self.assertEqual(rj.scale_decimal_text("0.1235", 3), 124)
        self.assertEqual(rj.scale_decimal_text("-0.1235", 3), -124)
        self.assertEqual(rj.scale_decimal_text("12", 3), 12000)
        self.assertEqual(rj.scale_decimal_text("-0", 2), 0)
        with self.assertRaises(ValueError):
            rj.scale_decimal_text("1e3", 0)
        with self.assertRaises(ValueError):
            rj.scale_decimal_text("2147483.648", 3)


class StreamingParserTests(unittest.TestCase):
    def setUp(self):
        self.config = rj.JsonParserConfig.from_protocol(FIXTURE)

    def run_lines(self, *lines, config=None):
        model = rj.JsonKeyLineParserModel(config or self.config)
        model.feed(b"".join(lines))
        return model.events

    def test_valid_record_matches_semantic_parse(self):
        line = rj.encode_command(FIXTURE, "set_joints", (1, -2, 3, -4, 5, -6))
        events = self.run_lines(line)
        self.assertEqual([e.kind for e in events], ["record"])
        self.assertEqual(events[0].values, (1, -2, 3, -4, 5, -6))
        self.assertEqual(events[0].mask, 0x3F)
        semantic = rj.parse_feedback_line(FIXTURE, line)
        self.assertEqual(semantic.device_values, (1, -2, 3, -4, 5, -6))

    def test_random_cross_check_against_json_loads(self):
        rng = random.Random(1051)
        for _ in range(300):
            values = [rng.randint(-2_000_000_000, 2_000_000_000) // 10 for _ in range(6)]
            fields = [f'"j{ch}": {rj.aft.format_fixed_decimal(values[ch], rng.randint(0, 6))}'
                      for ch in range(6)]
            rng.shuffle(fields)
            fields.insert(rng.randint(0, 6), '"type":101')
            if rng.random() < 0.5:
                fields.insert(rng.randint(0, 7), '"note":"x\\"y:z"')
            line = ("{" + ", ".join(fields) + "}\r\n").encode("ascii")
            try:
                semantic = rj.parse_feedback_line(FIXTURE, line)
            except ValueError:
                continue
            events = self.run_lines(line)
            self.assertEqual(events[0].kind, "record", line)
            self.assertEqual(events[0].values, semantic.device_values, line)

    def test_ignored_and_error_classification(self):
        cases = [
            (b"\n", "ignored"),
            (b"\r\n", "ignored"),
            (b'{"type":7}\n', "ignored"),
            (b'{"type":101.4,"j0":1}\n', "error"),                 # disc 101.4 rounds to 101
            (b'{"type":102,"j0":1,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "ignored"),
            (b'{"type":101,"j0":1,"j1":2,"j2":3,"j3":4,"j4":5}\n', "error"),   # missing j5
            (b'{"type":101,"j0":1,"j0":1,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j0":1e3,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j0":"1","j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j0":1.,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j0":-,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j0":214749,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
            (b'{"type":101,"j\\u0030":1,"j1":2,"j2":3,"j3":4,"j4":5,"j5":6}\n', "error"),
        ]
        for line, expected in cases:
            events = self.run_lines(line)
            self.assertEqual([e.kind for e in events], [expected], line)

    def test_limits_of_int32_device_units(self):
        ok = b'{"type":101,"j0":-214748.3648,"j1":214748.3647,"j2":0,"j3":0,"j4":0,"j5":0}\n'
        events = self.run_lines(ok)
        self.assertEqual(events[0].values[:2], (-(1 << 31), (1 << 31) - 1))
        bad = b'{"type":101,"j0":214748.36475,"j1":0,"j2":0,"j3":0,"j4":0,"j5":0}\n'
        self.assertEqual(self.run_lines(bad)[0].kind, "error")

    def test_overlong_line_is_error_and_parser_recovers(self):
        config = rj.JsonParserConfig(self.config.keys, 4, 0x0A, 40, 101)
        good = b'{"type":101,"j0":0,"j1":0,"j2":0,"j3":0,"j4":0,"j5":0}\n'
        long_config = rj.JsonParserConfig(self.config.keys, 4, 0x0A, 80, 101)
        events = self.run_lines(b"x" * 50 + b"\n", good, config=long_config)
        self.assertEqual([e.kind for e in events], ["ignored", "record"])
        events = self.run_lines(good, config=config)
        self.assertEqual([e.kind for e in events], ["error"])

    def test_no_discriminator_mode(self):
        protocol = fixture_with()
        config = rj.JsonParserConfig.from_protocol(protocol)
        events = self.run_lines(b'{"a":1.2345}\n', b'{"b":1}\n', config=config)
        self.assertEqual([(e.kind, e.values[0]) for e in events], [("record", 1235), ("ignored", 0)])

    def test_key_ram_image(self):
        ram = self.config.key_ram()
        self.assertEqual(bytes(ram[0:2]), b"j0")
        self.assertEqual(bytes(ram[6 * 16 : 6 * 16 + 4]), b"type")
        self.assertEqual(self.config.key_len_word(), 0x4222222)


if __name__ == "__main__":
    unittest.main()

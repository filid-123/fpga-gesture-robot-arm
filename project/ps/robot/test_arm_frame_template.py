import unittest

import arm_frame_template as aft
from arm_fixed_point import INT32_MAX, INT32_MIN


def image_with(words):
    return aft.TemplateImage.build(list(words) + [aft.end()])


class DecimalFormatTests(unittest.TestCase):
    def test_vectors(self):
        cases = [
            (0, 0, "0"), (0, 4, "0.0000"), (-5, 4, "-0.0005"), (15000, 4, "1.5000"),
            (-15109, 4, "-1.5109"), (123, 0, "123"), (-123, 0, "-123"),
            (INT32_MAX, 6, "2147.483647"), (INT32_MIN, 6, "-2147.483648"),
            (INT32_MIN, 0, "-2147483648"), (1, 6, "0.000001"), (999999, 6, "0.999999"),
            (1000000, 6, "1.000000"),
        ]
        for value, digits, text in cases:
            self.assertEqual(aft.format_fixed_decimal(value, digits), text, (value, digits))

    def test_rejects_out_of_range(self):
        with self.assertRaises(aft.TemplateError):
            aft.format_fixed_decimal(0, 7)
        with self.assertRaises(Exception):
            aft.format_fixed_decimal(INT32_MAX + 1, 0)


class BinaryFieldTests(unittest.TestCase):
    def test_twos_complement_and_saturation(self):
        self.assertEqual(aft.encode_binary_field(-2, 16, big_endian=False, encoding=aft.ENC_TWOS),
                         (b"\xfe\xff", False))
        self.assertEqual(aft.encode_binary_field(40000, 16, big_endian=True, encoding=aft.ENC_TWOS),
                         (b"\x7f\xff", True))
        self.assertEqual(aft.encode_binary_field(-40000, 16, big_endian=False, encoding=aft.ENC_TWOS),
                         (b"\x00\x80", True))

    def test_unsigned_and_sign_magnitude(self):
        self.assertEqual(aft.encode_binary_field(-1, 16, big_endian=False, encoding=aft.ENC_UNSIGNED),
                         (b"\x00\x00", True))
        self.assertEqual(aft.encode_binary_field(70000, 16, big_endian=False, encoding=aft.ENC_UNSIGNED),
                         (b"\xff\xff", True))
        self.assertEqual(aft.encode_binary_field(-300, 16, big_endian=False, encoding=aft.ENC_SIGN_MAGNITUDE),
                         (b"\x2c\x81", False))
        self.assertEqual(aft.encode_binary_field(-40000, 16, big_endian=False,
                                                 encoding=aft.ENC_SIGN_MAGNITUDE), (b"\xff\xff", True))
        self.assertEqual(aft.encode_binary_field(INT32_MIN, 32, big_endian=False,
                                                 encoding=aft.ENC_SIGN_MAGNITUDE)[1], True)

    def test_decode_inverts_encode(self):
        for encoding in (aft.ENC_TWOS, aft.ENC_UNSIGNED, aft.ENC_SIGN_MAGNITUDE):
            for value in (0, 1, 1234, 32767):
                data, _ = aft.encode_binary_field(value, 16, big_endian=True, encoding=encoding)
                self.assertEqual(aft.decode_binary_field(data, big_endian=True, encoding=encoding), value)
        data, _ = aft.encode_binary_field(-1234, 16, big_endian=False, encoding=aft.ENC_SIGN_MAGNITUDE)
        self.assertEqual(aft.decode_binary_field(data, big_endian=False, encoding=aft.ENC_SIGN_MAGNITUDE), -1234)


class EngineTests(unittest.TestCase):
    def test_checksum_ops_and_ids(self):
        image = image_with([
            aft.lit(0xAA), aft.ckb(aft.CK_SUM8), aft.lit(0x01), aft.idb(2), aft.idb(None),
            aft.seq(), aft.cke(invert=True), aft.ckb(aft.CK_XOR8), aft.lit(0x0F), aft.lit(0xF0),
            aft.cke(invert=False),
        ])
        result = aft.run_program(image.ram, 0, device_values=(0,) * 6,
                                 device_ids=(10, 11, 12, 13, 14, 15), rr_channel=4, seq_byte=0x33)
        body = [0x01, 12, 14, 0x33]
        self.assertEqual(result.data, bytes([0xAA] + body + [(~sum(body)) & 0xFF, 0x0F, 0xF0, 0xFF]))

    def test_dec_bin_mixture_and_saturation_flag(self):
        image = image_with([aft.dec(0, 2), aft.lit(ord(",")),
                            aft.binf(1, 16, big_endian=False, encoding=aft.ENC_TWOS)])
        ok = aft.run_program(image.ram, 0, device_values=(-12345, 7, 0, 0, 0, 0))
        self.assertEqual(ok.data, b"-123.45,\x07\x00")
        self.assertFalse(ok.saturated)
        sat = aft.run_program(image.ram, 0, device_values=(0, 1 << 20, 0, 0, 0, 0))
        self.assertTrue(sat.saturated)

    def test_word_legality_matches_pl_rules(self):
        legal = [aft.end(), aft.lit(0xFF), aft.dec(5, 6), aft.binf(5, 32, big_endian=True,
                 encoding=aft.ENC_SIGN_MAGNITUDE), aft.ckb(1), aft.cke(invert=True), aft.idb(None),
                 aft.idb(5), aft.seq()]
        for word in legal:
            self.assertTrue(aft.word_is_legal(word), hex(word))
        illegal = [0x0001, 0x1100, 0x2006, 0x2070, 0x2080, 0x3000, 0x3018, 0x30C8, 0x3108,
                   0x4002, 0x5002, 0x6006, 0x6009, 0x7001, 0x8000, 0xF000]
        for word in illegal:
            self.assertFalse(aft.word_is_legal(word), hex(word))

    def test_validation_rejects_missing_end(self):
        ram = [aft.lit(0x41)] * aft.TEMPLATE_DEPTH
        with self.assertRaises(aft.TemplateError):
            aft.validate_program(ram, 0)
        ram[255] = aft.end()
        self.assertEqual(aft.validate_program(ram, 250), 6)

    def test_image_layout_and_overflow(self):
        image = aft.TemplateImage.build([aft.lit(1), aft.end()], [aft.lit(2), aft.end()])
        self.assertEqual((image.cmd_base, image.req_base, image.req_enable), (0, 2, True))
        with self.assertRaises(aft.TemplateError):
            aft.TemplateImage.build([aft.lit(1)] * 200 + [aft.end()], [aft.lit(1)] * 60 + [aft.end()])
        with self.assertRaises(aft.TemplateError):
            aft.TemplateImage.build([aft.lit(1)])


if __name__ == "__main__":
    unittest.main()

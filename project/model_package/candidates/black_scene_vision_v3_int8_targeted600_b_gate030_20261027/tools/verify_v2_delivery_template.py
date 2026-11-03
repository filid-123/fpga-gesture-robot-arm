"""Standalone integrity, ROM/descriptors, numerical boundaries and geometry checks."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'reference'))


def verify_hashes(root=ROOT):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in ('manifest.json', 'CHECKSUMS.sha256')}
    assert actual == set(manifest['files_sha256']), 'Package file inventory differs'
    for relative, expected in manifest['files_sha256'].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
    if (root / 'CHECKSUMS.sha256').exists():
        for line in (root / 'CHECKSUMS.sha256').read_text(encoding='utf-8').splitlines():
            expected, relative = line.split('  ', 1)
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
    return manifest


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    manifest = verify_hashes()
    from preprocessing import preprocess_bgr_to_locator_input, small_roi_descriptor, classifier_from_small
    from integer_vision_reference import wrap32, round_shift
    from locator_temporal_pc import GeometryStabilizer
    lp = dict(np.load(ROOT / 'quantized/locator/parameters.npz', allow_pickle=False))
    cp = dict(np.load(ROOT / 'quantized/classifier/parameters.npz', allow_pickle=False))
    assert int(lp['confidence_threshold_i32']) == math.ceil(math.log(.3 / .7) / float(lp['conv5_output_scale'][0])) == -11748
    scale = float(lp['conv5_output_scale'][0])
    assert 1 / (1 + math.exp(-(-11749) * scale)) < .3 <= 1 / (1 + math.exp(-(-11748) * scale))
    assert wrap32(np.array([2**31, -2**31 - 1], np.int64)).tolist() == [-2**31, 2**31 - 1]
    assert round_shift(np.array([-3, -1, 1, 3], np.int64), 1, 1).tolist() == [-1, 0, 1, 2]
    assert round_shift(np.array([-1, 1], np.int64), 5, 0).tolist() == [-5, 5]
    for kind, name in (('locator', 'model_rom_16k'), ('classifier', 'weights_all'), ('classifier', 'layer_descriptors')):
        p = ROOT / 'quantized' / kind / (name + '.mem')
        assert np.array([int(line, 16) for line in p.read_text().splitlines()], dtype='<u4').tobytes() == p.with_suffix('.bin').read_bytes()
    blob = (ROOT / 'quantized/classifier/weights_all.bin').read_bytes()
    layout = read(ROOT / 'quantized/classifier/layout_and_descriptors.json')
    assert len(blob) == layout['bytes'] == 39488
    descriptor = np.frombuffer((ROOT / 'quantized/classifier/layer_descriptors.bin').read_bytes(), dtype='<u4').reshape(8, 8)
    assert descriptor.tolist() == layout['descriptor_words'] and int(descriptor[7, 0]) == 0x01060102
    for record, stage in zip(layout['layers'], (0, 2, 4, 6, 7), strict=True):
        name = record['layer']; w, b = record['weight_offset_bytes'], record['bias_offset_bytes']
        assert blob[w:w + record['weight_size_bytes']] == cp[name + '_weight_q'].tobytes()
        assert blob[b:b + record['bias_size_bytes']] == cp[name + '_bias_q'].astype('<i4').tobytes()
        assert int(descriptor[stage, 2]) == w and int(descriptor[stage, 3]) == b
        if name != 'fc2':
            assert int(descriptor[stage, 4]) == int(cp[name + '_M'])
            assert int(descriptor[stage, 5]) & 255 == int(cp[name + '_shift'])
    small = np.zeros((128, 128), np.uint8); small[16:112] = np.arange(128, dtype=np.uint8)[None]
    assert classifier_from_small(small, (0, 0, 480, 480)).shape == (32, 32)
    assert small_roi_descriptor((600, 0, 640, 40)) == {'sx': 120, 'sy': 16, 'ss': 8}
    for roi in ((0., 0, 480, 480), (0, 0, 481, 480), (-1, 0, 479, 480)):
        try: small_roi_descriptor(roi)
        except ValueError: pass
        else: raise AssertionError('Illegal ROI accepted')
    try: preprocess_bgr_to_locator_input(np.zeros((240, 320, 3), np.uint8))
    except ValueError: pass
    else: raise AssertionError('Non-VGA input not rejected')
    timing = read(ROOT / 'golden_integer/temporal_examples.json'); filter_ = GeometryStabilizer()
    for row in timing['rows']:
        current = filter_.update(row['raw_box'], row['detected'], 640, 480, row['timestamp_seconds'])
        assert current['state'] == row['expected']['state']
        np.testing.assert_allclose(current['effective_box'], row['expected']['effective_box'], atol=1e-8)
        if not row['detected']: assert current['classifier_allowed'] is False
    print(json.dumps({'status': 'PASS_DELIVERY_INTEGRITY_LAYOUT_GATE_AND_TEMPORAL',
        'checked_files': len(manifest['files_sha256']), 'MEM_BIN_and_NPZ_descriptors_exact': True,
        'raw_gate030': -11748, 'temporal_synthetic_events': len(timing['rows']), 'RTL_simulated': False}))


if __name__ == '__main__': main()

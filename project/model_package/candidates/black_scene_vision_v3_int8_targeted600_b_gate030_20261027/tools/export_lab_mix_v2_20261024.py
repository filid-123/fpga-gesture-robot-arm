"""Freeze the approved B/gate0.30 combination and TRAIN-only classifier PTQ."""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'handoff/black_scene_vision_v1_int8_20261013'
OUT = ROOT / 'quantized_black_scene_v2_B_gate030_20261024'
DATA = ROOT / 'gesture_CNN/datasets/classifier_lab_dim_mix_B_20261023'
VAL = ROOT / 'gesture_CNN/datasets/classifier_phase2_b_existing_v1_20261023'
MODEL = ROOT / 'gesture_CNN/models_classifier_lab_dim_mix_B_20261023/translation4/classifier_final.pt'
MODEL_SHA = '214404744a8f3b62ed7cd4147b4c7403694b5295e3b054dd86a9d9070e6d7c58'
sys.path.insert(0, str(ROOT / 'gesture_CNN'))
from gesture_model_v4_six_class import GestureCNN6, CLASS_NAMES


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
def rows(path): return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def helpers():
    source = ROOT / 'handoff_tools/export_black_scene_integer.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    names = ('away', 'multiplier', 'quant_layer', 'read_legacy_descriptor_helpers', 'write_mem')
    functions = [node for name in names for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(functions) == len(names)
    ns = {'np': np, 'math': math, 'ast': ast, 'CLS': ROOT / 'gesture_CNN'}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), ns)
    return ns


def integer_ops():
    spec = importlib.util.spec_from_file_location('v2_export_integer_ops', BASE / 'reference/integer_vision_reference.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


@torch.no_grad()
def float_forward(model, bank):
    maxima = {n: 0. for n in ('conv1', 'conv2', 'conv3', 'fc1')}; outputs = []
    for start in range(0, len(bank), 64):
        x = torch.from_numpy(bank[start:start + 64].astype(np.float32) / 255)
        x = model.pool1(model.relu1(model.conv1(x))); maxima['conv1'] = max(maxima['conv1'], float(x.max()))
        x = model.pool2(model.relu2(model.conv2(x))); maxima['conv2'] = max(maxima['conv2'], float(x.max()))
        x = model.pool3(model.relu3(model.conv3(x))); maxima['conv3'] = max(maxima['conv3'], float(x.max()))
        x = model.relu4(model.fc1(model.flatten(x))); maxima['fc1'] = max(maxima['fc1'], float(x.max()))
        outputs.append(model.fc2(x).numpy())
    return np.concatenate(outputs), maxima


def summarize(records, predictions, gate):
    matrix = np.zeros((6, 7), np.int64)
    for r, k in zip(records, predictions, strict=True):
        accepted = r['locator_confidence_raw_i32'] >= gate and r['roi_source'] is not None
        matrix[r['class_id'], int(k) if accepted else 6] += 1
    return {'hand_support': int(matrix[1:].sum()), 'hand_detected': int(matrix[1:, :6].sum()),
        'hand_correct': int(sum(matrix[k, k] for k in range(1, 6))),
        'empty_support': int(matrix[0].sum()), 'empty_detector_false_positive': int(matrix[0, :6].sum()),
        'empty_effective_gesture_false_positive': int(matrix[0, 1:6].sum()),
        'class_names': list(CLASS_NAMES), 'columns': [*CLASS_NAMES, 'no_detection'], 'confusion_matrix': matrix.tolist(),
        'per_class_correct': {CLASS_NAMES[k]: int(matrix[k, k]) for k in range(1, 6)}}


def merge_ranges(destination, source):
    for name, values in source.items():
        out = destination.setdefault(name, {'min': values['min'], 'max': values['max'], 'overflow_count': 0,
            'high_saturation_count': 0, 'activation_elements': 0})
        out['min'] = min(out['min'], values['min']); out['max'] = max(out['max'], values['max'])
        for field in ('overflow_count', 'high_saturation_count', 'activation_elements'):
            out[field] += values.get(field, 0)


def main():
    if OUT.exists(): raise FileExistsError('Never overwrite a frozen quantization attempt')
    torch.set_num_threads(4); torch.backends.mkldnn.enabled = True
    assert sha(MODEL) == MODEL_SHA
    original_manifest = read(BASE / 'manifest.json')
    for relative, digest in original_manifest['files_sha256'].items(): assert sha(BASE / relative) == digest
    prep = read(DATA / 'preparation_report.json')
    for path, digest in prep['artifact_sha256'].items(): assert sha(path) == digest
    train = rows(DATA / 'train_manifest.jsonl'); images = np.load(DATA / 'train_inputs_u8.npy', allow_pickle=False)
    assert len(train) == 690 and images.shape == (690, 1, 32, 32)
    lp = dict(np.load(BASE / 'quantized/locator/parameters.npz', allow_pickle=False))
    gate = math.ceil(math.log(.3 / .7) / float(lp['conv5_output_scale'][0])); assert gate == -11748
    lp['confidence_threshold_i32'] = np.asarray(gate, dtype=np.int32)
    ids = [i for i, r in enumerate(train) if r['roi_source'] is not None and
        (r['class_name'] == 'background' or r['locator_confidence_raw_i32'] >= gate)]
    assert len(ids) == 681
    print({'stage': 'TRAIN_ONLY_CALIBRATION', 'crops': len(ids), 'classifier_SHA': MODEL_SHA}, flush=True)
    for i in ids:
        r = train[i]
        assert r['split'] == 'train' and sha(r['image']) == r['image_sha256']
        assert hashlib.sha256(images[i, 0].tobytes()).hexdigest() == r['classifier_input_sha256']
    model = GestureCNN6().eval(); checkpoint = torch.load(MODEL, map_location='cpu', weights_only=False)
    assert tuple(checkpoint['class_names']) == CLASS_NAMES
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    _, maxima = float_forward(model, images[ids])
    utility = helpers(); quant = utility['quant_layer']
    cp, layer_info, previous = {}, {}, 1 / 255
    state = model.state_dict()
    for name in ('conv1', 'conv2', 'conv3', 'fc1', 'fc2'):
        scale = max(maxima[name] / 255, 1e-12) if name != 'fc2' else None
        p, info = quant(state[name + '.weight'], state[name + '.bias'], previous, scale)
        cp.update({name + '_' + k: v for k, v in p.items()}); layer_info[name] = info
        if scale is not None: previous = scale
    cp['fc2_output_scale'] = cp['fc2_bias_scale']
    OUT.mkdir(); (OUT / 'locator').mkdir(); (OUT / 'classifier').mkdir()
    np.savez_compressed(OUT / 'locator/parameters.npz', **lp)
    np.savez_compressed(OUT / 'classifier/parameters.npz', **cp)
    for name in ('model_rom_16k.mem', 'model_rom_16k.bin', 'layout.json'):
        shutil.copy2(BASE / 'quantized/locator' / name, OUT / 'locator' / name)
    cblob, layout = bytearray(), []
    for name in ('conv1', 'conv2', 'conv3', 'fc1', 'fc2'):
        cblob.extend(bytes((-len(cblob)) % 4)); wo = len(cblob); wb = cp[name + '_weight_q'].tobytes(); cblob.extend(wb)
        cblob.extend(bytes((-len(cblob)) % 4)); bo = len(cblob); bb = cp[name + '_bias_q'].astype('<i4').tobytes(); cblob.extend(bb)
        layout.append({'layer': name, 'weight_offset_bytes': wo, 'weight_size_bytes': len(wb), 'bias_offset_bytes': bo, 'bias_size_bytes': len(bb)})
    assert len(cblob) == 39488
    (OUT / 'classifier/weights_all.bin').write_bytes(cblob); utility['write_mem'](OUT / 'classifier/weights_all.mem', cblob)
    descriptor_helpers = utility['read_legacy_descriptor_helpers']()
    descriptors = descriptor_helpers['build_layer_descriptors']({n: {'M': int(cp[n + '_M']) if n != 'fc2' else 0,
        'shift': int(cp[n + '_shift']) if n != 'fc2' else 0} for n in layer_info}, layout)
    assert descriptors[7][0] == 0x01060102
    dblob = np.asarray(descriptors, dtype='<u4').tobytes()
    (OUT / 'classifier/layer_descriptors.bin').write_bytes(dblob); utility['write_mem'](OUT / 'classifier/layer_descriptors.mem', dblob)
    write(OUT / 'classifier/layout_and_descriptors.json', {'bytes': len(cblob), 'layers': layout, 'descriptor_words': descriptors, 'final_Cout': 6})
    calibration = {'role': 'TRAIN_ONLY_STATIC_PTQ', 'selection': 'all681legalTRAINproductionROIatgate0.30_plus_approved_empty_peak',
        'activation_range_policy': 'strict100percent_max;no_VAL_percentile_or_search', 'crops': len(ids),
        'by_cohort': dict(Counter(train[i]['training_cohort'] for i in ids)),
        'by_class': dict(Counter(train[i]['class_name'] for i in ids)), 'activation_maxima': maxima,
        'VAL_or_TEST_used': False, 'crop_sha256': [{'image_id': train[i]['image_id'], 'input_sha256': train[i]['classifier_input_sha256'],
            'source_image_sha256': train[i]['image_sha256']} for i in ids]}
    write(OUT / 'calibration.json', calibration)
    frozen_quant_hashes = {str(p.relative_to(OUT)): sha(p) for p in OUT.rglob('*') if p.is_file()}
    write(OUT / 'manifest.json', {'status': 'QUANTIZATION_FROZEN_BEFORE_DEVELOPMENT_VALIDATION',
        'classifier_sha256': MODEL_SHA, 'classifier_layers': layer_info, 'threshold_probability': .3,
        'confidence_threshold_raw_i32': gate, 'locator_weights_and_scales_reused_exact': True,
        'locator_ROM_sha256': sha(OUT / 'locator/model_rom_16k.bin'), 'files_sha256': frozen_quant_hashes})
    print({'stage': 'QUANTIZATION_FROZEN', 'maxima': maxima, 'raw_gate': gate}, flush=True)
    ops = integer_ops(); ranges = {}; validation = {}; details = {}
    val_records = rows(VAL / 'val_manifest.jsonl'); val_images = np.load(VAL / 'val_inputs_u8.npy', allow_pickle=False)
    assert len(val_records) == 270
    for name, records, bank in (('combined_TRAIN_diagnostic', train, images), ('development_VAL', val_records, val_images)):
        fl, _ = float_forward(model, bank)
        integer_logits = []
        for i, image in enumerate(bank):
            logits, _, observed = ops.forward_classifier(image[0], cp)
            merge_ranges(ranges, observed); integer_logits.append(logits)
        q = np.stack(integer_logits); fp, ip = fl.argmax(1), q.argmax(1)
        fsum, isum = summarize(records, fp, gate), summarize(records, ip, gate)
        accepted_hand = np.array([r['class_name'] != 'background' and r['locator_confidence_raw_i32'] >= gate and r['roi_source'] is not None for r in records])
        labels = np.array([r['class_id'] for r in records])
        validation[name] = {'mixed_integerLocator_floatClassifier': fsum, 'full_integer': isum,
            'float_correct_integer_wrong_hand': int((accepted_hand & (fp == labels) & (ip != labels)).sum()),
            'integer_correct_float_wrong_hand': int((accepted_hand & (ip == labels) & (fp != labels)).sum()),
            'same_prediction_all_ROIs': int((fp == ip).sum()), 'ROI_count': len(records)}
        details[name] = [{'image_id': r['image_id'], 'truth': r['class_name'], 'raw_locator_conf': r['locator_confidence_raw_i32'],
            'accepted': r['locator_confidence_raw_i32'] >= gate, 'float_class': CLASS_NAMES[int(fp[i])],
            'integer_class': CLASS_NAMES[int(ip[i])], 'integer_logits': q[i].tolist(),
            'float_logits': fl[i].tolist()} for i, r in enumerate(records)]
        print({'cohort': name, 'float_correct': fsum['hand_correct'], 'integer_correct': isum['hand_correct']}, flush=True)
    assert validation['development_VAL']['mixed_integerLocator_floatClassifier']['hand_correct'] == 200
    assert sum(r['overflow_count'] for r in ranges.values()) == 0
    for relative, digest in frozen_quant_hashes.items(): assert sha(OUT / relative) == digest
    result = {'status': 'CLASSIFIER_PTQ_VALIDATED', 'quantization_parameters_frozen_before_VAL': True,
        'metrics': validation, 'observed_classifier_ranges_TRAIN_and_VAL': ranges,
        'classifier_observed_overflow_count': 0, 'locator_reference': 'unchanged_v1_verified_weights_scales_arithmetic',
        'TEST_read': False, 'new_training': False, 'RTL_simulated': False}
    write(OUT / 'validation.json', result); write(OUT / 'validation_rows.json', details)
    print({'status': result['status'], 'validation': validation}, flush=True)


if __name__ == '__main__': main()

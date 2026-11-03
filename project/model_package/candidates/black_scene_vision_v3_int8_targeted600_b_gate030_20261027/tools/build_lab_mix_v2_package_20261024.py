"""Build an independent B/gate0.30 INT8 handoff, with full-layer TRAIN goldens."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
BASE = ROOT / 'handoff/black_scene_vision_v1_int8_20261013'
PARAM = ROOT / 'quantized_black_scene_v2_B_gate030_20261024'
ID = 'black_scene_vision_v2_int8_B_gate030_20261024'
OUT = ROOT / 'handoff' / ID


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def import_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def save_mem(path, values):
    a = np.asarray(values)
    if a.dtype == np.uint8:
        data = a.reshape(-1).tobytes(); data += bytes((-len(data)) % 4)
        words = np.frombuffer(data, dtype='<u4'); bits = 32
    elif a.dtype == np.int32: words, bits = a.reshape(-1).astype(np.uint32), 32
    elif a.dtype == np.int64: words, bits = a.reshape(-1).astype(np.uint64), 64
    else: raise ValueError('Unsupported golden dtype ' + str(a.dtype))
    path.write_text(''.join(f'{int(word):0{bits // 4}X}\n' for word in words), encoding='ascii')
    return {'shape': list(a.shape), 'dtype': str(a.dtype), 'mem_word_bits': bits,
        'mem_words': len(words), 'layout': 'CHW/C row-major;uint8 packed little-endian4bytes/word'}


def bank_pack(a):
    banks = np.zeros((8, 4096), np.uint8)
    for channel in range(a.shape[0]): banks[channel % 8, channel // 8 * 256:(channel // 8 + 1) * 256] = a[channel].reshape(-1)
    return banks


def main():
    if OUT.exists(): raise FileExistsError('Never overwrite a candidate package')
    torch.set_num_threads(4)
    validation = read(PARAM / 'validation.json'); assert validation['status'] == 'CLASSIFIER_PTQ_VALIDATED'
    assert validation['classifier_observed_overflow_count'] == 0
    OUT.mkdir()
    for name in ('reference/models', 'models', 'golden_integer', 'hardware_contract', 'docs', 'evidence', 'tools'):
        (OUT / name).mkdir(parents=True)
    shutil.copytree(PARAM, OUT / 'quantized')
    for name in ('locator_model.py', 'locator_context_b.py', 'gesture_model_v4_six_class.py'):
        shutil.copy2(BASE / 'reference/models' / name, OUT / 'reference/models' / name)
    shutil.copy2(BASE / 'models/locator_best.pt', OUT / 'models/locator_best.pt')
    model_source = ROOT / 'gesture_CNN/models_classifier_lab_dim_mix_B_20261023/translation4/classifier_final.pt'
    shutil.copy2(model_source, OUT / 'models/classifier_final.pt')
    shutil.copy2(BASE / 'reference/locator_temporal_pc.py', OUT / 'reference/locator_temporal_pc.py')
    shutil.copy2(BASE / 'hardware_contract/integer_contract_rules.py', OUT / 'hardware_contract/integer_contract_rules.py')
    # Reuse the proven core arithmetic, with only the pipeline changed from A to B.
    integer_source = (BASE / 'reference/integer_vision_reference.py').read_text(encoding='utf-8')
    start, end = integer_source.index('    def predict(self,frame,timestamp=None):'), integer_source.index('\n\ndef main():')
    methods = '''    def classify_input(self,image):
        logits,_,_=forward_classifier(image,self.classifier)
        k=int(np.argmax(logits))
        return {'class_id':k,'class':CLASSES[k],'logits_i32':logits.tolist()}

    def predict(self,frame,timestamp=None):
        from preprocessing import preprocess_bgr_to_locator_input
        return self.predict_small(preprocess_bgr_to_locator_input(frame),timestamp)

    def predict_small(self,small,timestamp=None):
        from preprocessing import clipped_int_box,square_roi_from_source_box,classifier_from_small,small_roi_descriptor
        small=np.asarray(small)
        if small.dtype!=np.uint8 or small.shape!=(128,128):raise ValueError('Expected128x128uint8')
        if small[:16].any() or small[112:].any():raise ValueError('Letterbox rows must be zero')
        raw,_,_=forward_locator(small,self.locator)
        decoded=decode_locator(raw,self.locator,640,480)
        effective=decoded['bbox_source'];filtered=None
        if self.stabilizer is not None:
            if timestamp is None:raise ValueError('Acquisition timestamp seconds required')
            filtered=self.stabilizer.update(effective,decoded['detected'],640,480,timestamp)
            effective=filtered['effective_box']
        roi=None;classification=None;descriptor=None
        if decoded['detected'] and decoded['bbox_source'][2]>decoded['bbox_source'][0] and decoded['bbox_source'][3]>decoded['bbox_source'][1]:
            roi=square_roi_from_source_box(clipped_int_box(effective,640,480),640,480,.18)
            descriptor=small_roi_descriptor(roi)
            classification=self.classify_input(classifier_from_small(small,roi))
        return {**decoded,'effective_bbox_source':list(effective),'roi_source':list(roi) if roi else None,
                'small_roi':descriptor,'classifier':classification,'stabilizer':filtered,
                'fresh_target_gesture':bool(classification and classification['class_id']!=0)}
'''
    integer_source = integer_source[:start] + methods + integer_source[end:]
    integer_source = integer_source.replace('from pc_reference import verify_files\n    verify_files()',
        'from verify_delivery import verify_hashes\n    verify_hashes(root)')
    integer_source = integer_source.replace("parser.add_argument('--image',type=Path);args=parser.parse_args()",
        "parser.add_argument('--image',type=Path);parser.add_argument('--small-npy',type=Path);args=parser.parse_args()")
    integer_source = integer_source.replace("    else:parser.error('Choose --verify or --image')",
        "    elif args.small_npy:print(json.dumps(runtime.predict_small(np.load(args.small_npy,allow_pickle=False)),ensure_ascii=False,indent=2))\n    else:parser.error('Choose --verify, --image or --small-npy')")
    (OUT / 'reference/integer_vision_reference.py').write_text(integer_source, encoding='utf-8')
    shutil.copy2(TOOLS / 'pc_reference_v2_template.py', OUT / 'reference/pc_reference.py')
    shutil.copy2(TOOLS / 'verify_v2_delivery_template.py', OUT / 'reference/verify_delivery.py')
    # Keep exact original geometry helpers, replace only the source-image sampling.
    pre_path = BASE / 'reference/preprocessing.py'; pre_text = pre_path.read_text(encoding='utf-8')
    tree = ast.parse(pre_text)
    geometry = '\n\n'.join(ast.get_source_segment(pre_text, node) for name in ('clipped_int_box', 'square_roi_from_source_box')
        for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    preprocessing = '''from pathlib import Path
import cv2 as cv
import numpy as np

def read_bgr_image(path):
    image=cv.imdecode(np.fromfile(Path(path),np.uint8),cv.IMREAD_COLOR)
    if image is None:raise ValueError('Cannot decode image')
    return image

def preprocess_bgr_to_locator_input(frame):
    if frame.dtype!=np.uint8 or frame.shape!=(480,640,3):raise ValueError('Actual640x480BGRrequired;no resize')
    gray=cv.cvtColor(frame,cv.COLOR_BGR2GRAY)
    small=np.zeros((128,128),np.uint8)
    small[16:112]=gray[0:480:5,0:640:5]
    return small

def small_roi_descriptor(roi):
    if len(roi)!=4 or any(not isinstance(v,(int,np.integer)) for v in roi):raise ValueError('ROI edges must be integers')
    x0,y0,x1,y1=map(int,roi);side=x1-x0
    if not(0<=x0<x1<=640 and 0<=y0<y1<=480 and y1-y0==side):raise ValueError('Illegal squareROI')
    sx,sy,ss=x0//5,16+y0//5,(side+4)//5
    if not(0<=sx and 16<=sy and sx+ss<=128 and sy+ss<=112):raise ValueError('Illegal smallROI')
    return {'sx':sx,'sy':sy,'ss':ss}

def classifier_from_small(small,roi):
    if small.dtype!=np.uint8 or small.shape!=(128,128):raise ValueError('Expected small128')
    d=small_roi_descriptor(roi);idx=np.arange(32,dtype=np.int64)*d['ss']//32
    return small[d['sy']+idx[:,None],d['sx']+idx[None,:]]

def classifier_input(frame,roi):return classifier_from_small(preprocess_bgr_to_locator_input(frame),roi)

'''
    (OUT / 'reference/preprocessing.py').write_text(preprocessing + geometry + '\n', encoding='utf-8')
    # Import only from the newly isolated reference directory.
    sys.path.insert(0, str(OUT / 'reference')); sys.path.insert(0, str(OUT / 'reference/models'))
    ops = import_path('v2_builder_ops', OUT / 'reference/integer_vision_reference.py')
    pre = import_path('v2_builder_pre', OUT / 'reference/preprocessing.py')
    pc = import_path('v2_builder_pc', OUT / 'reference/pc_reference.py')
    runtime, mixed = ops.IntegerVision(OUT), pc.VisionReference()
    lp, cp = runtime.locator, runtime.classifier
    base_lp = dict(np.load(BASE / 'quantized/locator/parameters.npz', allow_pickle=False))
    assert all(np.array_equal(lp[k], base_lp[k]) for k in lp if k != 'confidence_threshold_i32')
    assert int(lp['confidence_threshold_i32']) == -11748
    data = ROOT / 'gesture_CNN/datasets/classifier_lab_dim_mix_B_20261023'
    records = [json.loads(s) for s in (data / 'train_manifest.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    bank = np.load(data / 'train_inputs_u8.npy', allow_pickle=False)
    selected = []
    for cohort in ('original_TRAIN', 'lab_TRAIN'):
        for label in ops.CLASSES:
            candidates = [i for i, r in enumerate(records) if r['training_cohort'] == cohort and r['class_name'] == label
                and r['roi_source'] is not None and (label == 'background' or r['locator_confidence_raw_i32'] >= -11748)]
            selected.extend(candidates[:2])
        extra = next(i for i, r in enumerate(records) if r['training_cohort'] == cohort and r['class_name'] != 'background'
            and -11748 <= r['locator_confidence_raw_i32'] < -2726 and i not in selected)
        selected.append(extra)
    assert len(selected) == len(set(selected)) == 26
    index = {'kind': 'int8_uint8_int32_B_gate0.30_full_CNN_goldens', 'selection': 'twoTRAIN_per_class_per_cohort_plus_two_newly_accepted', 'samples': []}
    locator_ranges = {}; oracle_checks = 0
    for number, i in enumerate(selected):
        row = records[i]; name = f'sample_{number:02d}'; folder = OUT / 'golden_integer' / name
        folder.mkdir(); (folder / 'banks').mkdir()
        shutil.copy2(row['image'], folder / 'source.png')
        frame = pre.read_bgr_image(folder / 'source.png'); small = pre.preprocess_bgr_to_locator_input(frame)
        raw, ls, ranges = ops.forward_locator(small, lp)
        decoded = ops.decode_locator(raw, lp)
        assert decoded['confidence_raw_i32'] == row['locator_confidence_raw_i32'] and decoded['peak_xy'] == row['peak_xy']
        roi = tuple(row['roi_source']); classifier_input = pre.classifier_from_small(small, roi)
        assert np.array_equal(classifier_input, bank[i, 0])
        # Independent scalar VGA coordinate oracle, no default resize implementation.
        gray = __import__('cv2').cvtColor(frame, __import__('cv2').COLOR_BGR2GRAY)
        x0, y0, x1, y1 = roi; ss = (x1 - x0 + 4) // 5
        scalar = np.array([[gray[5 * (y0 // 5 + y * ss // 32), 5 * (x0 // 5 + x * ss // 32)] for x in range(32)] for y in range(32)], np.uint8)
        assert np.array_equal(classifier_input, scalar)
        logits, cs, _ = ops.forward_classifier(classifier_input, cp)
        _, lo, _ = ops.forward_locator(small, lp, oracle=True)
        _, co, _ = ops.forward_classifier(classifier_input, cp, oracle=True)
        assert all(np.array_equal(a, lo[k]) for k, a in ls.items())
        assert all(np.array_equal(a, co[k]) for k, a in cs.items()); oracle_checks += 1
        for layer, values in ranges.items():
            item = locator_ranges.setdefault(layer, {'min': values['min'], 'max': values['max'], 'overflow_count': 0})
            item['min'] = min(item['min'], values['min']); item['max'] = max(item['max'], values['max'])
            item['overflow_count'] += values['overflow_count']
        combined = {'locator_input_u8': small, 'classifier_input_u8': classifier_input,
            **{'locator_' + k: a for k, a in ls.items()}, **{'classifier_' + k: a for k, a in cs.items()}}
        np.savez_compressed(folder / 'layers.npz', **combined)
        np.save(folder / 'locator_input_u8.npy', small, allow_pickle=False)
        np.save(folder / 'classifier_input_u8.npy', classifier_input, allow_pickle=False)
        specs = {k: save_mem(folder / (k + '.mem'), a) for k, a in combined.items()}
        _, floats = mixed.forward_classifier(classifier_input); np.savez_compressed(folder / 'float_classifier_layers.npz', **floats)
        stream = [((channel * 256 + cell) << 32) | (int(raw[channel, cell // 16, cell % 16]) & 0xFFFFFFFF)
            for cell in range(256) for channel in range(5)]
        (folder / 'locator_output_stream_addr12_data32.mem').write_text(''.join(f'{v:011X}\n' for v in stream), encoding='ascii')
        act0 = bank_pack(ls['conv3_pool_u8'])
        residual = ls['g2_acc_i32'].astype(np.int64).reshape(4, 256) & 0xFFFFFFFF
        for k in range(4):
            for byte in range(4): act0[2 * k + (byte >> 1), 0x200 + (byte & 1) * 256:0x300 + (byte & 1) * 256] = (residual[k] >> (8 * byte)) & 255
        for kind, values in (('act0_F3_and_residual', act0), ('act1_G1', bank_pack(ls['g1_u8'])), ('act1_F4', bank_pack(ls['conv4_u8']))):
            for k in range(8):
                data_bytes = values[k].tobytes(); (folder / 'banks' / f'{kind}_bank{k}.bin').write_bytes(data_bytes)
                save_mem(folder / 'banks' / f'{kind}_bank{k}.mem', values[k])
        write(folder / 'layout.json', {'arrays': specs, 'output_stream': '44bit{addr12,data32};cell-major/channel0..4',
            'bank_valid_bytes': {'act0_F3_and_residual': [0, 1024], 'act1_G1': [0, 256], 'act1_F4': [0, 768]},
            'zero_unwritten_bytes': 'fixture padding only;not a whole-RAM-clear requirement'})
        index['samples'].append({'id': name, 'image': f'golden_integer/{name}/source.png', 'source_role': 'TRAIN',
            'source_image_id': row['image_id'], 'source_sha256': row['image_sha256'], 'class_label': row['class_name'],
            'vectors': f'golden_integer/{name}/layers.npz', 'float_classifier_vectors': f'golden_integer/{name}/float_classifier_layers.npz',
            'classifier_input_role': 'production' if decoded['detected'] else 'rejected_empty_peak_diagnostic',
            'pipeline': runtime.predict(frame), 'pipeline_float_classifier': mixed.predict(frame)})
        print({'golden': name, 'truth': row['class_name'], 'accepted': decoded['detected'], 'oracle': 'EXACT'}, flush=True)
    write(OUT / 'golden_integer/index.json', index)
    assert sum(v['overflow_count'] for v in locator_ranges.values()) == 0
    # Parameter MEM readback, arithmetic edges, and immutable Locator ROM.
    for kind, name in (('locator', 'model_rom_16k'), ('classifier', 'weights_all'), ('classifier', 'layer_descriptors')):
        path = OUT / 'quantized' / kind / (name + '.mem')
        binary = np.array([int(line, 16) for line in path.read_text().splitlines()], dtype='<u4').tobytes()
        assert binary == path.with_suffix('.bin').read_bytes()
    assert sha(OUT / 'quantized/locator/model_rom_16k.bin') == sha(BASE / 'quantized/locator/model_rom_16k.bin')
    assert ops.wrap32(np.array([1 << 31, -(1 << 31) - 1])).tolist() == [-(1 << 31), (1 << 31) - 1]
    assert ops.round_shift(np.array([-3, -1, 1, 3]), 1, 1).tolist() == [-1, 0, 1, 2]
    assert ops.round_shift(np.array([-1, 1]), 5, 0).tolist() == [-5, 5]
    write(OUT / 'evidence/golden_build_validation.json', {'status': 'PASS_FULL_B_GOLDEN_BUILD', 'samples': len(selected),
        'independent_tap_scalarDense_oracle_samples': oracle_checks, 'B_VGA_scalar_sampling_exact': True,
        'parameter_MEM_binary_exact': True, 'unchanged_locator_ROM_and_all_quant_except_gate': True,
        'locator_ranges_golden_frames': locator_ranges, 'RTL_simulated': False})
    for name, path in (('quantization_validation.json', PARAM / 'validation.json'),
        ('quantization_validation_rows.json', PARAM / 'validation_rows.json'),
        ('training_analysis.json', ROOT / 'gesture_CNN/reports/classifier_lab_dim_mix_analysis_20261023/summary.json'),
        ('training_analysis.md', ROOT / 'gesture_CNN/reports/classifier_lab_dim_mix_analysis_20261023/RESULTS_CN.md'),
        ('threshold_comparison.json', ROOT / 'hand_locator/reports/locator_gate030_20261024/summary.json')):
        shutil.copy2(path, OUT / 'evidence' / name)
    for source in (Path(__file__), TOOLS / 'export_lab_mix_v2_20261024.py', TOOLS / 'pc_reference_v2_template.py', TOOLS / 'verify_v2_delivery_template.py'):
        shutil.copy2(source, OUT / 'tools' / source.name)
    (OUT / '.gitattributes').write_text('* -text -filter\n', encoding='utf-8')
    (OUT / '.gitignore').write_text('__pycache__/\n*.pyc\n!quantized/**/*.bin\n!golden_integer/**/*.bin\n', encoding='utf-8')
    write(OUT / 'manifest.json', {'release_id': ID, 'date': '2026-10-24', 'status': 'BUILD_COMPLETE_PENDING_PORTABLE_VERIFY_AND_DOCS',
        'locator': {'path': 'models/locator_best.pt', 'sha256': sha(OUT / 'models/locator_best.pt'), 'weights_changed_from_v1': False},
        'classifier': {'path': 'models/classifier_final.pt', 'sha256': sha(OUT / 'models/classifier_final.pt'), 'parameters': 39110, 'class_names': list(ops.CLASSES)},
        'pc_contract': {'threshold': .3, 'threshold_raw_int32': -11748, 'roi_margin': .18, 'preprocessing': 'Phase2_B_exact_small_ROI_nearest32', 'stabilization_enabled': True},
        'git': {'repository': 'https://github.com/filid-123/Gesture.git', 'branch': 'dev/Rain', 'candidate_path': 'model_package/candidates/' + ID},
        'files_sha256': {p.relative_to(OUT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.relative_to(OUT).as_posix() != 'manifest.json'}})
    print({'status': 'V2_PACKAGE_BUILT_PENDING_PORTABLE_VERIFY', 'path': str(OUT), 'samples': len(selected),
        'files': sum(p.is_file() for p in OUT.rglob('*'))})


if __name__ == '__main__': main()
